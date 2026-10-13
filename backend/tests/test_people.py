import uuid

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.people.models import Department, Person, StudyClass, SyncRun
from app.modules.people.service import apply_directory
from app.modules.people.sync import run_directory_sync
from tests.fakes import STUDENT_ID, TEACHER_ID, directory_payload
from tests.helpers import login_as


async def _person(db, skolstream_id):
    return await db.scalar(select(Person).where(Person.skolstream_id == uuid.UUID(skolstream_id)))


async def test_full_directory_sync_creates_and_deactivates(db):
    stats = await apply_directory(db, directory_payload(), full=True)
    await db.commit()
    assert stats == {'academic_years': 1, 'classes': 1, 'departments': 1, 'persons': 2, 'deactivated': 0}

    teacher = await _person(db, TEACHER_ID)
    assert teacher.is_employee and [d.name for d in teacher.departments] == ['Кафедра естественных наук']
    student = await _person(db, STUDENT_ID)
    assert student.study_class.name == '9А'
    assert student.study_class.academic_year.name == '2026/2027'

    without_teacher = directory_payload(users=[directory_payload()['users'][1]])
    stats = await apply_directory(db, without_teacher, full=True)
    await db.commit()
    assert stats['deactivated'] == 1
    db.expire_all()
    assert (await _person(db, TEACHER_ID)).is_active is False
    assert (await _person(db, STUDENT_ID)).is_active is True


async def test_incremental_sync_keeps_missing_people(db):
    await apply_directory(db, directory_payload(), full=True)
    await apply_directory(db, directory_payload(users=[]), full=False)
    await db.commit()
    assert (await _person(db, TEACHER_ID)).is_active is True


async def test_sync_does_not_touch_external_people(db):
    db.add(Person(email='guest@example.org', last_name='Гостев'))
    await db.commit()
    await apply_directory(db, directory_payload(users=[]), full=True)
    await db.commit()
    guest = await db.scalar(select(Person).where(Person.email == 'guest@example.org'))
    assert guest.is_active is True


async def test_run_directory_sync_records_result(db, skolstream):
    run = SyncRun(mode='full')
    db.add(run)
    await db.commit()
    run_id = run.id
    stats = await run_directory_sync(skolstream, run_id)
    assert stats['persons'] == 2
    db.expire_all()
    saved = await db.get(SyncRun, run_id)
    assert saved.status == 'success' and saved.finished_at is not None
    assert await db.scalar(select(Department.name)) == 'Кафедра естественных наук'
    assert await db.scalar(select(StudyClass.name)) == '9А'


async def test_people_endpoints_require_admin(db, client):
    assert (await client.get('/api/v1/people/persons')).status_code == 401
    await login_as(db, client, email='user@skolkovo.example.org')
    assert (await client.get('/api/v1/people/persons')).status_code == 403


async def test_admin_lists_and_filters_persons(db, client):
    await apply_directory(db, directory_payload(), full=True)
    await db.commit()
    await login_as(db, client, is_superuser=True)

    students = await client.get('/api/v1/people/persons', params={'kind': 'student'})
    assert [p['full_name'] for p in students.json()['items']] == ['Иванова Анна']

    found = await client.get('/api/v1/people/persons', params={'search': 'петр'})
    assert found.json()['total'] == 1
    assert found.json()['items'][0]['departments'][0]['name'] == 'Кафедра естественных наук'


async def test_admin_cannot_demote_self(db, client):
    admin = await login_as(db, client, is_superuser=True)
    response = await client.patch(f'/api/v1/people/users/{admin.id}', json={'is_superuser': False})
    assert response.status_code == 400


async def test_admin_grants_rights(db, client):
    await login_as(db, client, is_superuser=True)
    other = await login_as(db, client.__class__(), email='teacher@skolkovo.example.org', last_name='Петров')
    response = await client.patch(f'/api/v1/people/users/{other.id}', json={'is_superuser': True})
    assert response.status_code == 200
    assert response.json()['is_superuser'] is True


@pytest.mark.parametrize('token, expected', [('', 409), ('secret', 202)])
async def test_start_sync(db, client, queue, monkeypatch, token, expected):
    monkeypatch.setattr(settings.skolstream, 'directory_token', token)
    await login_as(db, client, is_superuser=True)
    response = await client.post('/api/v1/people/sync', json={'mode': 'full'})
    assert response.status_code == expected
    if expected == 202:
        assert queue.jobs == [('sync_directory', (response.json()['id'],), {})]
        again = await client.post('/api/v1/people/sync', json={'mode': 'full'})
        assert again.status_code == 409
