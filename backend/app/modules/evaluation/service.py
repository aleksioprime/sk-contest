import secrets
from decimal import Decimal

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application
from app.modules.audit.service import record
from app.modules.evaluation import scoring
from app.modules.evaluation.models import (
    Category,
    Criterion,
    CriterionOption,
    Evaluation,
    EvaluationItem,
    EvaluationItemOption,
    Scale,
    ScaleLevel,
    Scorecard,
    Sheet,
    SheetJudge,
    SheetWork,
)
from app.modules.evaluation.schemas import AddWorks, ScaleIn, ScorecardIn
from app.modules.events.models import Event
from app.modules.events.service import add_member
from app.modules.people.models import User
from app.modules.people.service import find_or_create_user_by_email


class EvaluationError(Exception):
    pass


# --- Шкалы и таблицы оценок ------------------------------------------------------------------


async def scale_in_use(session: AsyncSession, scale_id: int) -> bool:
    return bool(await session.scalar(select(exists().where(Criterion.scale_id == scale_id))))


def fill_scale(scale: Scale, data: ScaleIn) -> None:
    scale.title = data.title
    scale.levels = [ScaleLevel(title=lv.title, points=lv.points, order=i) for i, lv in enumerate(data.levels)]


async def scorecard_in_use(session: AsyncSession, scorecard_id: int) -> bool:
    """Таблица уже используется, если по её критериям выставлена хотя бы одна оценка."""
    query = select(
        exists().where(
            EvaluationItem.criterion_id == Criterion.id,
            Criterion.scorecard_id == scorecard_id,
            EvaluationItem.score.is_not(None),
        )
    )
    return bool(await session.scalar(query))


async def fill_scorecard(session: AsyncSession, scorecard: Scorecard, event_id: int, data: ScorecardIn) -> None:
    scorecard.title = data.title  # до первого запроса: autoflush сохранит новую таблицу
    scale_ids = {c.scale_id for c in data.criteria if c.scale_id}
    if scale_ids:
        found = set(await session.scalars(select(Scale.id).where(Scale.id.in_(scale_ids), Scale.event_id == event_id)))
        if found != scale_ids:
            raise EvaluationError('Шкала не найдена в этом мероприятии')
    scorecard.criteria = []
    scorecard.categories = [Category(title=title, order=i) for i, title in enumerate(data.categories)]
    await session.flush()
    scorecard.criteria = [
        Criterion(
            title=c.title,
            description=c.description,
            type=c.type,
            scale_id=c.scale_id if c.type == 'scale' else None,
            weight=c.weight,
            category_id=scorecard.categories[c.category].id if c.category is not None else None,
            order=i,
            options=[
                CriterionOption(title=o.title, points=o.points, is_exclusive=o.is_exclusive, order=j)
                for j, o in enumerate(c.options if c.type == 'checklist' else [])
            ],
        )
        for i, c in enumerate(data.criteria)
    ]
    await session.flush()


def max_score(scorecard: Scorecard) -> Decimal:
    total = Decimal(0)
    for criterion in scorecard.criteria:
        if criterion.type == 'checklist':
            exclusive = [Decimal(o.points) for o in criterion.options if o.is_exclusive]
            regular = sum(
                (Decimal(o.points) for o in criterion.options if not o.is_exclusive and o.points > 0), Decimal(0)
            )
            best = max([regular, *exclusive]) if exclusive else regular
        else:
            best = (
                max((Decimal(lv.points) for lv in criterion.scale.levels), default=Decimal(0)) if criterion.scale else 0
            )
        total += Decimal(criterion.weight) * best
    return scoring.round2(total)


# --- Состав листа ----------------------------------------------------------------------------


