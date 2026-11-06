"""Первый шаг заявки: открытая форма, заявка вошедшего пользователя, вебхук и связь с людьми из базы."""

from urllib.parse import parse_qs, urlparse

import pytest
from sk_common.people.models import Person
from sk_common.testing import login_as

from app.modules.applications.form import ApplicationForm, FormField
from app.modules.applications.models import Application
from app.modules.applications.webhook import is_test_request, parse
from app.modules.events.models import Direction, Event, ParticipationForm
from tests.test_applications import SLUG, _open_event, _other, _payload

pytestmark = pytest.mark.usefixtures('redis_clean')

REGISTER = f'/api/v1/public/events/{SLUG}/register'
ANNA = {'full_name': 'Иванова Анна', 'email': 'Anna@Example.org', 'phone': '+7 900 000-00-00', 'grade': '9'}
CONSENT = {'consents': ['personal_data']}


def _anonymous(client):
    """Клиент без cookie: посетитель открытой формы."""
    return _other(client)


async def _pending_id(client, event) -> int:
    listing = (await client.get(f'/api/v1/events/{event["id"]}/applications', params={'status': 'requested'})).json()
    return listing['items'][-1]['id']


def _invite_token(queue) -> str:
    """Токен входа из последнего письма-приглашения."""
    _, args, _ = next(job for job in reversed(queue.jobs) if job[1][1].startswith('Заявка подтверждена'))
    link = next(word for word in args[2].split() if '/auth/magic' in word)
    return parse_qs(urlparse(link).query)['token'][0]


async def _webhook_url(client, event) -> str:
    response = await client.post(f'/api/v1/events/{event["id"]}/webhook')
    assert response.status_code == 200
    return urlparse(response.json()['url']).path


async def test_open_form_then_invitation_to_cabinet(db, client, queue):
    event = await _open_event(db, client)
    async with _anonymous(client) as visitor:
        sent = await visitor.post(REGISTER, json={**ANNA, **CONSENT})
        assert sent.status_code == 201, sent.text
        assert sent.json()['application_id'] is None  # посетитель без входа не получает доступ к заявке
        assert queue.jobs[-1][1][0] == 'anna@example.org' and 'Заявка получена' in queue.jobs[-1][1][1]

        # повторная отправка не создаёт копию
        assert (await visitor.post(REGISTER, json={**ANNA, **CONSENT})).status_code == 201
        listing = (await client.get(f'/api/v1/events/{event["id"]}/applications')).json()
        assert listing['counts'] == {'requested': 1} and listing['items'][0]['is_linked'] is False
        assert listing['items'][0]['applicant_name'] == 'Иванова Анна'

        app_id = listing['items'][0]['id']
        opened = (await client.get(f'/api/v1/applications/{app_id}')).json()
        assert opened['source'] == 'form' and opened['allowed_decisions'] == ['confirmed', 'rejected']
        assert opened['consents'][0]['key'] == 'personal_data'

        confirmed = await client.post(f'/api/v1/applications/{app_id}/decision', json={'status': 'confirmed'})
        assert confirmed.status_code == 200, confirmed.text
        body = confirmed.json()
        assert body['status'] == 'draft' and body['is_linked'] is True
        assert body['members'][0]['full_name'] == 'Иванова Анна' and body['members'][0]['grade'] == '9'

        # ссылка из письма входит сразу и ведёт к заявке
        token = _invite_token(queue)
        login = await visitor.post('/api/v1/auth/magic-link/verify', json={'token': token})
        assert login.status_code == 200 and login.json()['next'] == f'/my/applications/{app_id}'
        mine = await visitor.get(f'/api/v1/applications/{app_id}')
        assert mine.json()['can_submit'] is True and mine.json()['allowed_decisions'] == []

        await visitor.put(f'/api/v1/applications/{app_id}', json=_payload(event))
        submitted = await visitor.post(f'/api/v1/applications/{app_id}/submit')
        assert submitted.json()['status'] == 'submitted', submitted.text


async def test_open_form_validation(db, client):
    event = await _open_event(db, client, registration={'asked': ['phone', 'title', 'direction']})
    async with _anonymous(client) as visitor:
        response = await visitor.post(REGISTER, json={'phone': 'abc'})
        assert response.status_code == 422
        errors = response.json()['detail']['errors']
        assert set(errors) == {'full_name', 'email', 'phone', 'title', 'direction_id', 'consent:personal_data'}

        direction = event['directions'][0]['id']
        fine = await visitor.post(REGISTER, json={**ANNA, **CONSENT, 'title': 'Работа', 'direction_id': direction})
        assert fine.status_code == 201, fine.text


