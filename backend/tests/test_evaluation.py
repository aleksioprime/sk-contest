import pytest

from app.core.config import settings
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
                'emails': ['judge1@example.org', 'judge2@example.org', 'petrov@example.org'],
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

    removal = await client.put(f'/api/v1/sheets/{sheet["id"]}/judges', json={'emails': ['judge2@example.org']})
    assert removal.status_code == 400
    forced = await client.put(
        f'/api/v1/sheets/{sheet["id"]}/judges', json={'emails': ['judge2@example.org'], 'force': True}
    )
    assert [j['email'] for j in forced.json()['judges']] == ['judge2@example.org']


async def test_strangers_cannot_manage_sheets(db, client):
    event, _, sheet = await _prepared_sheet(db, client)
    async with _other(client) as stranger:
        await login_as(db, stranger, email='stranger@example.org')
        assert (await stranger.get(f'/api/v1/sheets/{sheet["id"]}')).status_code == 404
        assert (await stranger.get(f'/api/v1/events/{event["id"]}/scorecards')).status_code == 404
        assert (await stranger.get(f'/api/v1/my/sheets/{sheet["id"]}/works')).status_code == 404