async def add_works(session: AsyncSession, sheet: Sheet, data: AddWorks) -> int:
    query = select(Application).where(Application.event_id == sheet.event_id, Application.status.in_(data.statuses))
    if data.application_ids:
        query = query.where(Application.id.in_(data.application_ids))
    if data.direction_ids:
        query = query.where(Application.direction_id.in_(data.direction_ids))
    present = {w.application_id for w in sheet.works}
    order = max((w.order for w in sheet.works), default=-1)
    added = 0
    for app in (await session.scalars(query.order_by(Application.number))).unique():
        if app.id in present:
            continue
        order += 1
        sheet.works.append(SheetWork(application_id=app.id, order=order, public_token=secrets.token_urlsafe(9)))
        added += 1
    await session.flush()
    return added


async def remove_work(session: AsyncSession, sheet: Sheet, work_id: int) -> None:
    work = next((w for w in sheet.works if w.id == work_id), None)
    if work is None:
        raise EvaluationError('Работа не найдена в листе')
    if any(e.is_scored or e.score is not None for e in work.evaluations):
        raise EvaluationError('По работе уже есть оценки, её нельзя убрать из листа')
    sheet.works.remove(work)
    await session.flush()
    recompute_ranks(sheet)


async def set_judges(
    session: AsyncSession, actor: User, sheet: Sheet, event: Event, emails: list[str], force: bool
) -> None:
    users = [await find_or_create_user_by_email(session, email) for email in dict.fromkeys(e.lower() for e in emails)]
    keep = {u.id for u in users}
    removed = [j for j in sheet.judges if j.user_id not in keep]
    for judge in removed:
        own = [e for w in sheet.works for e in w.evaluations if e.judge_id == judge.user_id]
        if any(e.score is not None for e in own) and not force:
            raise EvaluationError(
                f'Судья {judge.user.email} уже поставил оценки. Подтвердите удаление вместе с оценками.'
            )
        for work in sheet.works:
            work.evaluations = [e for e in work.evaluations if e.judge_id != judge.user_id]
        sheet.judges.remove(judge)
    present = {j.user_id for j in sheet.judges}
    for user in users:
        if user.id not in present:
            sheet.judges.append(SheetJudge(user_id=user.id))
        await add_member(session, actor, event, user, 'judge')
    await session.flush()
    for work in sheet.works:
        recompute_work(sheet, work)
    recompute_ranks(sheet)


def has_conflict(user: User, app: Application) -> bool:
    """Судья не оценивает работу, в которой он участник или руководитель."""
    email = user.email.lower()
    person_id = user.person_id
    return any((person_id and m.person_id == person_id) or (m.email and m.email.lower() == email) for m in app.members)


async def distribute(session: AsyncSession, sheet: Sheet, mode: str, per_work: int) -> dict:
    judges = [j.user for j in sheet.judges]
    if not judges:
        raise EvaluationError('Добавьте судей в лист')
    load = {j.id: 0 for j in judges}
    for work in sheet.works:
        for evaluation in work.evaluations:
            if evaluation.judge_id in load:
                load[evaluation.judge_id] += 1
    created, conflicts = 0, 0
    for work in sheet.works:
        assigned = {e.judge_id for e in work.evaluations if not e.is_anonymous}
        candidates = [j for j in judges if j.id not in assigned]
        allowed = [j for j in candidates if not has_conflict(j, work.application)]
        conflicts += len(candidates) - len(allowed)
        if mode == 'per_work':
            need = max(0, per_work - len(assigned))
            allowed = sorted(allowed, key=lambda j: (load[j.id], j.id))[:need]
        for judge in allowed:
            work.evaluations.append(Evaluation(judge_id=judge.id, items=[]))
            load[judge.id] += 1
            created += 1
    await session.flush()
    return {'created': created, 'conflicts': conflicts}


# --- Подсчёт ---------------------------------------------------------------------------------


def recompute_evaluation(sheet: Sheet, evaluation: Evaluation) -> None:
    scores = {item.criterion_id: item.score for item in evaluation.items}
    evaluation.score, evaluation.is_scored = scoring.evaluation_result(sheet.scorecard.criteria, scores)


