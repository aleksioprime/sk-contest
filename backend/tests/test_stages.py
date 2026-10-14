from io import BytesIO

import pytest
from openpyxl import load_workbook

from tests.helpers import login_as
from tests.test_applications import SLUG, _open_event, _other, _submitted
from tests.test_evaluation import _as

pytestmark = pytest.mark.usefixtures('redis_clean')


async def _contest(db, client):
    """Три принятые заявки, первый этап с оценённым листом: баллы 4, 2, 0."""
    event = await _open_event(db, client)
    apps = []
    for email in ('anna@example.org', 'boris@example.org', 'vera@example.org'):
        async with _other(client) as applicant:
            await login_as(db, applicant, email=email)
            apps.append(await _submitted(applicant, event))
    for app in apps:
        await client.post(f'/api/v1/applications/{app["id"]}/decision', json={'status': 'accepted'})

    url = f'/api/v1/events/{event["id"]}'
    first, second = event['stages']
    overview = (await client.post(f'{url}/stages/{first["id"]}/admit')).json()
    assert [p['status'] for p in overview['participants']] == ['admitted'] * 3

    scale = (
        await client.post(
            f'{url}/scales',
            json={
                'title': '0–4',
                'levels': [
                    {'title': 'Нет', 'points': 0},
                    {'title': 'Средне', 'points': 2},
                    {'title': 'Отлично', 'points': 4},
                ],
            },
        )
    ).json()
    card = (
        await client.post(
            f'{url}/scorecards',
            json={
                'title': 'Отбор',
                'criteria': [{'title': 'Качество', 'type': 'scale', 'scale_id': scale['id']}],
            },
        )
    ).json()
    sheet = (
        await client.post(
            f'{url}/sheets',
            json={
                'title': 'Заочный отбор',
                'scorecard_id': card['id'],
                'stage_id': first['id'],
            },
        )
    ).json()
    sheet_url = f'/api/v1/sheets/{sheet["id"]}'
    added = (await client.post(f'{sheet_url}/works', json={'source': 'stage'})).json()
    assert len(added['works']) == 3
    await client.put(f'{sheet_url}/judges', json={'judges': [{'email': 'judge1@example.org'}]})
    await client.post(f'{sheet_url}/distribute', json={'mode': 'all'})
    await client.post(f'{sheet_url}/status', json={'status': 'active'})

    criterion = card['criteria'][0]['id']
    levels = [lv['id'] for lv in card['criteria'][0]['scale']['levels']]
    judge = await _as(db, client, 'judge1@example.org')
    async with judge:
        works = (await judge.get(f'/api/v1/my/sheets/{sheet["id"]}/works')).json()
        for work, level in zip(works, reversed(levels), strict=True):
            await judge.put(
                f'/api/v1/evaluations/{work["evaluation_id"]}/criteria/{criterion}', json={'level_id': level}
            )
    return event, first, second


