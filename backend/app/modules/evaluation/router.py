from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response, status
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, Db
from app.core.security import TokenError, read_state, sign_state
from app.modules.applications.service import event_form
from app.modules.audit.service import record
from app.modules.auth.service import issue_judge_login
from app.modules.evaluation import service
from app.modules.evaluation.models import Evaluation, Scale, Scorecard, Sheet, SheetJudge, SheetWork
from app.modules.evaluation.schemas import (
    AddWorks,
    AnonymousStart,
    AnonymousStarted,
    CriterionValue,
    Distribute,
    EvaluationBundle,
    EvaluationComment,
    ItemOut,
    JudgeAccess,
    JudgeCard,
    JudgeCardsRequest,
    JudgeOut,
    JudgeWork,
    MySheet,
    PublicWork,
    ScaleIn,
    ScaleOut,
    ScorecardIn,
    ScorecardOut,
    SetJudges,
    SheetCreate,
    SheetListItem,
    SheetOut,
    SheetStatus,
    SheetUpdate,
    WorkInfo,
    WorkOut,
)
from app.modules.events.models import Event
from app.modules.events.permissions import ensure_manage, ensure_view, roles_of
from app.modules.events.service import get_event
from app.modules.people.models import User

router = APIRouter(prefix='/v1', tags=['evaluation'])
public_router = APIRouter(prefix='/v1/public/evaluate', tags=['public'])

ANON_TTL_MINUTES = 60 * 24 * 60  # анонимная оценка доступна с устройства два месяца


def _bad(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


def _not_found(what: str = 'Не найдено') -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, what)


LEVELS = {
    'manage': {'organizer'},
    'staff': {'organizer', 'moderator'},  # закрыть оценку, открыть судье, распечатать листы судей
    'view': {'organizer', 'moderator', 'observer'},
}


async def _event(db, event_id: int, user: User, level: str = 'manage') -> Event:
    event = await get_event(db, event_id)
    if event is None:
        raise _not_found('Мероприятие не найдено')
    ensure_view(user, event)
    if user.is_superuser or LEVELS[level] & set(roles_of(user, event)):
        return event
    if level == 'manage':
        ensure_manage(user, event)
    raise _not_found('Мероприятие не найдено')


async def _sheet(db, sheet_id: int, user: User, level: str = 'manage') -> tuple[Sheet, Event]:
    sheet = await db.get(Sheet, sheet_id, populate_existing=True)
    if sheet is None:
        raise _not_found('Лист не найден')
    return sheet, await _event(db, sheet.event_id, user, level)


def _scorecard_out(scorecard: Scorecard, in_use: bool = False) -> ScorecardOut:
    result = ScorecardOut.model_validate(scorecard)
    result.max_score = service.max_score(scorecard)
    result.in_use = in_use
    return result


def _person_name(user: User) -> str:
    return user.person.full_name if user.person and user.person.full_name else user.email


def _sheet_out(sheet: Sheet) -> SheetOut:
    judges = []
    for judge in sheet.judges:
        own = [e for w in sheet.works for e in w.evaluations if e.judge_id == judge.user_id]
        judges.append(
            JudgeOut(
                user_id=judge.user_id,
                email=judge.user.email if service.has_real_email(judge.user) else None,
                full_name=_person_name(judge.user),
                total=len(own),
                scored=sum(e.is_scored for e in own),
                reopened=judge.reopened,
            )
        )
    works = []
    for work in sheet.works:
        app = work.application
        jury = [e for e in work.evaluations if not e.is_anonymous]
        works.append(
            WorkOut(
                id=work.id,
                application_id=app.id,
                number=app.number,
                title=app.title,
                direction=app.direction.title if app.direction else '',
                participants=[m.full_name for m in app.members if m.role == 'participant'],
                public_token=work.public_token,
                score=work.score,
                rank=work.rank,
                is_scored=work.is_scored,
                evaluations_total=len(jury),
                evaluations_scored=sum(e.is_scored for e in jury),
                anonymous_count=sum(e.is_anonymous and e.is_scored for e in work.evaluations),
            )
        )
    return SheetOut(
        id=sheet.id,
        event_id=sheet.event_id,
        stage_id=sheet.stage_id,
        scorecard_id=sheet.scorecard_id,
        scorecard_title=sheet.scorecard.title,
        title=sheet.title,
        status=sheet.status,
        mode=sheet.mode,
        aggregate=sheet.aggregate,
        rank_method=sheet.rank_method,
        include_anonymous=sheet.include_anonymous,
        deadline=sheet.deadline,
        judges=judges,
        works=works,
    )