def recompute_work(sheet: Sheet, work: SheetWork) -> None:
    counted = [e for e in work.evaluations if not e.is_anonymous or (sheet.include_anonymous and sheet.mode != 'jury')]
    jury = [e for e in work.evaluations if not e.is_anonymous]
    work.score = scoring.aggregate([e.score for e in counted if e.is_scored], sheet.aggregate)
    work.is_scored = (
        bool(jury) and all(e.is_scored for e in jury) if sheet.mode != 'anonymous' else work.score is not None
    )


def recompute_ranks(sheet: Sheet) -> None:
    ranks = scoring.assign_ranks([(w.id, w.score) for w in sheet.works], sheet.rank_method)
    for work in sheet.works:
        work.rank = ranks.get(work.id)


def recompute_sheet(sheet: Sheet) -> None:
    for work in sheet.works:
        for evaluation in work.evaluations:
            recompute_evaluation(sheet, evaluation)
        recompute_work(sheet, work)
    recompute_ranks(sheet)


async def set_criterion(
    session: AsyncSession,
    sheet: Sheet,
    evaluation: Evaluation,
    criterion_id: int,
    level_id: int | None,
    option_ids: list[int] | None,
    comment: str | None,
    clear: bool,
) -> None:
    """Изменить оценку по критерию и сразу пересчитать оценку, балл работы и ранги листа."""
    criterion = next((c for c in sheet.scorecard.criteria if c.id == criterion_id), None)
    if criterion is None:
        raise EvaluationError('Критерий не найден')
    item = next((i for i in evaluation.items if i.criterion_id == criterion_id), None)
    if item is None:
        item = EvaluationItem(criterion_id=criterion_id, options=[])
        evaluation.items.append(item)

    if clear:
        item.level_id, item.score, item.options = None, None, []
    elif criterion.type == 'scale' and level_id is not None:
        level = next((lv for lv in criterion.scale.levels if lv.id == level_id), None)
        if level is None:
            raise EvaluationError('Такого уровня нет в шкале критерия')
        item.level_id, item.score = level.id, scoring.criterion_score(criterion, level=level)
    elif criterion.type == 'checklist' and option_ids is not None:
        normalized = scoring.normalize_options(option_ids, criterion.options)
        item.options = [EvaluationItemOption(option_id=i) for i in normalized]
        item.score = scoring.criterion_score(criterion, option_ids=normalized)
    if comment is not None:
        item.comment = comment.strip()

    recompute_evaluation(sheet, evaluation)
    recompute_work(sheet, work_of(sheet, evaluation))
    recompute_ranks(sheet)
    await session.flush()


def work_of(sheet: Sheet, evaluation: Evaluation) -> SheetWork:
    return next(w for w in sheet.works if w.id == evaluation.sheet_work_id)


async def change_status(session: AsyncSession, actor: User, sheet: Sheet, status: str) -> None:
    if status == 'active' and (not sheet.works or not (sheet.judges or sheet.mode != 'jury')):
        raise EvaluationError('Перед запуском добавьте в лист работы и судей')
    if status == 'active' and not sheet.scorecard.criteria:
        raise EvaluationError('В таблице оценок нет критериев')
    record(session, 'sheet.status', 'sheet', sheet.id, actor.id, old=sheet.status, new=status)
    sheet.status = status
    await session.flush()


async def sheet_count_scored(session: AsyncSession, sheet_ids: list[int]) -> dict[int, tuple[int, int]]:
    rows = await session.execute(
        select(SheetWork.sheet_id, func.count(Evaluation.id), func.count(Evaluation.id).filter(Evaluation.is_scored))
        .join(Evaluation, Evaluation.sheet_work_id == SheetWork.id)
        .where(SheetWork.sheet_id.in_(sheet_ids), Evaluation.is_anonymous.is_(False))
        .group_by(SheetWork.sheet_id)
    )
    return {sheet_id: (total, scored) for sheet_id, total, scored in rows}
