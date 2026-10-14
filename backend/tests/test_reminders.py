from datetime import timedelta

import pytest

from app.core.captcha import get_captcha
from app.core.security import now_utc
from app.modules.evaluation.models import Sheet
from app.modules.events.models import Event
from app.modules.reminders.service import run_hourly
from tests.fakes import FakeQueue
from tests.helpers import login_as
from tests.test_applications import SLUG, _open_event, _other, _payload
from tests.test_evaluation import _as, _prepared_sheet

pytestmark = pytest.mark.usefixtures('redis_clean')


def _mails(queue: FakeQueue) -> list[tuple[str, str]]:
    return [(args[0], args[1]) for name, args, _ in queue.jobs if name == 'send_email']


async def test_draft_reminder_before_registration_closes(db, client):
    event = await _open_event(db, client)
    async with _other(client) as applicant:
        await login_as(db, applicant, email='anna@example.org')
        app = (await applicant.post(f'/api/v1/events/{SLUG}/applications')).json()
        await applicant.put(f'/api/v1/applications/{app["id"]}', json=_payload(event))

    queue = FakeQueue()
    assert (await run_hourly(db, queue))['drafts'] == 0  # дата закрытия не задана

    stored = await db.get(Event, event['id'], populate_existing=True)
    stored.registration_closes_at = now_utc() + timedelta(hours=30)
    await db.commit()
    assert (await run_hourly(db, queue))['drafts'] == 1
    assert _mails(queue) == [('anna@example.org', 'Заявка не отправлена: SkolStart')]
    await db.commit()
    assert (await run_hourly(db, queue))['drafts'] == 0  # второй раз не напоминаем


async def test_deadline_reminders_and_auto_close(db, client, queue):
    _, _, sheet = await _prepared_sheet(db, client, mode='jury')
    sheet_url = f'/api/v1/sheets/{sheet["id"]}'
    deadline = (now_utc() + timedelta(hours=5)).isoformat()
    assert (await client.patch(sheet_url, json={'deadline': deadline})).status_code == 200

    jobs = FakeQueue()
    assert (await run_hourly(db, jobs))['judges'] == 2
    assert sorted(to for to, _ in _mails(jobs)) == ['judge1@example.org', 'judge2@example.org']
    await db.commit()
    assert (await run_hourly(db, jobs))['judges'] == 0

    # вручную модератор может напомнить ещё раз
    reminded = (await client.post(f'{sheet_url}/remind')).json()
    assert reminded == {'sent': 2, 'no_email': 0}

    # дедлайн прошёл: судья не может ставить баллы, лист закрывается по расписанию
    stored = await db.get(Sheet, sheet['id'], populate_existing=True)
    stored.deadline = now_utc() - timedelta(minutes=1)
    await db.commit()
    async with await _as(db, client, 'judge1@example.org') as judge:
        mine = (await judge.get('/api/v1/my/sheets')).json()
        assert mine[0]['editable'] is False
    assert (await run_hourly(db, FakeQueue()))['closed_sheets'] == 1
    await db.commit()
    assert (await client.get(sheet_url)).json()['status'] == 'closed'
    reopen = await client.post(f'{sheet_url}/status', json={'status': 'active'})
    assert reopen.status_code == 400 and 'Дедлайн' in reopen.text


class _RejectingCaptcha:
    enabled = True

    async def verify(self, token, ip):
        return token == 'good'


async def test_magic_link_requires_captcha_when_enabled(db, client):
    client._transport.app.dependency_overrides[get_captcha] = lambda: _RejectingCaptcha()
    bad = await client.post('/api/v1/auth/magic-link', json={'email': 'a@example.org'})
    assert bad.status_code == 400
    ok = await client.post('/api/v1/auth/magic-link', json={'email': 'a@example.org', 'captcha_token': 'good'})
    assert ok.status_code == 202
