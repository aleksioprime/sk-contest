import json

import pytest
from sqlalchemy import func, select

from app.legacy.nocobase import load
from app.modules.applications.models import Application
from app.modules.evaluation.models import Evaluation, Sheet, SheetWork
from app.modules.events.models import Event, EventMember
from app.modules.people.models import User

CONTEST = 360000000000001


def _dump(path, **collections):
    for name, rows in collections.items():
        (path / f'{name}.json').write_text(json.dumps(rows, ensure_ascii=False))


@pytest.fixture
def export(tmp_path):
    """Маленькая выгрузка в формате API NocoBase: конкурс, две работы, судья и анонимный зритель."""
    p = lambda i: CONTEST + i  # noqa: E731
    _dump(
        tmp_path,
        persons=[
            {'id': p(100), 'last_name': 'Иванова', 'first_name': 'Анна', 'type': ['student']},
            {'id': p(101), 'last_name': 'Борисов', 'first_name': 'Борис', 'type': ['student']},
            {
                'id': p(102),
                'last_name': 'Судьина',
                'first_name': 'Мария',
                'email': 'Judge@Example.org',
                'type': ['employee'],
            },
            {'id': p(103), 'last_name': 'Руководитель', 'first_name': 'Пётр', 'type': ['employee']},
        ],
        contests=[{'id': CONTEST, 'title': 'SkolStart 2026', 'createdAt': '2025-10-01T10:00:00Z'}],
        contest_directions=[{'id': p(1), 'contest_id': CONTEST, 'title': 'Инженерия'}],
        contest_stages=[{'id': p(2), 'contest_id': CONTEST, 'title': 'Финал', 'date_start': '2026-04-18'}],
        contest_participations=[
            {
                'id': p(10),
                'contest_id': CONTEST,
                'title': 'Умная теплица',
                'direction_id': p(1),
                'participants': [{'id': p(100)}],
                'supervisors': [{'id': p(103)}],
            },
            {
                'id': p(11),
                'contest_id': CONTEST,
                'title': 'Робот',
                'direction_id': p(1),
                'participants': [{'id': p(101)}],
            },
        ],
        contest_stage_participations=[
            {'id': p(20), 'stage_id': p(2), 'participation_id': p(10), 'status': 'passed'},
        ],
        contest_criterion_scales=[{'id': p(30), 'contest_id': CONTEST, 'title': '0–2'}],
        contest_criterion_scale_levels=[
            {'id': p(31), 'scale_id': p(30), 'title': 'Нет', 'point': 0, 'order': 0},
            {'id': p(32), 'scale_id': p(30), 'title': 'Частично', 'point': 1, 'order': 1},
            {'id': p(33), 'scale_id': p(30), 'title': 'Да', 'point': 2, 'order': 2},
        ],
        contest_scorecards=[{'id': p(40), 'contest_id': CONTEST, 'title': 'Защита'}],
        contest_scorecard_criteria=[
            {
                'id': p(41),
                'scorecard_id': p(40),
                'title': 'Актуальность',
                'type': 'scale',
                'scale_id': p(30),
                'order': 0,
            },
            {'id': p(42), 'scorecard_id': p(40), 'title': 'Результаты', 'type': 'checklist', 'order': 1},
        ],
        contest_scorecard_criterion_options=[
            {'id': p(43), 'criterion_id': p(42), 'title': 'Прототип', 'point': 1, 'order': 0},
            {'id': p(44), 'criterion_id': p(42), 'title': 'Испытания', 'point': 1, 'order': 1},
        ],
        contest_evaluation_sheets=[
            {
                'id': p(50),
                'contest_id': CONTEST,
                'stage_id': p(2),
                'scorecard_id': p(40),
                'title': 'Финал',
                'status': 'archived',
                'is_anonymous_enabled': True,
                'judges': [{'id': p(102)}],
            }
        ],
        contest_evaluation_sheet_works=[
            {'id': p(60), 'sheet_id': p(50), 'participation_id': p(10), 'score': 3.5, 'public_token': 'abc12345'},
            {'id': p(61), 'sheet_id': p(50), 'participation_id': p(11), 'score': 1},
        ],
        contest_evaluations=[
            {'id': p(70), 'sheet_work_id': p(60), 'judge_id': p(102)},
            {'id': p(71), 'sheet_work_id': p(61), 'judge_id': p(102)},
            {'id': p(72), 'sheet_work_id': p(60), 'is_anonymous': True, 'anonymous_name': 'Зритель'},
            {'id': p(73), 'sheet_work_id': p(60), 'judge_id': p(102)},  # повтор той же оценки
        ],
        contest_evaluation_items=[
            {'id': p(80), 'evaluation_id': p(70), 'criterion_id': p(41), 'level_id': p(33)},
            {'id': p(81), 'evaluation_id': p(70), 'criterion_id': p(42)},
            {'id': p(82), 'evaluation_id': p(71), 'criterion_id': p(41), 'level_id': p(32)},
            {'id': p(83), 'evaluation_id': p(71), 'criterion_id': p(42)},
            {'id': p(84), 'evaluation_id': p(72), 'criterion_id': p(41), 'level_id': p(31)},
            {'id': p(85), 'evaluation_id': p(72), 'criterion_id': p(42)},
        ],
        contest_evaluation_item_options=[
            {'evaluation_item_id': p(81), 'item_id': p(43)},
            {'evaluation_item_id': p(81), 'item_id': p(44)},
            {'evaluation_item_id': p(85), 'item_id': p(43)},
        ],
    )
    return tmp_path


async def test_load_contest_with_ids_and_recalculated_scores(db, export):
    report = await load(db, export)
    await db.commit()

    assert report['counts']['events'] == 1 and report['counts']['applications'] == 2
    assert report['skipped']['evaluations'][0]['reason'] == 'повтор оценки судьи'

    event = await db.get(Event, CONTEST)
    assert event.status == 'archived' and event.slug == 'skolstart-2026-2025'
    apps = list(await db.scalars(select(Application).order_by(Application.number)))
    assert [a.title for a in apps] == ['Умная теплица', 'Робот']
    assert [m.role for m in apps[0].members] == ['participant', 'supervisor']

    judge = await db.scalar(select(User).where(User.email == 'judge@example.org'))
    assert judge is not None
    roles = set(await db.scalars(select(EventMember.role).where(EventMember.user_id == judge.id)))
    assert roles == {'judge'}

    sheet = await db.get(Sheet, CONTEST + 50)
    assert sheet.status == 'closed' and sheet.mode == 'mixed'
    works = {w.id: w for w in await db.scalars(select(SheetWork))}
    # Судья: 2 + (1 + 1) = 4, зритель: 0 + 1 = 1; среднее с анонимной оценкой — 2,5 (в NocoBase было 3,5)
    assert str(works[CONTEST + 60].score) == '2.50' and works[CONTEST + 60].public_token == 'abc12345'
    # у второй работы судья не заполнил чек-лист: оценка неполная, балла и места нет
    assert works[CONTEST + 61].score is None and works[CONTEST + 61].is_scored is False
    assert [w.rank for w in sorted(works.values(), key=lambda w: w.id)] == [1, None]
    assert report['score_changes'] == [{'work_id': CONTEST + 60, 'sheet_id': CONTEST + 50, 'old': '3.5', 'new': '2.50'}]
    assert (await db.scalar(select(func.count(Evaluation.id)))) == 3

    # повторный запуск не дублирует конкурс
    again = await load(db, export)
    assert again['skipped']['contests'][0]['reason'] == 'уже перенесён'