def _work_info(work: SheetWork, full: bool) -> WorkInfo:
    app = work.application
    info = WorkInfo(
        number=app.number,
        title=app.title,
        direction=app.direction.title if app.direction else '',
        participation_form=app.participation_form.title if app.participation_form else '',
        participants=[m.full_name for m in app.members if m.role == 'participant'],
        supervisors=[m.full_name for m in app.members if m.role == 'supervisor'] if full else [],
    )
    if full:
        fields = [f for f in event_form(app.event).fields if f.type != 'file']
        info.answers = [
            {'label': f.label, 'value': app.answers[f.key]} for f in fields if app.answers.get(f.key) not in (None, '')
        ]
        info.files = [{'name': f.file.original_name, 'url': f'/api/v1/files/{f.file.id}'} for f in app.files]
    return info


def _bundle(sheet: Sheet, evaluation: Evaluation, editable: bool, full: bool, siblings=None) -> EvaluationBundle:
    work = service.work_of(sheet, evaluation)
    ids = [e.id for e in siblings or []]
    position = ids.index(evaluation.id) if evaluation.id in ids else -1
    return EvaluationBundle(
        evaluation_id=evaluation.id,
        sheet_id=sheet.id,
        sheet_title=sheet.title,
        event_title=work.application.event.title,
        editable=editable,
        work=_work_info(work, full),
        scorecard=_scorecard_out(sheet.scorecard),
        items=[
            ItemOut(
                criterion_id=i.criterion_id,
                level_id=i.level_id,
                option_ids=[o.option_id for o in i.options],
                score=i.score,
                comment=i.comment,
            )
            for i in evaluation.items
        ],
        score=evaluation.score,
        is_scored=evaluation.is_scored,
        comment=evaluation.comment,
        anonymous_name=evaluation.anonymous_name,
        prev_id=ids[position - 1] if position > 0 else None,
        next_id=ids[position + 1] if 0 <= position < len(ids) - 1 else None,
    )


# --- Шкалы -----------------------------------------------------------------------------------


@router.get('/events/{event_id}/scales', response_model=list[ScaleOut], summary='Шкалы мероприятия')
async def list_scales(event_id: int, db: Db, user: CurrentUser):
    await _event(db, event_id, user)
    return list(await db.scalars(select(Scale).where(Scale.event_id == event_id).order_by(Scale.created_at)))


@router.post('/events/{event_id}/scales', response_model=ScaleOut, status_code=201, summary='Создать шкалу')
async def create_scale(event_id: int, payload: ScaleIn, db: Db, user: CurrentUser):
    await _event(db, event_id, user)
    scale = Scale(event_id=event_id, levels=[])
    service.fill_scale(scale, payload)
    db.add(scale)
    await db.commit()
    return await db.get(Scale, scale.id, populate_existing=True)


@router.put('/scales/{scale_id}', response_model=ScaleOut, summary='Изменить шкалу')
async def update_scale(scale_id: int, payload: ScaleIn, db: Db, user: CurrentUser):
    scale = await db.get(Scale, scale_id)
    if scale is None:
        raise _not_found('Шкала не найдена')
    await _event(db, scale.event_id, user)
    if await service.scale_in_use(db, scale_id) and len(payload.levels) != len(scale.levels):
        raise _bad('Шкала используется в критериях: можно менять названия и баллы, но не число уровней')
    if await service.scale_in_use(db, scale_id):
        scale.title = payload.title
        for level, data in zip(scale.levels, payload.levels, strict=True):
            level.title, level.points = data.title, data.points
    else:
        service.fill_scale(scale, payload)
    await db.commit()
    return await db.get(Scale, scale.id, populate_existing=True)


