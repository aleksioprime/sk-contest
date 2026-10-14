"""Формулы подсчёта без обращения к БД.

Совпадают с логикой старой системы (docs/legacy/nocobase.md), но без её ошибок:
считаются все оценки, ранги пересчитываются сразу, метод ранга и агрегат настраиваются.
"""

from decimal import ROUND_HALF_UP, Decimal
from statistics import median

TWO_PLACES = Decimal('0.01')


def round2(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def normalize_options(selected: list[int], options: list) -> list[int]:
    """Исключающий пункт снимает остальные; обычный пункт снимает исключающие. Последний выбранный побеждает."""
    by_id = {o.id: o for o in options}
    selected = [i for i in dict.fromkeys(selected) if i in by_id]
    if not selected:
        return []
    last = by_id[selected[-1]]
    if last.is_exclusive:
        return [last.id]
    return [i for i in selected if not by_id[i].is_exclusive]


def criterion_score(criterion, level=None, option_ids: list[int] | None = None) -> Decimal | None:
    if criterion.type == 'checklist':
        if not option_ids:
            return None
        points = {o.id: Decimal(o.points) for o in criterion.options}
        return sum((points[i] for i in option_ids if i in points), Decimal(0))
    return Decimal(level.points) if level is not None else None


def evaluation_result(criteria: list, scores: dict[int, Decimal | None]) -> tuple[Decimal | None, bool]:
    """Сумма баллов по критериям с весами и признак полной оценки (заполнены все критерии)."""
    filled = [(c, scores.get(c.id)) for c in criteria if scores.get(c.id) is not None]
    if not filled:
        return None, False
    total = sum((Decimal(c.weight) * score for c, score in filled), Decimal(0))
    return round2(total), len(filled) == len(criteria)


def aggregate(scores: list[Decimal], method: str) -> Decimal | None:
    if not scores:
        return None
    if method == 'sum':
        return round2(sum(scores, Decimal(0)))
    if method == 'median':
        return round2(Decimal(median(scores)))
    return round2(sum(scores, Decimal(0)) / len(scores))


def assign_ranks(scored: list[tuple[int, Decimal | None]], method: str) -> dict[int, int | None]:
    """Ранги по убыванию балла. competition: 1, 1, 3; dense: 1, 1, 2. Без балла — без ранга."""
    ranks: dict[int, int | None] = {item_id: None for item_id, score in scored if score is None}
    ordered = sorted(((i, s) for i, s in scored if s is not None), key=lambda pair: -pair[1])
    previous, rank, distinct = None, 0, 0
    for position, (item_id, score) in enumerate(ordered, start=1):
        if score != previous:
            distinct += 1
            rank = position if method == 'competition' else distinct
            previous = score
        ranks[item_id] = rank
    return ranks
