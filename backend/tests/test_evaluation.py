from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.auth.models import MagicLinkToken
from app.modules.auth.service import open_session
from app.modules.people.service import get_user_by_email
from tests.helpers import login_as
from tests.test_applications import _open_event, _other, _submitted

pytestmark = pytest.mark.usefixtures('redis_clean')


async def _as(db, client, email):
    """Клиент, вошедший под существующим пользователем."""
    other = _other(client)
    user = await get_user_by_email(db, email)
    access, _ = await open_session(db, user, 'magic_link', None, None)
    await db.commit()
    other.cookies.set(settings.auth.access_cookie, access)
    return other


async def _prepared_sheet(db, client, mode='mixed'):
    """Мероприятие с двумя принятыми заявками, шкалой, таблицей оценок и листом с судьями."""
    event = await _open_event(db, client)
    apps = []
    for email in ('anna@example.org', 'boris@example.org'):
        async with _other(client) as applicant:
            await login_as(db, applicant, email=email)
            apps.append(await _submitted(applicant, event))
    for app in apps:
        await client.post(f'/api/v1/applications/{app["id"]}/decision', json={'status': 'accepted'})

    url = f'/api/v1/events/{event["id"]}'
    scale = (
        await client.post(
            f'{url}/scales',
            json={
                'title': '0–2',
                'levels': [
                    {'title': 'Нет', 'points': 0},
                    {'title': 'Частично', 'points': 1},
                    {'title': 'Полностью', 'points': 2},
                ],
            },
        )
    ).json()
    scorecard = (
        await client.post(
            f'{url}/scorecards',
            json={
                'title': 'Проекты',
                'categories': ['Содержание'],
                'criteria': [
                    {'title': 'Актуальность', 'type': 'scale', 'scale_id': scale['id'], 'category': 0},
                    {
                        'title': 'Результаты',
                        'type': 'checklist',
                        'options': [
                            {'title': 'Есть прототип', 'points': 1},
                            {'title': 'Есть испытания', 'points': 1},
                            {'title': 'Ничего нет', 'points': 0, 'is_exclusive': True},
                        ],
                    },
                ],
            },
        )
    ).json()
    assert scorecard['max_score'] == '4.00'

    sheet = (
        await client.post(
            f'{url}/sheets',
            json={
                'title': 'Защита',
                'scorecard_id': scorecard['id'],
                'mode': mode,
            },
        )
    ).json()
    sheet_url = f'/api/v1/sheets/{sheet["id"]}'
    sheet = (await client.post(f'{sheet_url}/works', json={})).json()
    assert len(sheet['works']) == 2
    # руководитель обеих работ тоже в жюри — ему работы не достанутся
    sheet = (
        await client.put(
            f'{sheet_url}/judges',
            json={
                'judges': [
                    {'email': 'judge1@example.org'},
                    {'email': 'judge2@example.org'},
                    {'email': 'petrov@example.org'},
                ],
            },
        )
    ).json()
    result = (await client.post(f'{sheet_url}/distribute', json={'mode': 'all'})).json()
    assert result == {'created': 4, 'conflicts': 2}
    sheet = (await client.post(f'{sheet_url}/status', json={'status': 'active'})).json()
    return event, scorecard, sheet