@router.delete('/scales/{scale_id}', status_code=204, summary='Удалить шкалу')
async def delete_scale(scale_id: int, db: Db, user: CurrentUser) -> Response:
    scale = await db.get(Scale, scale_id)
    if scale is None:
        raise _not_found('Шкала не найдена')
    await _event(db, scale.event_id, user)
    if await service.scale_in_use(db, scale_id):
        raise _bad('Шкала используется в критериях')
    await db.delete(scale)
    await db.commit()
    return Response(status_code=204)


# --- Таблицы оценок --------------------------------------------------------------------------


@router.get('/events/{event_id}/scorecards', response_model=list[ScorecardOut], summary='Таблицы оценок')
async def list_scorecards(event_id: int, db: Db, user: CurrentUser):
    await _event(db, event_id, user)
    rows = await db.scalars(select(Scorecard).where(Scorecard.event_id == event_id).order_by(Scorecard.created_at))
    return [_scorecard_out(s, await service.scorecard_in_use(db, s.id)) for s in rows.unique()]


@router.post('/events/{event_id}/scorecards', response_model=ScorecardOut, status_code=201, summary='Создать таблицу')
async def create_scorecard(event_id: int, payload: ScorecardIn, db: Db, user: CurrentUser):
    await _event(db, event_id, user)
    scorecard = Scorecard(event_id=event_id, categories=[], criteria=[])
    db.add(scorecard)
    try:
        await service.fill_scorecard(db, scorecard, event_id, payload)
    except service.EvaluationError as exc:
        raise _bad(exc) from exc
    await db.commit()
    return _scorecard_out(await db.get(Scorecard, scorecard.id, populate_existing=True))


@router.put('/scorecards/{scorecard_id}', response_model=ScorecardOut, summary='Изменить таблицу')
async def update_scorecard(scorecard_id: int, payload: ScorecardIn, db: Db, user: CurrentUser):
    scorecard = await db.get(Scorecard, scorecard_id)
    if scorecard is None:
        raise _not_found('Таблица не найдена')
    await _event(db, scorecard.event_id, user)
    if await service.scorecard_in_use(db, scorecard_id):
        raise _bad('По этой таблице уже ставят оценки. Сделайте копию и измените её.')
    try:
        await service.fill_scorecard(db, scorecard, scorecard.event_id, payload)
    except service.EvaluationError as exc:
        raise _bad(exc) from exc
    await db.commit()
    return _scorecard_out(await db.get(Scorecard, scorecard.id, populate_existing=True))


@router.post('/scorecards/{scorecard_id}/copy', response_model=ScorecardOut, status_code=201, summary='Копия таблицы')
async def copy_scorecard(scorecard_id: int, db: Db, user: CurrentUser):
    source = await db.get(Scorecard, scorecard_id)
    if source is None:
        raise _not_found('Таблица не найдена')
    await _event(db, source.event_id, user)
    category_index = {c.id: i for i, c in enumerate(source.categories)}
    payload = ScorecardIn(
        title=f'{source.title} (копия)',
        categories=[c.title for c in source.categories],
        criteria=[
            {
                'title': c.title,
                'description': c.description,
                'type': c.type,
                'scale_id': c.scale_id,
                'weight': c.weight,
                'category': category_index.get(c.category_id),
                'options': [{'title': o.title, 'points': o.points, 'is_exclusive': o.is_exclusive} for o in c.options],
            }
            for c in source.criteria
        ],
    )
    copy = Scorecard(event_id=source.event_id, categories=[], criteria=[])
    db.add(copy)
    await service.fill_scorecard(db, copy, source.event_id, payload)
    await db.commit()
    return _scorecard_out(await db.get(Scorecard, copy.id, populate_existing=True))


@router.delete('/scorecards/{scorecard_id}', status_code=204, summary='Удалить таблицу')
async def delete_scorecard(scorecard_id: int, db: Db, user: CurrentUser) -> Response:
    scorecard = await db.get(Scorecard, scorecard_id)
    if scorecard is None:
        raise _not_found('Таблица не найдена')
    await _event(db, scorecard.event_id, user)
    if await db.scalar(select(Sheet.id).where(Sheet.scorecard_id == scorecard_id).limit(1)):
        raise _bad('Таблица используется в оценочном листе')
    await db.delete(scorecard)
    await db.commit()
    return Response(status_code=204)