async def test_stage_advancement_schedule_and_results(db, client):
    event, first, second = await _contest(db, client)
    url = f'/api/v1/events/{event["id"]}'

    overview = (await client.get(f'{url}/stages/{first["id"]}')).json()
    by_number = {p['number']: p for p in overview['participants']}
    assert [by_number[n]['score'] for n in (1, 2, 3)] == ['4.00', '2.00', '0.00']
    assert [by_number[n]['rank'] for n in (1, 2, 3)] == [1, 2, 3]
    assert {p['status'] for p in overview['participants']} == {'evaluated'}

    rule = (await client.put(f'{url}/stages/{first["id"]}/rule', json={'type': 'top_n', 'n': 2})).json()
    proposals = {p['number']: p['proposal'] for p in rule['participants']}
    assert proposals == {1: 'passed', 2: 'passed', 3: 'not_passed'}

    decisions = {p['id']: p['proposal'] for p in rule['participants']}
    result = (await client.post(f'{url}/stages/{first["id"]}/advance', json={'decisions': decisions})).json()
    assert result == {'passed': 2, 'not_passed': 1, 'admitted_next': 2}

    final = (await client.get(f'{url}/stages/{second["id"]}')).json()
    assert sorted(p['number'] for p in final['participants']) == [1, 2]

    slot = (
        await client.post(
            f'{url}/stages/{second["id"]}/slots',
            json={
                'title': 'Секция 1',
                'room': '301',
                'starts_at': '2027-04-18T10:00:00+03:00',
                'ends_at': '2027-04-18T12:00:00+03:00',
            },
        )
    ).json()
    scheduled = await client.patch(
        f'/api/v1/stage-participants/{final["participants"][0]["id"]}', json={'slot_id': slot['id']}
    )
    assert scheduled.json()['status'] == 'scheduled'
    program = await client.get(f'{url}/stages/{second["id"]}/program.xlsx')
    sheet = load_workbook(BytesIO(program.content)).active
    assert sheet['B4'].value == '301' and sheet['E4'].value == 'Умная теплица'

    # итоги по первому этапу: 1 победитель, 3 призовых места
    await client.put(
        f'{url}/awards',
        json={
            'winners': 1,
            'prize_places': 2,
            'stage_id': first['id'],
            'signatory': 'И. И. Иванов',
            'signatory_title': 'Председатель жюри',
        },
    )
    results = (await client.get(f'{url}/results')).json()
    assert [(r['rank'], r['award']) for r in results['rows']] == [(1, 'winner'), (2, 'prize'), (3, 'participant')]
    assert (await client.get(f'/api/v1/public/events/{SLUG}/results')).status_code == 404

    published = (await client.post(f'{url}/results/publish')).json()
    assert published['published_at'] is not None
    public = (await client.get(f'/api/v1/public/events/{SLUG}/results')).json()
    assert [w['award'] for w in public[0]['winners']] == ['winner', 'prize']

    pdf = await client.get(f'{url}/diplomas.pdf')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')

    winner_app = results['rows'][0]['application_id']
    async with await _as(db, client, 'anna@example.org') as anna:
        mine = (await anna.get('/api/v1/my/results')).json()
        assert mine == [
            {'application_id': winner_app, 'rank': 1, 'award': 'winner', 'score': '4.00', 'nominations': []}
        ]
        diploma = await anna.get(f'/api/v1/applications/{winner_app}/diploma.pdf')
        assert diploma.status_code == 200 and diploma.content.startswith(b'%PDF')
        assert (await anna.get(f'{url}/results')).status_code == 404


async def test_threshold_rule_and_permissions(db, client):
    event, first, _ = await _contest(db, client)
    url = f'/api/v1/events/{event["id"]}'
    rule = (await client.put(f'{url}/stages/{first["id"]}/rule', json={'type': 'threshold', 'threshold': 2})).json()
    assert sorted(p['proposal'] for p in rule['participants']) == ['not_passed', 'passed', 'passed']
    bad = await client.post(f'{url}/stages/{first["id"]}/advance', json={'decisions': {'1': 'maybe'}})
    assert bad.status_code == 400
    async with await _as(db, client, 'judge1@example.org') as judge:
        assert (await judge.get(f'{url}/stages/{first["id"]}')).status_code == 404
        assert (await judge.post(f'{url}/results/publish')).status_code == 403


async def test_overall_ranking_combined_sheets_and_nominations(db, client):
    event, first, _ = await _contest(db, client)
    url = f'/api/v1/events/{event["id"]}'
    # общий рейтинг этапа и объединение листов суммой
    overview = (
        await client.put(
            f'{url}/stages/{first["id"]}/rule', json={'type': 'manual', 'rank_scope': 'overall', 'score_combine': 'sum'}
        )
    ).json()
    assert overview['rule']['rank_scope'] == 'overall' and overview['rule']['score_combine'] == 'sum'

    results = (await client.get(f'{url}/results')).json()
    third = next(r for r in results['rows'] if r['rank'] == 3)
    awards = {
        'rank_scope': 'overall',
        'winners': 1,
        'prize_places': 2,
        'stage_id': first['id'],
        'nominations': [{'id': 'n1', 'title': 'Лучший дизайн', 'application_ids': [third['application_id']]}],
    }
    assert (await client.put(f'{url}/awards', json=awards)).status_code == 200
    results = (await client.get(f'{url}/results')).json()
    nominated = next(r for r in results['rows'] if r['application_id'] == third['application_id'])
    assert nominated['nominations'] == ['Лучший дизайн'] and nominated['award'] == 'participant'

    await client.post(f'{url}/results/publish')
    public = (await client.get(f'/api/v1/public/events/{SLUG}/results')).json()
    assert [g['direction'] for g in public] == ['', 'Номинация «Лучший дизайн»']
    assert public[1]['nomination'] is True and public[1]['winners'][0]['award'] == 'nomination'

    # заявка чужого мероприятия в номинации не принимается
    bad = {**awards, 'nominations': [{'id': 'n2', 'title': 'X', 'application_ids': [1]}]}
    assert (await client.put(f'{url}/awards', json=bad)).status_code == 400