async def test_judging_cycle_and_ranks(db, client):
    _, scorecard, sheet = await _prepared_sheet(db, client)
    scale_criterion, checklist = scorecard['criteria']
    levels = scale_criterion['scale']['levels']
    prototype, tests_done, nothing = (o['id'] for o in checklist['options'])

    judge1 = await _as(db, client, 'judge1@example.org')
    async with judge1:
        mine = (await judge1.get('/api/v1/my/sheets')).json()
        assert mine[0]['total'] == 2 and mine[0]['scored'] == 0
        works = (await judge1.get(f'/api/v1/my/sheets/{sheet["id"]}/works')).json()
        first, second = works
        url = f'/api/v1/evaluations/{first["evaluation_id"]}'

        bundle = (await judge1.get(url)).json()
        assert bundle['work']['participants'] == ['Иванова Анна'] and bundle['next_id'] == second['evaluation_id']
        assert bundle['work']['answers'][0]['label'] == 'Краткое описание работы'

        await judge1.put(f'{url}/criteria/{scale_criterion["id"]}', json={'level_id': levels[2]['id']})
        state = (
            await judge1.put(f'{url}/criteria/{checklist["id"]}', json={'option_ids': [prototype, tests_done]})
        ).json()
        assert state['score'] == '4.00' and state['is_scored'] is True

        state = (
            await judge1.put(f'{url}/criteria/{checklist["id"]}', json={'option_ids': [prototype, nothing]})
        ).json()
        assert state['items'][1]['option_ids'] == [nothing] and state['score'] == '2.00'

        bad = await judge1.put(f'{url}/criteria/{scale_criterion["id"]}', json={'level_id': 999})
        assert bad.status_code == 400

        second_url = f'/api/v1/evaluations/{second["evaluation_id"]}'
        await judge1.put(f'{second_url}/criteria/{scale_criterion["id"]}', json={'level_id': levels[1]['id']})
        await judge1.put(f'{second_url}/criteria/{checklist["id"]}', json={'option_ids': [prototype]})

    results = (await client.get(f'/api/v1/sheets/{sheet["id"]}')).json()
    by_number = {w['number']: w for w in results['works']}
    assert by_number[1]['score'] == '2.00' and by_number[2]['score'] == '2.00'
    assert by_number[1]['rank'] == by_number[2]['rank'] == 1  # равные баллы — общее место
    assert by_number[1]['is_scored'] is False  # второй судья ещё не оценил
    judge = next(j for j in results['judges'] if j['email'] == 'judge1@example.org')
    assert (judge['total'], judge['scored']) == (2, 2)

    # второй судья не видит чужую оценку и не может оценивать после закрытия листа
    judge2 = await _as(db, client, 'judge2@example.org')
    async with judge2:
        assert (await judge2.get(f'/api/v1/evaluations/{first["evaluation_id"]}')).status_code == 404
        own = (await judge2.get(f'/api/v1/my/sheets/{sheet["id"]}/works')).json()[0]
        await client.post(f'/api/v1/sheets/{sheet["id"]}/status', json={'status': 'closed'})
        closed = await judge2.put(
            f'/api/v1/evaluations/{own["evaluation_id"]}/criteria/{scale_criterion["id"]}',
            json={'level_id': levels[0]['id']},
        )
        assert closed.status_code == 400


async def test_anonymous_evaluation_counts_in_mixed_mode(db, client):
    _, scorecard, sheet = await _prepared_sheet(db, client)
    scale_criterion, checklist = scorecard['criteria']
    work = sheet['works'][0]
    token = work['public_token']

    public = (await client.get(f'/api/v1/public/evaluate/{token}')).json()
    assert public['open'] is True and public['work']['supervisors'] == [] and public['work']['files'] == []

    started = (await client.post(f'/api/v1/public/evaluate/{token}/start', json={'name': 'Гость'})).json()
    headers = {'X-Anonymous-Token': started['token']}
    level = scale_criterion['scale']['levels'][2]['id']
    await client.put(
        f'/api/v1/public/evaluate/{token}/criteria/{scale_criterion["id"]}', json={'level_id': level}, headers=headers
    )
    state = (
        await client.put(
            f'/api/v1/public/evaluate/{token}/criteria/{checklist["id"]}',
            json={'option_ids': [checklist['options'][0]['id']]},
            headers=headers,
        )
    ).json()
    assert state['score'] == '3.00' and state['is_scored'] is True

    no_token = await client.get(f'/api/v1/public/evaluate/{token}/evaluation')
    assert no_token.status_code == 401

    results = (await client.get(f'/api/v1/sheets/{sheet["id"]}')).json()
    scored = next(w for w in results['works'] if w['id'] == work['id'])
    assert scored['score'] == '3.00' and scored['anonymous_count'] == 1 and scored['rank'] == 1


async def test_jury_sheet_has_no_public_access(db, client):
    _, _, sheet = await _prepared_sheet(db, client, mode='jury')
    token = sheet['works'][0]['public_token']
    assert (await client.get(f'/api/v1/public/evaluate/{token}')).status_code == 404


async def test_scorecard_locked_after_scoring_and_judge_removal(db, client):
    event, scorecard, sheet = await _prepared_sheet(db, client)
    scale_criterion = scorecard['criteria'][0]
    judge1 = await _as(db, client, 'judge1@example.org')
    async with judge1:
        work = (await judge1.get(f'/api/v1/my/sheets/{sheet["id"]}/works')).json()[0]
        await judge1.put(
            f'/api/v1/evaluations/{work["evaluation_id"]}/criteria/{scale_criterion["id"]}',
            json={'level_id': scale_criterion['scale']['levels'][1]['id']},
        )

    locked = await client.put(f'/api/v1/scorecards/{scorecard["id"]}', json={'title': 'Новая', 'criteria': []})
    assert locked.status_code == 400
    copy = await client.post(f'/api/v1/scorecards/{scorecard["id"]}/copy')
    assert copy.status_code == 201 and len(copy.json()['criteria']) == 2

    removal = await client.put(
        f'/api/v1/sheets/{sheet["id"]}/judges', json={'judges': [{'email': 'judge2@example.org'}]}
    )
    assert removal.status_code == 400
    forced = await client.put(
        f'/api/v1/sheets/{sheet["id"]}/judges', json={'judges': [{'email': 'judge2@example.org'}], 'force': True}
    )
    assert [j['email'] for j in forced.json()['judges']] == ['judge2@example.org']