# --- Листы -----------------------------------------------------------------------------------


@router.get('/events/{event_id}/sheets', response_model=list[SheetListItem], summary='Оценочные листы')
async def list_sheets(event_id: int, db: Db, user: CurrentUser):
    await _event(db, event_id, user, 'view')
    sheets = list(
        (await db.scalars(select(Sheet).where(Sheet.event_id == event_id).order_by(Sheet.created_at))).unique()
    )
    counts = await service.sheet_count_scored(db, [s.id for s in sheets])
    result = []
    for sheet in sheets:
        total, scored = counts.get(sheet.id, (0, 0))
        result.append(
            SheetListItem(
                id=sheet.id,
                title=sheet.title,
                status=sheet.status,
                mode=sheet.mode,
                works=len(sheet.works),
                judges=len(sheet.judges),
                progress=round(100 * scored / total) if total else 0,
            )
        )
    return result


@router.post('/events/{event_id}/sheets', response_model=SheetOut, status_code=201, summary='Создать лист')
async def create_sheet(event_id: int, payload: SheetCreate, db: Db, user: CurrentUser):
    event = await _event(db, event_id, user)
    scorecard = await db.get(Scorecard, payload.scorecard_id)
    if scorecard is None or scorecard.event_id != event.id:
        raise _bad('Таблица оценок не найдена в этом мероприятии')
    if payload.stage_id and payload.stage_id not in {s.id for s in event.stages}:
        raise _bad('Этап не найден в этом мероприятии')
    sheet = Sheet(event_id=event.id, judges=[], works=[], **payload.model_dump(exclude_none=True))
    db.add(sheet)
    await db.commit()
    sheet, _ = await _sheet(db, sheet.id, user)
    return _sheet_out(sheet)


@router.get('/sheets/{sheet_id}', response_model=SheetOut, summary='Лист с работами, судьями и баллами')
async def get_sheet(sheet_id: int, db: Db, user: CurrentUser):
    sheet, _ = await _sheet(db, sheet_id, user, 'view')
    return _sheet_out(sheet)


@router.patch('/sheets/{sheet_id}', response_model=SheetOut, summary='Изменить настройки листа')
async def update_sheet(sheet_id: int, payload: SheetUpdate, db: Db, user: CurrentUser):
    sheet, event = await _sheet(db, sheet_id, user)
    changes = payload.model_dump(exclude_unset=True)
    if 'scorecard_id' in changes and changes['scorecard_id'] != sheet.scorecard_id:
        if any(e.items for w in sheet.works for e in w.evaluations):
            raise _bad('Таблицу оценок нельзя сменить: оценки уже начали ставить')
        scorecard = await db.get(Scorecard, changes['scorecard_id'])
        if scorecard is None or scorecard.event_id != event.id:
            raise _bad('Таблица оценок не найдена в этом мероприятии')
    for field, value in changes.items():
        setattr(sheet, field, value)
    await db.flush()
    await db.refresh(sheet, ['scorecard'])
    service.recompute_sheet(sheet)
    await db.commit()
    return _sheet_out(sheet)


@router.delete('/sheets/{sheet_id}', status_code=204, summary='Удалить лист')
async def delete_sheet(sheet_id: int, db: Db, user: CurrentUser) -> Response:
    sheet, _ = await _sheet(db, sheet_id, user)
    if any(e.score is not None for w in sheet.works for e in w.evaluations):
        raise _bad('В листе уже есть оценки. Закройте лист вместо удаления.')
    await db.delete(sheet)
    await db.commit()
    return Response(status_code=204)


@router.post('/sheets/{sheet_id}/works', response_model=SheetOut, summary='Добавить работы')
async def add_works(sheet_id: int, payload: AddWorks, db: Db, user: CurrentUser):
    sheet, _ = await _sheet(db, sheet_id, user)
    await service.add_works(db, sheet, payload)
    await db.commit()
    sheet, _ = await _sheet(db, sheet_id, user)
    return _sheet_out(sheet)


