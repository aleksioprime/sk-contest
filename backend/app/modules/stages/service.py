from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import ACCEPTED, Application
from app.modules.audit.service import record
from app.modules.evaluation.models import Sheet, SheetWork
from app.modules.evaluation.scoring import assign_ranks, round2
from app.modules.events.models import Event, Stage
from app.modules.people.models import User
from app.modules.stages.models import (
    ADMITTED,
    EVALUATED,
    NOT_PASSED,
    PASSED,
    SCHEDULED,
    WITHDRAWN,
    StageParticipation,
)

RULE_TYPES = ('top_n', 'threshold', 'manual')


class StageError(Exception):
    pass


def next_stage(event: Event, stage: Stage) -> Stage | None:
    ordered = sorted(event.stages, key=lambda s: s.order)
    index = ordered.index(stage)
    return ordered[index + 1] if index + 1 < len(ordered) else None


def previous_stage(event: Event, stage: Stage) -> Stage | None:
    ordered = sorted(event.stages, key=lambda s: s.order)
    index = ordered.index(stage)
    return ordered[index - 1] if index > 0 else None


async def participations(session: AsyncSession, stage_id: int) -> list[StageParticipation]:
    rows = await session.scalars(select(StageParticipation).where(StageParticipation.stage_id == stage_id))
    return sorted(rows.unique(), key=lambda p: p.application.number)


async def sheet_scores(
    session: AsyncSession, event_id: int, stage_id: int | None, combine: str = 'avg'
) -> dict[int, Decimal]:
    """Балл заявки на этапе по всем оценочным листам этапа.

    Листов может быть несколько (например, по дням защит): работа обычно есть в одном из них,
    а если в нескольких — баллы объединяются по правилу этапа: среднее, сумма или лучший.

    Если у этапа нет своих листов, учитываются листы без этапа — так работают мероприятия,
    где листы создали, не привязывая к этапам.
    """
    query = (
        select(SheetWork.application_id, SheetWork.score)
        .join(Sheet, Sheet.id == SheetWork.sheet_id)
        .where(Sheet.event_id == event_id, SheetWork.score.is_not(None))
    )
    if stage_id is not None:
        has_own = await session.scalar(
            select(Sheet.id).where(Sheet.event_id == event_id, Sheet.stage_id == stage_id).limit(1)
        )
        query = query.where(Sheet.stage_id == stage_id if has_own else Sheet.stage_id.is_(None))
    scores: dict[int, list[Decimal]] = defaultdict(list)
    for application_id, score in await session.execute(query):
        scores[application_id].append(Decimal(score))
    combined = {
        'sum': lambda values: sum(values),
        'max': lambda values: max(values),
        'avg': lambda values: sum(values) / len(values),
    }[combine]
    return {app_id: round2(combined(values)) for app_id, values in scores.items()}


def rank_by_direction(items: list, key_score, key_direction, method: str = 'competition') -> dict[int, int | None]:
    """Места внутри каждого направления. items — объекты с id."""
    groups: dict = defaultdict(list)
    for item in items:
        groups[key_direction(item)].append(item)
    ranks = {}
    for group in groups.values():
        ranks.update(assign_ranks([(i.id, key_score(i)) for i in group], method))
    return ranks


async def refresh(session: AsyncSession, event: Event, stage: Stage) -> list[StageParticipation]:
    """Подтянуть баллы из листов этапа и пересчитать места по направлениям."""
    items = await participations(session, stage.id)
    scores = await sheet_scores(session, event.id, stage.id, stage.score_combine)
    active = [p for p in items if p.status != WITHDRAWN]
    for p in items:
        p.score = scores.get(p.application_id) if p.status != WITHDRAWN else None
        if p.score is not None and p.status in (ADMITTED, SCHEDULED):
            p.status = EVALUATED
    by = (lambda p: p.application.direction_id) if stage.rank_scope == 'direction' else (lambda p: None)
    ranks = rank_by_direction(active, lambda p: p.score, by)
    for p in items:
        p.rank = ranks.get(p.id)
    await session.flush()
    return items


