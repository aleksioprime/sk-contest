from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.core.deps import CurrentUser, Db
from app.core.security import now_utc
from app.modules.applications.models import Application
from app.modules.audit.service import record
from app.modules.events.models import Event, Stage
from app.modules.events.permissions import ensure_manage, ensure_view, roles_of
from app.modules.events.service import get_by_slug, get_event
from app.modules.people.models import User
from app.modules.stages import service
from app.modules.stages.documents import diplomas_pdf, program_xlsx
from app.modules.stages.models import DefenseSlot, StageParticipation
from app.modules.stages.schemas import (
    AdvanceApply,
    Awards,
    EventResults,
    ParticipantOut,
    ParticipantUpdate,
    PublicDirectionResults,
    PublicWinner,
    ResultRow,
    SlotIn,
    SlotOut,
    StageOverview,
    StageRule,
)

router = APIRouter(prefix='/v1', tags=['stages'])
public_router = APIRouter(prefix='/v1/public/events', tags=['public'])

VIEW_ROLES = {'organizer', 'moderator', 'observer'}


def _bad(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


async def _event(db, event_id: int, user: User, manage: bool = True) -> Event:
    event = await get_event(db, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    ensure_view(user, event)
    if manage:
        ensure_manage(user, event)
    elif not (user.is_superuser or VIEW_ROLES & set(roles_of(user, event))):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    return event


async def _stage(db, event_id: int, stage_id: int, user: User, manage: bool = True) -> tuple[Event, Stage]:
    event = await _event(db, event_id, user, manage)
    stage = next((s for s in event.stages if s.id == stage_id), None)
    if stage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Этап не найден')
    return event, stage


def _participant(p: StageParticipation, proposal: str | None = None) -> ParticipantOut:
    app = p.application
    return ParticipantOut(
        id=p.id,
        application_id=app.id,
        number=app.number,
        title=app.title,
        direction=app.direction.title if app.direction else '',
        direction_id=app.direction_id,
        participants=[m.full_name for m in app.members if m.role == 'participant'],
        status=p.status,
        score=p.score,
        rank=p.rank,
        slot_id=p.slot_id,
        slot_order=p.slot_order,
        note=p.note,
        proposal=proposal,
    )


async def _overview(db, event: Event, stage: Stage, with_proposal: bool = True) -> StageOverview:
    items = await service.refresh(db, event, stage)
    rule = stage.advance_rule or {'type': 'manual'}
    proposals = service.proposal(items, rule) if with_proposal else {}
    slots = list(
        await db.scalars(select(DefenseSlot).where(DefenseSlot.stage_id == stage.id).order_by(DefenseSlot.starts_at))
    )
    counts = {}
    for p in items:
        if p.slot_id:
            counts[p.slot_id] = counts.get(p.slot_id, 0) + 1
    following = service.next_stage(event, stage)
    return StageOverview(
        stage_id=stage.id,
        title=stage.title,
        rule=StageRule(**rule),
        has_next=following is not None,
        next_title=following.title if following else None,
        participants=[_participant(p, proposals.get(p.id)) for p in items],
        slots=[
            SlotOut(
                id=s.id,
                title=s.title,
                room=s.room,
                starts_at=s.starts_at,
                ends_at=s.ends_at,
                participants=counts.get(s.id, 0),
            )
            for s in slots
        ],
    )


# --- Этапы -----------------------------------------------------------------------------------


@router.get('/events/{event_id}/stages/{stage_id}', response_model=StageOverview, summary='Участники этапа')
async def stage_overview(event_id: int, stage_id: int, db: Db, user: CurrentUser):
    event, stage = await _stage(db, event_id, stage_id, user, manage=False)
    result = await _overview(db, event, stage)
    await db.commit()
    return result


@router.post('/events/{event_id}/stages/{stage_id}/admit', response_model=StageOverview, summary='Допустить на этап')
async def admit(event_id: int, stage_id: int, db: Db, user: CurrentUser):
    event, stage = await _stage(db, event_id, stage_id, user)
    await service.admit(db, user, event, stage)
    result = await _overview(db, event, stage)
    await db.commit()
    return result


@router.put('/events/{event_id}/stages/{stage_id}/rule', response_model=StageOverview, summary='Правило перехода')
async def set_rule(event_id: int, stage_id: int, payload: StageRule, db: Db, user: CurrentUser):
    event, stage = await _stage(db, event_id, stage_id, user)
    try:
        stage.advance_rule = service.validate_rule(payload.model_dump(mode='json'))
    except service.StageError as exc:
        raise _bad(exc) from exc
    result = await _overview(db, event, stage)
    await db.commit()
    return result


@router.post('/events/{event_id}/stages/{stage_id}/advance', summary='Применить решения о переходе')
async def advance(event_id: int, stage_id: int, payload: AdvanceApply, db: Db, user: CurrentUser) -> dict:
    event, stage = await _stage(db, event_id, stage_id, user)
    try:
        result = await service.apply_decisions(db, user, event, stage, payload.decisions)
    except service.StageError as exc:
        raise _bad(exc) from exc
    await db.commit()
    return result


@router.patch('/stage-participants/{participant_id}', response_model=ParticipantOut, summary='Изменить участника этапа')
async def update_participant(participant_id: int, payload: ParticipantUpdate, db: Db, user: CurrentUser):
    item = await db.get(StageParticipation, participant_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Участник не найден')
    await _event(db, item.application.event_id, user)
    changes = payload.model_dump(exclude_unset=True)
    if changes.pop('clear_slot', False):
        item.slot_id = None
        if item.status == 'scheduled':
            item.status = 'admitted'
    if 'slot_id' in changes and changes['slot_id'] is not None:
        slot = await db.get(DefenseSlot, changes['slot_id'])
        if slot is None or slot.stage_id != item.stage_id:
            raise _bad(service.StageError('Слот не найден на этом этапе'))
        if item.status == 'admitted':
            item.status = 'scheduled'
    for field, value in changes.items():
        if value is not None or field == 'note':
            setattr(item, field, value)
    record(
        db,
        'stage.participant',
        'stage',
        item.stage_id,
        user.id,
        participant=item.id,
        **{k: str(v) for k, v in changes.items()},
    )
    await db.commit()
    await db.refresh(item)
    return _participant(item)


# --- Слоты защит -----------------------------------------------------------------------------


@router.post(
    '/events/{event_id}/stages/{stage_id}/slots', response_model=SlotOut, status_code=201, summary='Добавить слот'
)
async def add_slot(event_id: int, stage_id: int, payload: SlotIn, db: Db, user: CurrentUser):
    await _stage(db, event_id, stage_id, user)
    slot = DefenseSlot(stage_id=stage_id, **payload.model_dump())
    db.add(slot)
    await db.commit()
    return SlotOut(id=slot.id, **payload.model_dump())


@router.put('/slots/{slot_id}', response_model=SlotOut, summary='Изменить слот')
async def update_slot(slot_id: int, payload: SlotIn, db: Db, user: CurrentUser):
    slot = await db.get(DefenseSlot, slot_id)
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Слот не найден')
    stage = await db.get(Stage, slot.stage_id)
    await _event(db, stage.event_id, user)
    for field, value in payload.model_dump().items():
        setattr(slot, field, value)
    await db.commit()
    return SlotOut(id=slot.id, **payload.model_dump())


@router.delete('/slots/{slot_id}', status_code=204, summary='Удалить слот')
async def delete_slot(slot_id: int, db: Db, user: CurrentUser) -> Response:
    slot = await db.get(DefenseSlot, slot_id)
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Слот не найден')
    stage = await db.get(Stage, slot.stage_id)
    await _event(db, stage.event_id, user)
    for item in await db.scalars(select(StageParticipation).where(StageParticipation.slot_id == slot.id)):
        item.slot_id = None
        if item.status == 'scheduled':
            item.status = 'admitted'
    await db.delete(slot)
    await db.commit()
    return Response(status_code=204)


@router.get('/events/{event_id}/stages/{stage_id}/program.xlsx', summary='Программа защит в Excel')
async def program(event_id: int, stage_id: int, db: Db, user: CurrentUser) -> Response:
    event, stage = await _stage(db, event_id, stage_id, user, manage=False)
    items = await service.participations(db, stage.id)
    slots = list(
        await db.scalars(select(DefenseSlot).where(DefenseSlot.stage_id == stage.id).order_by(DefenseSlot.starts_at))
    )
    data = []
    for slot in slots:
        in_slot = sorted((p for p in items if p.slot_id == slot.id), key=lambda p: (p.slot_order, p.application.number))
        data.append(
            {
                'starts_at': slot.starts_at,
                'ends_at': slot.ends_at,
                'room': slot.room,
                'title': slot.title,
                'items': [
                    {
                        'number': p.application.number,
                        'title': p.application.title,
                        'participants': [m.full_name for m in p.application.members if m.role == 'participant'],
                        'direction': p.application.direction.title if p.application.direction else '',
                    }
                    for p in in_slot
                ],
            }
        )
    filename = quote(f'Программа — {event.title} — {stage.title}.xlsx')
    return Response(
        program_xlsx(stage.title, data),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{filename}"},
    )


# --- Итоги -----------------------------------------------------------------------------------


def _row(item: dict) -> ResultRow:
    app = item['application']
    return ResultRow(
        application_id=app.id,
        number=app.number,
        title=app.title,
        direction=app.direction.title if app.direction else '',
        participants=[m.full_name for m in app.members if m.role == 'participant'],
        score=item['score'],
        rank=item['rank'],
        award=item['award'],
    )


@router.get('/events/{event_id}/results', response_model=EventResults, summary='Итоговый рейтинг')
async def event_results(event_id: int, db: Db, user: CurrentUser):
    event = await _event(db, event_id, user, manage=False)
    rows = await service.results(db, event)
    await db.commit()
    return EventResults(
        published_at=event.results_published_at,
        stage_id=rows[0]['stage_id'] if rows else None,
        awards=Awards(**(event.awards or {})),
        rows=[_row(r) for r in rows],
    )


@router.put('/events/{event_id}/awards', response_model=Awards, summary='Награды и оформление дипломов')
async def set_awards(event_id: int, payload: Awards, db: Db, user: CurrentUser):
    event = await _event(db, event_id, user)
    if payload.stage_id and payload.stage_id not in {s.id for s in event.stages}:
        raise _bad(service.StageError('Этап не найден'))
    event.awards = payload.model_dump()
    await db.commit()
    return payload


@router.post('/events/{event_id}/results/publish', response_model=EventResults, summary='Опубликовать или скрыть итоги')
async def publish(event_id: int, db: Db, user: CurrentUser, published: bool = True):
    event = await _event(db, event_id, user)
    event.results_published_at = now_utc() if published else None
    record(db, 'event.results', 'event', event.id, user.id, published=published)
    await db.commit()
    return await event_results(event_id, db, user)


def _diploma_entries(rows: list[dict]) -> list[dict]:
    entries = []
    for row in rows:
        app = row['application']
        for member in (m for m in app.members if m.role == 'participant'):
            entries.append(
                {
                    'name': member.full_name,
                    'award': row['award'],
                    'rank': row['rank'],
                    'direction': app.direction.title if app.direction else '',
                    'work_title': app.title,
                }
            )
    return entries


def _pdf(content: bytes, name: str) -> Response:
    return Response(
        content,
        media_type='application/pdf',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(name)}"},
    )


@router.get('/events/{event_id}/diplomas.pdf', summary='Дипломы всех участников')
async def all_diplomas(event_id: int, db: Db, user: CurrentUser) -> Response:
    event = await _event(db, event_id, user, manage=False)
    rows = await service.results(db, event)
    if not rows:
        raise _bad(service.StageError('Нет участников для дипломов'))
    return _pdf(diplomas_pdf(_diploma_entries(rows), event.title, event.awards or {}), f'Дипломы — {event.title}.pdf')


@router.get('/applications/{application_id}/diploma.pdf', summary='Диплом по заявке')
async def my_diploma(application_id: int, db: Db, user: CurrentUser) -> Response:
    app = await db.get(Application, application_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Заявка не найдена')
    event = await get_event(db, app.event_id)
    staff = user.is_superuser or VIEW_ROLES & set(roles_of(user, event))
    if not staff and (app.user_id != user.id or event.results_published_at is None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Диплом пока недоступен')
    row = next((r for r in await service.results(db, event) if r['application'].id == app.id), None)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Заявка не участвует в итогах')
    return _pdf(diplomas_pdf(_diploma_entries([row]), event.title, event.awards or {}), f'Диплом — {app.title}.pdf')


@router.get('/my/results', summary='Мои результаты по опубликованным итогам')
async def my_results(db: Db, user: CurrentUser) -> list[dict]:
    apps = (await db.scalars(select(Application).where(Application.user_id == user.id))).unique()
    by_event: dict[int, list[Application]] = {}
    for app in apps:
        by_event.setdefault(app.event_id, []).append(app)
    result = []
    for event_id, own in by_event.items():
        event = await get_event(db, event_id)
        if event.results_published_at is None:
            continue
        rows = {r['application'].id: r for r in await service.results(db, event)}
        for app in own:
            if app.id in rows:
                row = rows[app.id]
                result.append(
                    {'application_id': app.id, 'rank': row['rank'], 'award': row['award'], 'score': row['score']}
                )
    return result


@public_router.get('/{slug}/results', response_model=list[PublicDirectionResults], summary='Опубликованные итоги')
async def public_results(slug: str, db: Db):
    event = await get_by_slug(db, slug)
    if event is None or event.results_published_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Итоги не опубликованы')
    groups: dict[str, list[PublicWinner]] = {}
    for row in await service.results(db, event):
        if row['award'] == 'participant':
            continue
        app = row['application']
        groups.setdefault(app.direction.title if app.direction else '', []).append(
            PublicWinner(
                rank=row['rank'],
                award=row['award'],
                title=app.title,
                participants=[m.full_name for m in app.members if m.role == 'participant'],
            )
        )
    return [PublicDirectionResults(direction=d, winners=w) for d, w in groups.items()]