@router.delete('/sheets/{sheet_id}/works/{work_id}', response_model=SheetOut, summary='Убрать работу')
async def remove_work(sheet_id: int, work_id: int, db: Db, user: CurrentUser):
    sheet, _ = await _sheet(db, sheet_id, user)
    try:
        await service.remove_work(db, sheet, work_id)
    except service.EvaluationError as exc:
        raise _bad(exc) from exc
    await db.commit()
    return _sheet_out(sheet)


@router.put('/sheets/{sheet_id}/judges', response_model=SheetOut, summary='Судьи листа')
async def set_judges(sheet_id: int, payload: SetJudges, db: Db, user: CurrentUser):
    sheet, event = await _sheet(db, sheet_id, user)
    try:
        await service.set_judges(db, user, sheet, event, payload.judges, payload.force)
    except service.EvaluationError as exc:
        raise _bad(exc) from exc
    await db.commit()
    sheet, _ = await _sheet(db, sheet_id, user)
    return _sheet_out(sheet)


@router.post('/sheets/{sheet_id}/distribute', summary='Распределить работы между судьями')
async def distribute(sheet_id: int, payload: Distribute, db: Db, user: CurrentUser) -> dict:
    sheet, _ = await _sheet(db, sheet_id, user)
    try:
        result = await service.distribute(db, sheet, payload.mode, payload.per_work)
    except service.EvaluationError as exc:
        raise _bad(exc) from exc
    service.recompute_sheet(sheet)
    await db.commit()
    return result


@router.post('/sheets/{sheet_id}/status', response_model=SheetOut, summary='Запустить, закрыть или вернуть в черновик')
async def change_status(sheet_id: int, payload: SheetStatus, db: Db, user: CurrentUser):
    sheet, _ = await _sheet(db, sheet_id, user, 'staff')
    try:
        await service.change_status(db, user, sheet, payload.status)
    except service.EvaluationError as exc:
        raise _bad(exc) from exc
    await db.commit()
    return _sheet_out(sheet)


@router.post(
    '/sheets/{sheet_id}/judges/{user_id}/access', response_model=SheetOut, summary='Открыть или закрыть оценку судье'
)
async def judge_access(sheet_id: int, user_id: int, payload: JudgeAccess, db: Db, user: CurrentUser):
    sheet, _ = await _sheet(db, sheet_id, user, 'staff')
    judge = next((j for j in sheet.judges if j.user_id == user_id), None)
    if judge is None:
        raise _not_found('Судья не найден в листе')
    if sheet.status != 'closed':
        raise _bad('Отдельный доступ нужен только для закрытого листа')
    judge.reopened = payload.open
    record(db, 'sheet.judge_access', 'sheet', sheet.id, user.id, judge_id=user_id, open=payload.open)
    await db.commit()
    return _sheet_out(sheet)


@router.post('/sheets/{sheet_id}/judge-cards', response_model=list[JudgeCard], summary='Листы судей с QR для входа')
async def judge_cards(sheet_id: int, payload: JudgeCardsRequest, db: Db, user: CurrentUser):
    """Одноразовые ссылки входа на 20 минут для печати. Каждый вызов выпускает новые ссылки."""
    sheet, _ = await _sheet(db, sheet_id, user, 'staff')
    cards = []
    for judge in sheet.judges:
        if payload.user_ids and judge.user_id not in payload.user_ids:
            continue
        token, expires_at = await issue_judge_login(db, judge.user, f'/judging/sheets/{sheet.id}')
        cards.append(
            JudgeCard(
                user_id=judge.user_id,
                full_name=_person_name(judge.user),
                login_url=f'{settings.app_url.rstrip("/")}/auth/magic?token={token}',
                expires_at=expires_at,
                works=sum(1 for w in sheet.works for e in w.evaluations if e.judge_id == judge.user_id),
            )
        )
    record(db, 'sheet.judge_cards', 'sheet', sheet.id, user.id, count=len(cards))
    await db.commit()
    return cards


# --- Судья -----------------------------------------------------------------------------------