async def test_strangers_cannot_manage_sheets(db, client):
    event, _, sheet = await _prepared_sheet(db, client)
    async with _other(client) as stranger:
        await login_as(db, stranger, email='stranger@example.org')
        assert (await stranger.get(f'/api/v1/sheets/{sheet["id"]}')).status_code == 404
        assert (await stranger.get(f'/api/v1/events/{event["id"]}/scorecards')).status_code == 404
        assert (await stranger.get(f'/api/v1/my/sheets/{sheet["id"]}/works')).status_code == 404


async def test_judge_qr_login_and_moderator_controls(db, client):
    event, scorecard, sheet = await _prepared_sheet(db, client)
    sheet_url = f'/api/v1/sheets/{sheet["id"]}'
    level = scorecard['criteria'][0]['scale']['levels'][1]['id']
    criterion = scorecard['criteria'][0]['id']

    # судья без email: заводится по ФИО, входит только по QR
    judges = [
        {'email': 'judge1@example.org'},
        {'email': 'judge2@example.org'},
        {'full_name': 'Сидорова  Мария Петровна'},
    ]
    updated = (await client.put(f'{sheet_url}/judges', json={'judges': judges})).json()
    no_email = next(j for j in updated['judges'] if j['email'] is None)
    assert no_email['full_name'] == 'Сидорова Мария Петровна'
    await client.post(f'{sheet_url}/distribute', json={'mode': 'all'})

    # модератор печатает листы судей и управляет оценкой
    async with _other(client) as moderator:
        await login_as(db, moderator, email='moderator@example.org')
        await client.post(
            f'/api/v1/events/{event["id"]}/members', json={'email': 'moderator@example.org', 'role': 'moderator'}
        )
        cards = (await moderator.post(f'{sheet_url}/judge-cards', json={'user_ids': [no_email['user_id']]})).json()
        assert len(cards) == 1 and cards[0]['works'] == 2
        token = cards[0]['login_url'].split('token=')[1]

        async with _other(client) as judge:
            login = await judge.post('/api/v1/auth/magic-link/verify', json={'token': token})
            assert login.status_code == 200 and login.json()['next'] == f'/judging/sheets/{sheet["id"]}'
            assert (await judge.get('/api/v1/auth/me')).json()['judge_mode'] is True
            again = await _other(client).post('/api/v1/auth/magic-link/verify', json={'token': token})
            assert again.status_code == 400

            own = (await judge.get(f'/api/v1/my/sheets/{sheet["id"]}/works')).json()[0]
            url = f'/api/v1/evaluations/{own["evaluation_id"]}/criteria/{criterion}'
            assert (await judge.put(url, json={'level_id': level})).status_code == 200

            assert (await moderator.post(f'{sheet_url}/status', json={'status': 'closed'})).status_code == 200
            assert (await judge.put(url, json={'level_id': level})).status_code == 400
            assert (await judge.get('/api/v1/my/sheets')).json()[0]['editable'] is False

            opened = await moderator.post(f'{sheet_url}/judges/{no_email["user_id"]}/access', json={'open': True})
            assert next(j for j in opened.json()['judges'] if j['user_id'] == no_email['user_id'])['reopened'] is True
            assert (await judge.put(url, json={'level_id': level})).status_code == 200

        # модератор не может менять состав листа — это делает организатор
        assert (await moderator.put(f'{sheet_url}/judges', json={'judges': []})).status_code == 403


async def test_judge_qr_link_expires_in_20_minutes(db, client):
    _, _, sheet = await _prepared_sheet(db, client)
    cards = (await client.post(f'/api/v1/sheets/{sheet["id"]}/judge-cards', json={})).json()
    assert len(cards) == 3
    record = await db.scalar(select(MagicLinkToken).where(MagicLinkToken.purpose == 'judge_qr').limit(1))
    assert record.expires_at - record.created_at <= timedelta(minutes=20, seconds=5)