async def test_questions_on_registration_step(db, client):
    question = {'key': 'city', 'type': 'text', 'label': 'Город', 'required': True, 'on_registration': True}
    event = await _open_event(db, client, fields=[question])
    async with _anonymous(client) as visitor:
        missing = await visitor.post(REGISTER, json={**ANNA, **CONSENT})
        assert missing.json()['detail']['errors'] == {'city': 'Заполните поле'}
        assert (
            await visitor.post(REGISTER, json={**ANNA, **CONSENT, 'answers': {'city': 'Москва'}})
        ).status_code == 201
    app_id = await _pending_id(client, event)
    assert (await client.get(f'/api/v1/applications/{app_id}')).json()['answers'] == {'city': 'Москва'}

    form = (await client.get(f'/api/v1/events/{event["id"]}/form')).json()
    form['fields'].append({'key': 'doc', 'type': 'file', 'label': 'Файл', 'on_registration': True})
    assert (await client.put(f'/api/v1/events/{event["id"]}/form', json=form)).status_code == 422


async def test_closed_form_requires_login(db, client):
    await _open_event(db, client, registration={'open_form': False})
    async with _anonymous(client) as visitor:
        denied = await visitor.post(REGISTER, json={**ANNA, **CONSENT})
        assert denied.status_code == 422 and 'войдите' in denied.json()['detail']['message']
        await login_as(db, visitor, email='anna@example.org')
        assert (await visitor.post(REGISTER, json=CONSENT)).status_code == 201


async def test_registered_user_applies_from_cabinet(db, client):
    event = await _open_event(db, client)
    async with _other(client) as applicant:
        user = await login_as(db, applicant, email='anna@example.org', last_name='Иванова')
        opened = (await applicant.get('/api/v1/public/events')).json()
        assert [e['slug'] for e in opened] == [SLUG]

        # данные учётной записи важнее присланных: нельзя подать заявку от чужого адреса
        sent = await applicant.post(REGISTER, json={**CONSENT, 'email': 'other@example.org', 'full_name': 'Другой'})
        app = (await applicant.get(f'/api/v1/applications/{sent.json()["application_id"]}')).json()
        assert app['status'] == 'requested' and app['source'] == 'cabinet'
        assert app['applicant_email'] == 'anna@example.org' and app['applicant_name'] == 'Иванова Тест'
        assert app['can_edit'] is False and app['can_withdraw'] is True
        assert [a['id'] for a in (await applicant.get('/api/v1/my/applications')).json()] == [app['id']]

        confirmed = await client.post(f'/api/v1/applications/{app["id"]}/decision', json={'status': 'confirmed'})
        assert confirmed.json()['members'][0]['person_id'] == user.person_id

        withdrawn = await applicant.post(f'/api/v1/applications/{app["id"]}/withdraw')
        assert withdrawn.json()['status'] == 'withdrawn'
    assert event['id']


async def test_confirmation_attaches_existing_user_by_email(db, client):
    event = await _open_event(db, client)
    async with _other(client) as anna:
        user = await login_as(db, anna, email='anna@example.org', last_name='Иванова')
        async with _anonymous(client) as visitor:
            await visitor.post(REGISTER, json={**ANNA, **CONSENT})
        app_id = await _pending_id(client, event)
        matches = (await client.get(f'/api/v1/applications/{app_id}/matches')).json()
        assert matches[0]['by_email'] is True and matches[0]['person_id'] == user.person_id

        await client.post(f'/api/v1/applications/{app_id}/decision', json={'status': 'confirmed'})
        assert [a['id'] for a in (await anna.get('/api/v1/my/applications')).json()] == [app_id]