@router.get('/my/sheets', response_model=list[MySheet], summary='Мои оценочные листы')
async def my_sheets(db: Db, user: CurrentUser):
    sheets = (
        await db.scalars(
            select(Sheet)
            .join(SheetJudge, SheetJudge.sheet_id == Sheet.id)
            .where(SheetJudge.user_id == user.id, Sheet.status != 'draft')
            .order_by(Sheet.created_at.desc())
        )
    ).unique()
    result = []
    for sheet in sheets:
        own = [e for w in sheet.works for e in w.evaluations if e.judge_id == user.id]
        event = await get_event(db, sheet.event_id)
        result.append(
            MySheet(
                id=sheet.id,
                title=sheet.title,
                status=sheet.status,
                editable=service.judge_can_edit(sheet, user.id),
                deadline=sheet.deadline,
                event_title=event.title,
                total=len(own),
                scored=sum(e.is_scored for e in own),
            )
        )
    return result


async def _judge_sheet(db, sheet_id: int, user: User) -> Sheet:
    sheet = await db.get(Sheet, sheet_id, populate_existing=True)
    if sheet is None or sheet.status == 'draft' or user.id not in {j.user_id for j in sheet.judges}:
        raise _not_found('Лист не найден')
    return sheet


def _own_evaluations(sheet: Sheet, user: User) -> list[Evaluation]:
    return [e for w in sheet.works for e in w.evaluations if e.judge_id == user.id]


@router.get('/my/sheets/{sheet_id}/works', response_model=list[JudgeWork], summary='Работы для оценки')
async def my_works(sheet_id: int, db: Db, user: CurrentUser):
    sheet = await _judge_sheet(db, sheet_id, user)
    result = []
    for evaluation in _own_evaluations(sheet, user):
        app = service.work_of(sheet, evaluation).application
        result.append(
            JudgeWork(
                evaluation_id=evaluation.id,
                number=app.number,
                title=app.title,
                direction=app.direction.title if app.direction else '',
                participants=[m.full_name for m in app.members if m.role == 'participant'],
                score=evaluation.score,
                is_scored=evaluation.is_scored,
            )
        )
    return result


async def _judge_evaluation(db, evaluation_id: int, user: User) -> tuple[Sheet, Evaluation]:
    evaluation = await db.get(Evaluation, evaluation_id)
    if evaluation is None or evaluation.judge_id != user.id:
        raise _not_found('Оценка не найдена')
    work = await db.get(SheetWork, evaluation.sheet_work_id)
    sheet = await _judge_sheet(db, work.sheet_id, user)
    return sheet, next(e for e in _own_evaluations(sheet, user) if e.id == evaluation_id)


@router.get('/evaluations/{evaluation_id}', response_model=EvaluationBundle, summary='Оценка работы судьёй')
async def get_evaluation(evaluation_id: int, db: Db, user: CurrentUser):
    sheet, evaluation = await _judge_evaluation(db, evaluation_id, user)
    editable = service.judge_can_edit(sheet, user.id)
    return _bundle(sheet, evaluation, editable, True, _own_evaluations(sheet, user))


@router.put(
    '/evaluations/{evaluation_id}/criteria/{criterion_id}', response_model=EvaluationBundle, summary='Оценить критерий'
)
async def set_criterion(evaluation_id: int, criterion_id: int, payload: CriterionValue, db: Db, user: CurrentUser):
    sheet, evaluation = await _judge_evaluation(db, evaluation_id, user)
    if not service.judge_can_edit(sheet, user.id):
        raise _bad('Оценка закрыта')
    try:
        await service.set_criterion(
            db, sheet, evaluation, criterion_id, payload.level_id, payload.option_ids, payload.comment, payload.clear
        )
    except service.EvaluationError as exc:
        raise _bad(exc) from exc
    await db.commit()
    return _bundle(sheet, evaluation, True, True, _own_evaluations(sheet, user))


