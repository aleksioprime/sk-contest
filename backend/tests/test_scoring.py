from decimal import Decimal
from types import SimpleNamespace as NS

from app.modules.evaluation.scoring import (
    aggregate,
    assign_ranks,
    criterion_score,
    evaluation_result,
    normalize_options,
)

D = Decimal


def test_exclusive_options():
    options = [NS(id=1, is_exclusive=False), NS(id=2, is_exclusive=False), NS(id=3, is_exclusive=True)]
    assert normalize_options([1, 2], options) == [1, 2]
    assert normalize_options([1, 2, 3], options) == [3]
    assert normalize_options([3, 1], options) == [1]
    assert normalize_options([1, 1, 99], options) == [1]


def test_criterion_score():
    checklist = NS(type='checklist', options=[NS(id=1, points=1), NS(id=2, points=D('0.5'))])
    assert criterion_score(checklist, option_ids=[1, 2]) == D('1.5')
    assert criterion_score(checklist, option_ids=[]) is None
    scale = NS(type='scale', options=[])
    assert criterion_score(scale, level=NS(points=3)) == D(3)
    assert criterion_score(scale) is None


def test_evaluation_result_with_weights():
    criteria = [NS(id=1, weight=1), NS(id=2, weight=2)]
    assert evaluation_result(criteria, {1: D(3), 2: D(2)}) == (D('7.00'), True)
    assert evaluation_result(criteria, {1: D(3)}) == (D('3.00'), False)
    assert evaluation_result(criteria, {}) == (None, False)


def test_aggregate_counts_all_scores():
    scores = [D(10)] * 20 + [D(1)] * 15  # в старой системе учитывались только первые 20
    assert aggregate(scores, 'avg') == D('6.14')
    assert aggregate([D(1), D(2), D(10)], 'median') == D('2.00')
    assert aggregate([D(1), D(2)], 'sum') == D('3.00')
    assert aggregate([], 'avg') is None


def test_rank_methods():
    scored = [(1, D(10)), (2, D(10)), (3, D(8)), (4, None), (5, D(7))]
    assert assign_ranks(scored, 'competition') == {1: 1, 2: 1, 3: 3, 4: None, 5: 4}
    assert assign_ranks(scored, 'dense') == {1: 1, 2: 1, 3: 2, 4: None, 5: 3}