async def test_moderator_links_application_to_person_from_directory(db, client, queue):
    """Человек из SkolStream ещё не входил в систему: у него появляется учётная запись, письмо идёт на его адрес."""
    event = await _open_event(db, client)
    person = Person(
        source='skolstream', last_name='Петрова', first_name='Мария', email='petrova@sk.example.org', is_student=True
    )
    db.add(person)
    await db.commit()
    async with _anonymous(client) as visitor:
        await visitor.post(REGISTER, json={**CONSENT, 'full_name': 'Мария Петрова', 'email': 'home@example.org'})
    app_id = await _pending_id(client, event)
    assert (await client.get(f'/api/v1/applications/{app_id}/matches')).json()[0]['person_id'] == person.id

    found = (await client.get(f'/api/v1/events/{event["id"]}/people', params={'q': 'петрова мар'})).json()
    assert [p['person_id'] for p in found] == [person.id] and found[0]['has_account'] is False
    assert found[0]['kind'] == 'student'

    linked = await client.put(f'/api/v1/applications/{app_id}/person', json={'person_id': person.id})
    assert linked.status_code == 200, linked.text
    assert linked.json()['applicant_email'] == 'petrova@sk.example.org' and linked.json()['is_linked'] is True

    # связь можно снять, пока заявка не подтверждена
    unlinked = await client.delete(f'/api/v1/applications/{app_id}/person')
    assert unlinked.json()['is_linked'] is False and unlinked.json()['applicant_email'] == 'home@example.org'
    await client.put(f'/api/v1/applications/{app_id}/person', json={'person_id': person.id})

    confirmed = (await client.post(f'/api/v1/applications/{app_id}/decision', json={'status': 'confirmed'})).json()
    assert confirmed['members'][0]['person_id'] == person.id and confirmed['members'][0]['full_name'] == 'Петрова Мария'
    assert (await client.delete(f'/api/v1/applications/{app_id}/person')).status_code == 422
    invitation = next(job for job in reversed(queue.jobs) if job[1][1].startswith('Заявка подтверждена'))
    assert invitation[1][0] == 'petrova@sk.example.org'

    # заявку после подтверждения можно передать другому человеку, состав обновится
    other = Person(source='local', last_name='Сидорова', first_name='Ольга', email='sidorova@example.org')
    db.add(other)
    await db.commit()
    moved = (await client.put(f'/api/v1/applications/{app_id}/person', json={'person_id': other.id})).json()
    assert moved['applicant_email'] == 'sidorova@example.org'
    assert moved['members'][0]['person_id'] == other.id and moved['members'][0]['full_name'] == 'Сидорова Ольга'


async def test_link_rejects_email_taken_by_another_account(db, client):
    event = await _open_event(db, client)
    async with _other(client) as anna:
        await login_as(db, anna, email='anna@example.org')
    person = Person(source='local', last_name='Без', first_name='Адреса')
    db.add(person)
    await db.commit()
    async with _anonymous(client) as visitor:
        await visitor.post(REGISTER, json={**ANNA, **CONSENT})
    app_id = await _pending_id(client, event)
    response = await client.put(f'/api/v1/applications/{app_id}/person', json={'person_id': person.id})
    assert response.status_code == 422 and 'занят' in response.json()['detail']['message']


async def test_reject_and_return_first_step(db, client, queue):
    event = await _open_event(db, client)
    async with _anonymous(client) as visitor:
        await visitor.post(REGISTER, json={**ANNA, **CONSENT})
    app_id = await _pending_id(client, event)
    url = f'/api/v1/applications/{app_id}/decision'
    assert (await client.post(url, json={'status': 'rejected'})).status_code == 422  # нужен комментарий
    rejected = (await client.post(url, json={'status': 'rejected', 'comment': 'Не подходит возраст'})).json()
    assert rejected['status'] == 'rejected' and rejected['allowed_decisions'] == ['requested']
    assert queue.jobs[-1][1][0] == 'anna@example.org' and 'Не подходит возраст' in queue.jobs[-1][1][2]
    assert (await client.post(url, json={'status': 'accepted'})).status_code == 422
    assert (await client.post(url, json={'status': 'requested'})).json()['status'] == 'requested'


async def test_one_step_event_is_accepted_on_confirmation(db, client, queue):
    organizer = await login_as(db, client, email='org@skolkovo.example.org')
    organizer.person.is_employee = True
    await db.commit()
    event = (
        await client.post(
            '/api/v1/events', json={'modules': {'registration': True}, 'title': 'Лекция', 'slug': 'lecture'}
        )
    ).json()
    url = f'/api/v1/events/{event["id"]}'
    await client.patch(url, json={'date_start': '2027-03-12'})
    await client.post(f'{url}/status', json={'status': 'registration'})
    async with _anonymous(client) as visitor:
        sent = await visitor.post('/api/v1/public/events/lecture/register', json={**ANNA, **CONSENT})
        assert sent.status_code == 201, sent.text
    app_id = await _pending_id(client, event)
    confirmed = (await client.post(f'/api/v1/applications/{app_id}/decision', json={'status': 'confirmed'})).json()
    assert confirmed['status'] == 'accepted' and confirmed['members'][0]['full_name'] == 'Иванова Анна'
    assert 'Заявка принята' in queue.jobs[-1][1][1]