@router.patch('/evaluations/{evaluation_id}', response_model=EvaluationBundle, summary='Общий комментарий')
async def set_comment(evaluation_id: int, payload: EvaluationComment, db: Db, user: CurrentUser):
    sheet, evaluation = await _judge_evaluation(db, evaluation_id, user)
    if not service.judge_can_edit(sheet, user.id):
        raise _bad('Оценка закрыта')
    evaluation.comment = payload.comment.strip()
    await db.commit()
    return _bundle(sheet, evaluation, True, True, _own_evaluations(sheet, user))


# --- Анонимная оценка по QR ------------------------------------------------------------------


async def _public_work(db, token: str) -> tuple[Sheet, SheetWork]:
    work = await db.scalar(select(SheetWork).where(SheetWork.public_token == token))
    if work is None:
        raise _not_found('Работа не найдена')
    sheet = await db.get(Sheet, work.sheet_id, populate_existing=True)
    if sheet.mode == 'jury' or sheet.status == 'draft':
        raise _not_found('Работа не найдена')
    return sheet, next(w for w in sheet.works if w.id == work.id)


async def _anonymous_evaluation(db, token: str, anon_token: str | None) -> tuple[Sheet, Evaluation]:
    sheet, work = await _public_work(db, token)
    try:
        payload = read_state(anon_token or '')
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Начните оценку заново') from exc
    evaluation = next((e for e in work.evaluations if e.id == payload.get('evaluation_id') and e.is_anonymous), None)
    if evaluation is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Начните оценку заново')
    return sheet, evaluation


@public_router.get('/{token}', response_model=PublicWork, summary='Работа для анонимной оценки')
async def public_work(token: str, db: Db):
    sheet, work = await _public_work(db, token)
    return PublicWork(
        sheet_title=sheet.title,
        event_title=work.application.event.title,
        open=sheet.status == 'active',
        work=_work_info(work, full=False),
    )


@public_router.post('/{token}/start', response_model=AnonymousStarted, summary='Начать анонимную оценку')
async def anonymous_start(token: str, payload: AnonymousStart, db: Db):
    sheet, work = await _public_work(db, token)
    if sheet.status != 'active':
        raise _bad('Оценка этой работы закрыта')
    evaluation = Evaluation(is_anonymous=True, anonymous_name=payload.name, items=[])
    work.evaluations.append(evaluation)
    await db.commit()
    anon_token = sign_state({'evaluation_id': evaluation.id}, ttl_minutes=ANON_TTL_MINUTES)
    return AnonymousStarted(token=anon_token, evaluation=_bundle(sheet, evaluation, True, False))


@public_router.get('/{token}/evaluation', response_model=EvaluationBundle, summary='Моя анонимная оценка')
async def anonymous_get(token: str, db: Db, x_anonymous_token: Annotated[str | None, Header()] = None):
    sheet, evaluation = await _anonymous_evaluation(db, token, x_anonymous_token)
    return _bundle(sheet, evaluation, sheet.status == 'active', False)


@public_router.put(
    '/{token}/criteria/{criterion_id}', response_model=EvaluationBundle, summary='Анонимно оценить критерий'
)
async def anonymous_set(
    token: str,
    criterion_id: int,
    payload: CriterionValue,
    db: Db,
    x_anonymous_token: Annotated[str | None, Header()] = None,
):
    sheet, evaluation = await _anonymous_evaluation(db, token, x_anonymous_token)
    if sheet.status != 'active':
        raise _bad('Оценка этой работы закрыта')
    try:
        await service.set_criterion(
            db, sheet, evaluation, criterion_id, payload.level_id, payload.option_ids, payload.comment, payload.clear
        )
    except service.EvaluationError as exc:
        raise _bad(exc) from exc
    await db.commit()
    return _bundle(sheet, evaluation, True, False)


@public_router.patch('/{token}/evaluation', response_model=EvaluationBundle, summary='Комментарий анонимной оценки')
async def anonymous_comment(
    token: str, payload: EvaluationComment, db: Db, x_anonymous_token: Annotated[str | None, Header()] = None
):
    sheet, evaluation = await _anonymous_evaluation(db, token, x_anonymous_token)
    if sheet.status != 'active':
        raise _bad('Оценка этой работы закрыта')
    evaluation.comment = payload.comment.strip()
    await db.commit()
    return _bundle(sheet, evaluation, True, False)