async def admit(session: AsyncSession, actor: User, event: Event, stage: Stage) -> int:
    """Первый этап — принятые заявки; следующие — прошедшие предыдущий этап."""
    previous = previous_stage(event, stage)
    if previous is None:
        query = select(Application.id).where(Application.event_id == event.id, Application.status == ACCEPTED)
    else:
        query = select(StageParticipation.application_id).where(
            StageParticipation.stage_id == previous.id, StageParticipation.status == PASSED
        )
    candidates = set(await session.scalars(query))
    present = set(
        await session.scalars(select(StageParticipation.application_id).where(StageParticipation.stage_id == stage.id))
    )
    added = candidates - present
    for application_id in added:
        session.add(StageParticipation(stage_id=stage.id, application_id=application_id, status=ADMITTED))
    await session.flush()
    record(session, 'stage.admit', 'stage', stage.id, actor.id, added=len(added))
    return len(added)


def validate_rule(rule: dict) -> dict:
    kind = rule.get('type', 'manual')
    if kind not in RULE_TYPES:
        raise StageError('Неизвестное правило перехода')
    if kind == 'top_n' and not (isinstance(rule.get('n'), int) and rule['n'] >= 1):
        raise StageError('Укажите, сколько участников проходит')
    if kind == 'threshold' and rule.get('threshold') is None:
        raise StageError('Укажите проходной балл')
    return {
        'type': kind,
        'n': rule.get('n'),
        'per_direction': bool(rule.get('per_direction', True)),
        'threshold': rule.get('threshold'),
    }


def proposal(items: list[StageParticipation], rule: dict) -> dict[int, str | None]:
    """Предложение по правилу: кто проходит. При равенстве баллов на границе top-N проходят все с этим баллом."""
    active = [p for p in items if p.status != WITHDRAWN]
    result: dict[int, str | None] = {}
    kind = rule.get('type', 'manual')
    if kind == 'manual':
        return {p.id: p.status if p.status in (PASSED, NOT_PASSED) else None for p in active}
    if kind == 'threshold':
        threshold = Decimal(str(rule['threshold']))
        return {p.id: PASSED if p.score is not None and p.score >= threshold else NOT_PASSED for p in active}
    groups: dict = defaultdict(list)
    for p in active:
        groups[p.application.direction_id if rule.get('per_direction') else None].append(p)
    for group in groups.values():
        scored = sorted((p for p in group if p.score is not None), key=lambda p: -p.score)
        cutoff = scored[rule['n'] - 1].score if len(scored) >= rule['n'] else None
        for p in group:
            passes = p.score is not None and (cutoff is None or p.score >= cutoff)
            result[p.id] = PASSED if passes else NOT_PASSED
    return result


async def apply_decisions(
    session: AsyncSession, actor: User, event: Event, stage: Stage, decisions: dict[int, str]
) -> dict:
    items = {p.id: p for p in await participations(session, stage.id)}
    unknown = set(decisions) - set(items)
    if unknown:
        raise StageError('Участник не найден на этапе')
    for pid, status in decisions.items():
        if status not in (PASSED, NOT_PASSED):
            raise StageError('Решение может быть только «прошёл» или «не прошёл»')
        items[pid].status = status
    following = next_stage(event, stage)
    admitted = 0
    if following:
        present = set(
            await session.scalars(
                select(StageParticipation.application_id).where(StageParticipation.stage_id == following.id)
            )
        )
        for p in items.values():
            if p.status == PASSED and p.application_id not in present:
                session.add(StageParticipation(stage_id=following.id, application_id=p.application_id))
                admitted += 1
    await session.flush()
    passed = sum(1 for status in decisions.values() if status == PASSED)
    record(session, 'stage.advance', 'stage', stage.id, actor.id, passed=passed, admitted_next=admitted)
    return {'passed': passed, 'not_passed': len(decisions) - passed, 'admitted_next': admitted}


