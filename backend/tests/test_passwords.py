import pytest

from app.core.security import hash_password, verify_password
from tests.helpers import login_as
from tests.test_applications import _other
from tests.test_evaluation import _prepared_sheet

pytestmark = pytest.mark.usefixtures('redis_clean')


def test_password_hash_roundtrip():
    stored = hash_password('секретный-пароль')
    assert stored.startswith('scrypt$') and verify_password('секретный-пароль', stored)
    assert not verify_password('другой', stored) and not verify_password('x', None)


async def test_admin_creates_user_and_user_logs_in(db, client):
    await login_as(db, client, email='root@example.org', is_superuser=True)
    created = await client.post(
        '/api/v1/people/users',
        json={'email': 'Org@Example.org', 'full_name': 'Петров Иван', 'password': 'pass-1234', 'is_employee': True},
    )
    assert created.status_code == 201, created.text
    assert created.json()['has_password'] is True and created.json()['person']['is_employee'] is True

    async with _other(client) as guest:
        bad = await guest.post('/api/v1/auth/login', json={'email': 'org@example.org', 'password': 'wrong-pass'})
        assert bad.status_code == 400
        ok = await guest.post(
            '/api/v1/auth/login', json={'email': 'org@example.org', 'password': 'pass-1234', 'next': '/events'}
        )
        assert ok.status_code == 200 and ok.json()['next'] == '/events'
        me = (await guest.get('/api/v1/auth/me')).json()
        assert me['has_password'] is True and me['user']['person']['full_name'] == 'Петров Иван'
        # смена своего пароля требует текущий
        assert (await guest.post('/api/v1/auth/password', json={'new_password': 'new-pass-99'})).status_code == 400
        changed = await guest.post(
            '/api/v1/auth/password', json={'current_password': 'pass-1234', 'new_password': 'new-pass-99'}
        )
        assert changed.status_code == 204

    # администратор сбрасывает пароль
    user_id = created.json()['id']
    assert (await client.patch(f'/api/v1/people/users/{user_id}', json={'password': 'reset-pass-1'})).status_code == 200


async def test_password_login_rate_limit(db, client):
    for _ in range(10):
        await client.post('/api/v1/auth/login', json={'email': 'nobody@example.org', 'password': 'x'})
    blocked = await client.post('/api/v1/auth/login', json={'email': 'nobody@example.org', 'password': 'x'})
    assert blocked.status_code == 429


async def test_judges_from_base_with_password(db, client):
    event, _, sheet = await _prepared_sheet(db, client, mode='jury')
    url = f'/api/v1/sheets/{sheet["id"]}'

    found = (await client.get(f'/api/v1/events/{event["id"]}/user-search', params={'q': 'judge1'})).json()
    assert [u['email'] for u in found] == ['judge1@example.org']

    judges = [
        {'user_id': found[0]['id']},
        {'email': 'judge2@example.org'},
        {'email': 'petrov@example.org'},
        {'full_name': 'Сидорова Мария Петровна', 'password': 'judge-pass-1'},
        {'full_name': 'Новиков Олег', 'email': 'novikov@example.org', 'password': 'judge-pass-2'},
    ]
    result = await client.put(f'{url}/judges', json={'judges': judges})
    assert result.status_code == 200, result.text
    by_name = {j['full_name']: j for j in result.json()['judges']}
    assert by_name['Сидорова Мария Петровна']['has_password'] is True
    assert by_name['Новиков Олег']['email'] == 'novikov@example.org'

    # новый судья входит по email и паролю
    async with _other(client) as judge:
        ok = await judge.post('/api/v1/auth/login', json={'email': 'novikov@example.org', 'password': 'judge-pass-2'})
        assert ok.status_code == 200
        assert (await judge.get('/api/v1/auth/me')).json()['judge_mode'] is True

    # организатору нельзя задать пароль пользователю с другими ролями (самому себе как организатору)
    org = (await client.get(f'/api/v1/events/{event["id"]}/user-search', params={'q': 'org@skolkovo'})).json()[0]
    takeover = await client.put(
        f'{url}/judges', json={'judges': [*judges[:3], {'user_id': org['id'], 'password': 'hijack-pass'}]}
    )
    assert takeover.status_code == 400

    # поиск доступен только организаторам и модераторам
    async with _other(client) as outsider:
        await login_as(db, outsider, email='outsider@example.org')
        assert (
            await outsider.get(f'/api/v1/events/{event["id"]}/user-search', params={'q': 'judge'})
        ).status_code == 404
