from datetime import date

import pytest

from app.core.config import settings
from app.modules.auth.service import open_session
from app.modules.people.service import get_user_by_email
from tests.helpers import login_as

pytestmark = pytest.mark.usefixtures('redis_clean')


async def _employee(db, client, email='org@skolkovo.example.org'):
    user = await login_as(db, client, email=email)
    user.person.is_employee = True
    await db.commit()
    return user


async def _create(client, slug='skolstart-2027', type_='project_contest', **extra):
    response = await client.post(
        '/api/v1/events', json={'type': type_, 'title': 'SkolStart 2027', 'slug': slug, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_types_list(db, client):
    await _employee(db, client)
    types = (await client.get('/api/v1/events/types')).json()
    assert {t['id'] for t in types} == {'project_contest', 'conference', 'creative', 'open_event', 'selection'}


async def test_create_from_template(db, client):
    await _employee(db, client)
    event = await _create(client)
    assert event['status'] == 'draft'
    assert event['my_roles'] == ['organizer'] and event['can_manage'] is True
    assert [s['title'] for s in event['stages']] == ['Заочный этап', 'Очная защита']
    assert event['modules']['evaluation'] is True
    assert event['allowed_statuses'] == ['registration', 'running']


async def test_only_staff_creates_events(db, client):
    await login_as(db, client, email='guest@example.org')
    response = await client.post('/api/v1/events', json={'type': 'conference', 'title': 'Тест', 'slug': 'test'})
    assert response.status_code == 403


@pytest.mark.parametrize('slug', ['app', 'Bad_Slug', '-x'])
async def test_slug_validation(db, client, slug):
    await _employee(db, client)
    response = await client.post('/api/v1/events', json={'type': 'conference', 'title': 'Тест', 'slug': slug})
    assert response.status_code == 422


async def test_slug_must_be_unique(db, client):
    await _employee(db, client)
    await _create(client)
    response = await client.post(
        '/api/v1/events', json={'type': 'conference', 'title': 'Тест', 'slug': 'skolstart-2027'}
    )
    assert response.status_code == 400
    assert (await client.get('/api/v1/events/slug-available', params={'slug': 'skolstart-2027'})).json() == {
        'available': False
    }


async def test_update_and_status_flow(db, client):
    await _employee(db, client)
    event = await _create(client)
    url = f'/api/v1/events/{event["id"]}'

    no_date = await client.post(f'{url}/status', json={'status': 'registration'})
    assert no_date.status_code == 400

    bad_dates = await client.patch(url, json={'date_start': '2027-04-18', 'date_end': '2027-03-12'})
    assert bad_dates.status_code == 400

    updated = await client.patch(url, json={'date_start': '2027-03-12', 'date_end': '2027-04-18', 'place': 'Гимназия'})
    assert updated.json()['place'] == 'Гимназия'

    published = await client.post(f'{url}/status', json={'status': 'registration'})
    assert published.json()['status'] == 'registration'
    assert (await client.post(f'{url}/status', json={'status': 'archived'})).status_code == 400
    assert (await client.delete(url)).status_code == 400


async def test_children_crud_and_order(db, client):
    await _employee(db, client)
    event = await _create(client)
    url = f'/api/v1/events/{event["id"]}'

    physics = (await client.post(f'{url}/directions', json={'title': 'Физика'})).json()
    biology = (await client.post(f'{url}/directions', json={'title': 'Биология'})).json()
    assert (
        await client.put(f'{url}/directions/order', json={'ids': [biology['id'], physics['id']]})
    ).status_code == 204
    assert [d['title'] for d in (await client.get(url)).json()['directions']] == ['Биология', 'Физика']

    stage = (await client.get(url)).json()['stages'][0]
    patched = await client.patch(
        f'{url}/stages/{stage["id"]}',
        json={'title': 'Отбор', 'kind': 'remote', 'date_start': '2027-03-01', 'date_end': '2027-03-20'},
    )
    assert patched.json()['title'] == 'Отбор'
    assert (await client.delete(f'{url}/directions/{physics["id"]}')).status_code == 204
    assert len((await client.get(url)).json()['directions']) == 1


async def test_team_and_access(db, client):
    await _employee(db, client)
    event = await _create(client)
    url = f'/api/v1/events/{event["id"]}'

    judge = await client.post(f'{url}/members', json={'email': 'expert@example.org', 'role': 'judge'})
    assert judge.status_code == 201

    members = (await client.get(f'{url}/members')).json()
    assert sorted(m['role'] for m in members) == ['judge', 'organizer']
    organizer = next(m for m in members if m['role'] == 'organizer')
    assert (await client.delete(f'{url}/members/{organizer["id"]}')).status_code == 400

    # судья видит мероприятие, но не меняет его; посторонний не видит
    other = client.__class__(transport=client._transport, base_url=str(client.base_url), headers=client.headers)
    async with other:
        await login_as(db, other, email='stranger@example.org')
        assert (await other.get(url)).status_code == 404
    async with client.__class__(
        transport=client._transport, base_url=str(client.base_url), headers=client.headers
    ) as j:
        judge_user = await get_user_by_email(db, 'expert@example.org')
        access, _ = await open_session(db, judge_user, 'magic_link', None, None)
        await db.commit()
        j.cookies.set(settings.auth.access_cookie, access)
        seen = await j.get(url)
        assert seen.status_code == 200 and seen.json()['my_roles'] == ['judge']
        assert (await j.patch(url, json={'place': 'x'})).status_code == 403
        assert [e['id'] for e in (await j.get('/api/v1/events')).json()] == [event['id']]


async def test_copy_event(db, client):
    await _employee(db, client)
    source = await _create(client)
    await client.post(f'/api/v1/events/{source["id"]}/directions', json={'title': 'Инженерия'})
    copy = await _create(client, slug='skolstart-2028', copy_from_id=source['id'])
    assert [d['title'] for d in copy['directions']] == ['Инженерия']
    assert len(copy['stages']) == 2 and copy['status'] == 'draft'


async def test_public_event(db, client):
    await _employee(db, client)
    event = await _create(client)
    url = f'/api/v1/events/{event["id"]}'
    assert (await client.get('/api/v1/public/events/skolstart-2027')).status_code == 404

    await client.patch(url, json={'date_start': date(2027, 3, 12).isoformat(), 'short_description': 'Конференция'})
    await client.post(f'{url}/status', json={'status': 'registration'})
    public = await client.get('/api/v1/public/events/skolstart-2027')
    assert public.status_code == 200
    body = public.json()
    assert body['title'] == 'SkolStart 2027' and body['registration_open'] is True
    assert 'members' not in body and len(body['stages']) == 2