# --- Итоги -----------------------------------------------------------------------------------


def results_stage(event: Event, with_participants: set[int]) -> Stage | None:
    """Этап итогов: выбранный в настройках наград или последний этап, где есть участники."""
    chosen = event.awards.get('stage_id') if event.awards else None
    stages = sorted(event.stages, key=lambda s: s.order)
    if chosen:
        return next((s for s in stages if s.id == chosen), None)
    with_people = [s for s in stages if s.id in with_participants]
    return with_people[-1] if with_people else None


def award_for(rank: int | None, awards: dict) -> str:
    winners = int(awards.get('winners', 1))
    prize_places = int(awards.get('prize_places', 3))
    if rank is not None and rank <= winners:
        return 'winner'
    if rank is not None and rank <= prize_places:
        return 'prize'
    return 'participant'


async def results(session: AsyncSession, event: Event) -> list[dict]:
    """Итоговый рейтинг по направлениям: место, балл, награда."""
    staged = set(
        await session.scalars(
            select(StageParticipation.stage_id)
            .where(StageParticipation.stage_id.in_([s.id for s in event.stages]))
            .distinct()
        )
    )
    stage = results_stage(event, staged)
    if stage is not None:
        items = [p for p in await refresh(session, event, stage) if p.status != WITHDRAWN]
        rows = [(p.application, p.score) for p in items]
    else:
        scores = await sheet_scores(session, event.id, None)
        apps = (
            await session.scalars(
                select(Application).where(Application.event_id == event.id, Application.status == ACCEPTED)
            )
        ).unique()
        rows = [(app, scores.get(app.id)) for app in apps]

    class Row:
        def __init__(self, app, score):
            self.id, self.app, self.score = app.id, app, score

    awards = event.awards or {}
    overall = awards.get('rank_scope') == 'overall'
    wrapped = [Row(app, score) for app, score in rows]
    ranks = rank_by_direction(
        wrapped, lambda r: r.score, (lambda r: None) if overall else (lambda r: r.app.direction_id)
    )
    nominations: dict[int, list[str]] = defaultdict(list)
    for nomination in awards.get('nominations', []):
        for app_id in nomination.get('application_ids', []):
            nominations[app_id].append(nomination['title'])
    result = []
    for row in wrapped:
        rank = ranks.get(row.id)
        result.append(
            {
                'application': row.app,
                'score': row.score,
                'rank': rank,
                'award': award_for(rank, awards),
                'nominations': nominations.get(row.id, []),
                'stage_id': stage.id if stage else None,
            }
        )
    direction_order = {d.id: d.order for d in event.directions}
    result.sort(
        key=lambda r: (
            0 if overall else direction_order.get(r['application'].direction_id, 999),
            r['rank'] or 10**6,
            r['application'].number,
        )
    )
    return result


async def published_winners(session: AsyncSession, event: Event) -> list[dict]:
    """Победители и призёры по направлениям для лендинга. Без опубликованных итогов — пусто."""
    if event.results_published_at is None:
        return []
    overall = (event.awards or {}).get('rank_scope') == 'overall'
    groups: dict[str, list[dict]] = {}
    by_nomination: dict[str, list[dict]] = {}
    for row in await results(session, event):
        app = row['application']
        entry = {
            'title': app.title,
            'participants': [m.full_name for m in app.members if m.role == 'participant'],
        }
        for title in row['nominations']:
            by_nomination.setdefault(title, []).append({**entry, 'rank': None, 'award': 'nomination'})
        if row['award'] == 'participant':
            continue
        key = '' if overall else (app.direction.title if app.direction else '')
        groups.setdefault(key, []).append({**entry, 'rank': row['rank'], 'award': row['award']})
    return [
        {'direction': direction, 'winners': winners, 'nomination': False} for direction, winners in groups.items()
    ] + [
        {'direction': f'Номинация «{title}»', 'winners': winners, 'nomination': True}
        for title, winners in by_nomination.items()
    ]