async def test_moderator_fixes_contact_and_resends_invitation(db, client, queue):
    event = await _open_event(db, client)
    async with _anonymous(client) as visitor:
        await visitor.post(REGISTER, json={**ANNA, **CONSENT})
    app_id = await _pending_id(client, event)
    fixed = await client.put(
        f'/api/v1/applications/{app_id}/contact', json={'name': 'Иванова Анна', 'email': 'anna.new@example.org'}
    )
    assert fixed.status_code == 200 and fixed.json()['contact']['email'] == 'anna.new@example.org'
    assert (await client.post(f'/api/v1/applications/{app_id}/invite')).status_code == 422  # ещё не подтверждена
    await client.post(f'/api/v1/applications/{app_id}/decision', json={'status': 'confirmed'})
    first = _invite_token(queue)
    assert (await client.post(f'/api/v1/applications/{app_id}/invite')).status_code == 200
    assert _invite_token(queue) != first


async def test_rights_for_moderator_and_strangers(db, client):
    event = await _open_event(db, client)
    await client.post(f'/api/v1/events/{event["id"]}/members', json={'email': 'mod@example.org', 'role': 'moderator'})
    async with _anonymous(client) as visitor:
        await visitor.post(REGISTER, json={**ANNA, **CONSENT})
    app_id = await _pending_id(client, event)
    async with _other(client) as moderator, _other(client) as stranger:
        await login_as(db, stranger, email='stranger@example.org')
        for call in (
            stranger.get(f'/api/v1/applications/{app_id}'),
            stranger.get(f'/api/v1/applications/{app_id}/matches'),
            stranger.get(f'/api/v1/events/{event["id"]}/people', params={'q': 'иванова'}),
            stranger.put(f'/api/v1/applications/{app_id}/contact', json={}),
        ):
            assert (await call).status_code == 404

        from tests.test_evaluation import _as

        async with await _as(db, client, 'mod@example.org') as moderator:
            assert (await moderator.get(f'/api/v1/applications/{app_id}/matches')).status_code == 200
            # настройка вебхука — только у организатора
            assert (await moderator.post(f'/api/v1/events/{event["id"]}/webhook')).status_code == 403
            confirmed = await moderator.post(f'/api/v1/applications/{app_id}/decision', json={'status': 'confirmed'})
            assert confirmed.status_code == 200


# --- Вебхук ----------------------------------------------------------------------------------


async def test_tilda_webhook(db, client, queue):
    event = await _open_event(db, client)
    url = await _webhook_url(client, event)
    async with _anonymous(client) as tilda:
        ping = await tilda.post(url, data={'test': 'test'})
        assert ping.status_code == 200 and ping.text == 'ok'
        assert (await client.get(f'/api/v1/events/{event["id"]}/applications')).json()['total'] == 0

        form = {
            'Name': 'Иванова Анна',
            'Email': 'anna@example.org',
            'Phone': '+7 (900) 000-00-00',
            'Школа': 'Лицей №1',
            'Направление': 'инженерия',
            'annotation': 'Описание работы',
            'tranid': '123:456',
            'formid': 'form1',
            'COOKIES': 'секрет',
        }
        response = await tilda.post(url, data=form)
        assert response.status_code == 200 and response.text == 'ok', response.text
        # повторная доставка той же записи ничего не добавляет
        assert (await tilda.post(url, data=form)).status_code == 200

    listing = (await client.get(f'/api/v1/events/{event["id"]}/applications')).json()
    assert listing['total'] == 1
    app = (await client.get(f'/api/v1/applications/{listing["items"][0]["id"]}')).json()
    assert app['source'] == 'webhook' and app['status'] == 'requested' and app['is_linked'] is False
    assert app['contact']['name'] == 'Иванова Анна' and app['contact']['organization'] == 'Лицей №1'
    assert app['direction']['id'] == event['directions'][0]['id']
    assert app['answers'] == {'annotation': 'Описание работы'}
    assert app['raw_payload']['tranid'] == '123:456' and 'COOKIES' not in app['raw_payload']
    assert app['consents'] == []  # согласие человек даст уже в кабинете
    assert 'Заявка получена' in queue.jobs[-1][1][1]


async def test_webhook_json_and_custom_field_names(db, client):
    registration = {'webhook_fields': {'full_name': 'participant', 'email': 'contact'}}
    event = await _open_event(db, client, registration=registration)
    url = await _webhook_url(client, event)
    async with _anonymous(client) as app_client:
        sent = await app_client.post(url, json={'participant': 'Борис', 'contact': 'boris@example.org', 'name': 'Нет'})
        assert sent.status_code == 200, sent.text
    item = (await client.get(f'/api/v1/events/{event["id"]}/applications')).json()['items'][0]
    assert item['applicant_name'] == 'Борис' and item['applicant_email'] == 'boris@example.org'


async def test_webhook_rejections(db, client):
    event = await _open_event(db, client)
    url = await _webhook_url(client, event)
    event_url = f'/api/v1/events/{event["id"]}'
    async with _anonymous(client) as tilda:
        assert (await tilda.post('/api/v1/public/webhooks/wrong', data={'Name': 'Анна'})).status_code == 404
        assert (await tilda.post(url, data={'comment': 'пусто'})).status_code == 422
        assert (await tilda.post(url, content=b'x' * 70000)).status_code == 413

        # приём закрыт: заявку всё равно берём, решит модератор
        await client.patch(
            event_url,
            json={'registration_opens_at': '2020-01-01T00:00:00Z', 'registration_closes_at': '2020-01-02T00:00:00Z'},
        )
        assert (await tilda.post(url, data={'Name': 'Анна'})).status_code == 200

        await client.post(f'{event_url}/status', json={'status': 'draft'})
        assert (await tilda.post(url, data={'Name': 'Борис'})).status_code == 409

        # смена адреса отключает прежний
        assert await _webhook_url(client, event) != url
        assert (await tilda.post(url, data={'Name': 'Вера'})).status_code == 404
        off = await client.delete(f'{event_url}/webhook')
        assert off.json() == {'url': None}


async def test_webhook_without_email_needs_moderator(db, client):
    event = await _open_event(db, client)
    url = await _webhook_url(client, event)
    async with _anonymous(client) as tilda:
        await tilda.post(url, data={'Name': 'Анна', 'Email': 'не адрес'})
    app_id = await _pending_id(client, event)
    app = (await client.get(f'/api/v1/applications/{app_id}')).json()
    assert app['contact']['email'] == '' and app['raw_payload']['Email'] == 'не адрес'
    refused = await client.post(f'/api/v1/applications/{app_id}/decision', json={'status': 'confirmed'})
    assert refused.status_code == 422 and 'нет email' in refused.json()['detail']['message']
    stored = await db.get(Application, app_id, populate_existing=True)
    assert stored.status == 'requested' and stored.user_id is None


async def test_public_form_hides_webhook_settings(db, client):
    await _open_event(db, client, registration={'webhook_fields': {'email': 'secret_field'}})
    form = (await client.get(f'/api/v1/public/events/{SLUG}/form')).json()
    assert 'webhook_fields' not in form['form']['registration']
    assert form['event']['title'] == 'SkolStart'


def test_webhook_parse_coerces_answers():
    event = Event(title='Тест', slug='t', modules={})
    event.directions = [Direction(id=1, title='Инженерия')]
    event.participation_forms = [ParticipationForm(id=2, title='Доклад')]
    form = ApplicationForm(
        fields=[
            FormField(key='age', type='number', label='Возраст'),
            FormField(key='topics', type='multiselect', label='Темы', options=['A', 'B']),
            FormField(key='agree', type='checkbox', label='Согласен с правилами'),
            FormField(key='size', type='select', label='Размер', options=['S', 'M']),
            FormField(key='doc', type='file', label='Файл'),
        ]
    )
    payload = {
        'name': 'Анна',
        'ВОЗРАСТ': '12,5',
        'topics': 'A; B',
        'Согласен с правилами': 'yes',
        'size': 'XL',
        'doc': 'файл',
        'форма участия': 'доклад',
        'Tranid': '7',
    }
    data, external_id, raw = parse(event, form, payload)
    assert data.answers == {'age': 12.5, 'topics': ['A', 'B'], 'agree': True}
    assert data.participation_form_id == 2 and data.direction_id is None
    assert external_id == '7' and raw['size'] == 'XL'  # неподходящее значение осталось в исходных данных
    assert is_test_request({'test': 'test'}) and not is_test_request({'test': 'другое'})
