"""
Перенос конкурсов из NocoBase (docs/legacy/nocobase.md).

Два шага, чтобы загрузку можно было повторять и проверять на копии данных:

    python -m app.cli nocobase-fetch /data/nocobase   # API NocoBase → JSON-файлы (только чтение)
    python -m app.cli nocobase-load /data/nocobase    # JSON-файлы → база SK Events

ID записей сохраняются: новые ID из next_id() всегда больше ID NocoBase, пересечений нет.
Баллы оценок, работ и места пересчитываются заново (в NocoBase часть посчитана по первым 20 оценкам),
отчёт о расхождениях со старыми значениями пишется в report.json.
"""

import json
import logging
import re
import secrets
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import ACCEPTED, Application, ApplicationMember
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
from app.modules.evaluation.service import NO_EMAIL_DOMAIN, recompute_sheet
from app.modules.events.models import Direction, Event, EventMember, ParticipationForm, Stage
from app.modules.events.templates import MODULES
from app.modules.people.models import Person, User
from app.modules.people.service import normalize_email
from app.modules.stages.models import StageParticipation

logger = logging.getLogger('sk_events.nocobase')

# Коллекция → связи, которые нужно получить вместе с записями
COLLECTIONS: dict[str, list[str]] = {
    'persons': [],
    'users': [],
    'contests': [],
    'contest_directions': [],
    'contest_stages': [],
    'contest_performance_types': [],
    'contest_participations': ['participants', 'supervisors'],
    'contest_stage_participations': [],
    'contest_criterion_scales': [],
    'contest_criterion_scale_levels': [],
    'contest_scorecards': [],
    'contest_criterion_categories': [],
    'contest_scorecard_criteria': [],
    'contest_scorecard_criterion_options': [],
    'contest_evaluation_sheets': ['judges', 'observers'],
    'contest_evaluation_sheet_works': [],
    'contest_evaluations': [],
    'contest_evaluation_items': [],
    'contest_evaluation_item_options': [],
}

SHEET_STATUS = {'active': 'active', 'inactive': 'closed', 'archived': 'closed'}
STAGE_STATUS = {'accepted': 'admitted', 'evaluated': 'evaluated', 'passed': 'passed', 'not_passed': 'not_passed'}
ARCHIVE_OWNER = 'archive@import.sk-events.local'


# --- Шаг 1: выгрузка из API -----------------------------------------------------------------------


async def fetch(base_url: str, api_key: str, target: Path, page_size: int = 500) -> dict[str, int]:
    """Все записи нужных коллекций постранично. Ничего не меняет в NocoBase."""
    target.mkdir(parents=True, exist_ok=True)
    counts = {}
    headers = {'Authorization': f'Bearer {api_key}', 'X-Role': 'root'}
    async with httpx.AsyncClient(base_url=base_url.rstrip('/'), headers=headers, timeout=60) as client:
        for name, appends in COLLECTIONS.items():
            rows: list[dict] = []
            page = 1
            while True:
                params: list[tuple[str, Any]] = [('page', page), ('pageSize', page_size), ('sort', 'id')]
                params += [('appends[]', a) for a in appends]
                response = await client.get(f'/api/{name}:list', params=params)
                response.raise_for_status()
                body = response.json()
                chunk = body.get('data') or []
                rows += chunk
                meta = body.get('meta') or {}
                if len(chunk) < page_size or page >= meta.get('totalPage', page):
                    break
                page += 1
            (target / f'{name}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
            counts[name] = len(rows)
            logger.info('%s: %s записей', name, len(rows))
    return counts


# --- Шаг 2: загрузка в SK Events ------------------------------------------------------------------


def _read(source: Path, name: str) -> list[dict]:
    path = source / f'{name}.json'
    return json.loads(path.read_text()) if path.exists() else []


def _date(value) -> date | None:
    return date.fromisoformat(str(value)[:10]) if value else None


def _dt(value) -> datetime | None:
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')) if value else None


def _dec(value) -> Decimal:
    return Decimal(str(value or 0))


def _text(value, limit: int) -> str:
    return (str(value) if value is not None else '').strip()[:limit]


def _slug(title: str, year: str, used: set[str]) -> str:
    table = str.maketrans(
        'абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
        'abvgdeejziiklmnoprstufhccss_y_eua',
    )
    base = re.sub(r'[^a-z0-9]+', '-', title.lower().translate(table)).strip('-')[:40] or 'contest'
    slug = f'{base}-{year}'.strip('-')
    candidate, n = slug, 2
    while candidate in used:
        candidate, n = f'{slug}-{n}', n + 1
    used.add(candidate)
    return candidate


def _name_parts(row: dict) -> tuple[str, str, str]:
    if any(row.get(k) for k in ('last_name', 'first_name')):
        return _text(row.get('last_name'), 100), _text(row.get('first_name'), 100), _text(row.get('middle_name'), 100)
    full = _text(row.get('full_name') or row.get('name') or row.get('nickname'), 300).split()
    return (full + ['', ''])[0], (full + ['', ''])[1], ' '.join(full[2:])


def _ids(value) -> list[int]:
    """Связь «многие ко многим» в ответе API: список объектов или id."""
    return [int(v['id'] if isinstance(v, dict) else v) for v in value or []]


class Loader:
    def __init__(self, session: AsyncSession, source: Path):
        self.session = session
        self.source = source
        self.data = {name: _read(source, name) for name in COLLECTIONS}
        self.report: dict[str, Any] = {'counts': {}, 'skipped': defaultdict(list), 'score_changes': []}
        self.persons = {int(p['id']): p for p in self.data['persons']}
        self.user_emails = {
            int(u['id']): u.get('email') for u in self.data['users'] if u.get('email')
        }  # NocoBase users ↔ persons по полю user_id у персоны, если есть
        self.person_ids: dict[int, int] = {}  # id персоны NocoBase → id персоны SK Events
        self.judge_users: dict[int, int] = {}  # id персоны NocoBase → id пользователя SK Events

    def skip(self, kind: str, row_id, reason: str) -> None:
        self.report['skipped'][kind].append({'id': row_id, 'reason': reason})

    # --- люди

    async def person(self, nb_id: int) -> int | None:
        if nb_id in self.person_ids:
            return self.person_ids[nb_id]
        row = self.persons.get(nb_id)
        if row is None:
            self.skip('persons', nb_id, 'персона не найдена в выгрузке')
            return None
        existing = None
        if row.get('skolstream_id'):
            existing = await self.session.scalar(select(Person).where(Person.skolstream_id == row['skolstream_id']))
        if existing is None:
            existing = await self.session.get(Person, nb_id)
        if existing is None:
            last, first, middle = _name_parts(row)
            types = row.get('type') or []
            existing = Person(
                id=nb_id,
                source='local',
                skolstream_id=row.get('skolstream_id') or None,
                last_name=last,
                first_name=first,
                middle_name=middle,
                email=normalize_email(row['email']) if row.get('email') else None,
                is_student='student' in types,
                is_employee='employee' in types,
            )
            self.session.add(existing)
            await self.session.flush()
        self.person_ids[nb_id] = existing.id
        return existing.id

    def email_of(self, row: dict) -> str | None:
        email = row.get('email') or self.user_emails.get(int(row.get('user_id') or 0))
        return normalize_email(email) if email else None

    async def judge_user(self, nb_person_id: int) -> int | None:
        if nb_person_id in self.judge_users:
            return self.judge_users[nb_person_id]
        person_id = await self.person(nb_person_id)
        if person_id is None:
            return None
        user = await self.session.scalar(select(User).where(User.person_id == person_id))
        email = self.email_of(self.persons[nb_person_id])
        if user is None and email:
            user = await self.session.scalar(select(User).where(User.email == email))
            if user is not None and user.person_id is None:
                user.person_id = person_id
        if user is None:
            user = User(email=email or f'judge-{secrets.token_hex(6)}@{NO_EMAIL_DOMAIN}', person_id=person_id)
            self.session.add(user)
            await self.session.flush()
        self.judge_users[nb_person_id] = user.id
        return user.id

    async def archive_owner(self) -> int:
        user = await self.session.scalar(select(User).where(User.email == ARCHIVE_OWNER))
        if user is None:
            user = User(email=ARCHIVE_OWNER, is_active=False)
            self.session.add(user)
            await self.session.flush()
        return user.id

    # --- загрузка

    async def run(self) -> dict:
        s = self.session
        d = self.data
        owner = await self.archive_owner()
        used = set(await s.scalars(select(Event.slug)))
        events = {}
        for row in d['contests']:
            cid = int(row['id'])
            if await s.get(Event, cid):
                self.skip('contests', cid, 'уже перенесён')
                continue
            year = str(row.get('createdAt') or row.get('created_at') or '')[:4]
            event = Event(
                id=cid,
                slug=_slug(row.get('title') or 'contest', year, used),
                type='project_contest',
                title=_text(row.get('title'), 200) or f'Конкурс {cid}',
                description=_text(row.get('description'), 20000),
                status='archived',
                modules={m: True for m in MODULES},
                awards={'winners': 1, 'prize_places': 3},
            )
            s.add(event)
            events[cid] = event
        await s.flush()

        stage_events = {}
        for kind, model, rows in (
            ('directions', Direction, d['contest_directions']),
            ('stages', Stage, d['contest_stages']),
            ('forms', ParticipationForm, d['contest_performance_types']),
        ):
            for order, row in enumerate(sorted(rows, key=lambda r: (r.get('order') or 0, int(r['id'])))):
                cid = int(row.get('contest_id') or 0)
                if cid not in events:
                    self.skip(kind, row.get('id'), 'конкурс не переносится')
                    continue
                fields = {'id': int(row['id']), 'event_id': cid, 'title': _text(row.get('title'), 200), 'order': order}
                if model is Stage:
                    fields |= {'date_start': _date(row.get('date_start')), 'date_end': _date(row.get('date_end'))}
                    stage_events[int(row['id'])] = cid
                s.add(model(**fields))
        await s.flush()

        # заявки
        numbers: dict[int, int] = defaultdict(int)
        apps = {}
        for row in sorted(d['contest_participations'], key=lambda r: int(r['id'])):
            cid = int(row.get('contest_id') or 0)
            if cid not in events:
                self.skip('participations', row.get('id'), 'конкурс не переносится')
                continue
            numbers[cid] += 1
            members = []
            for role, key in (('participant', 'participants'), ('supervisor', 'supervisors')):
                for order, nb_person in enumerate(_ids(row.get(key))):
                    person_id = await self.person(nb_person)
                    p = self.persons.get(nb_person, {})
                    last, first, middle = _name_parts(p)
                    members.append(
                        ApplicationMember(
                            role=role,
                            person_id=person_id,
                            full_name=' '.join(x for x in (last, first, middle) if x) or 'Без имени',
                            email=self.email_of(p) or '',
                            organization='' if not row.get('is_external') else _text(p.get('organization'), 300),
                            order=order,
                        )
                    )
            created = _dt(row.get('createdAt') or row.get('created_at'))
            app = Application(
                id=int(row['id']),
                event_id=cid,
                number=numbers[cid],
                user_id=owner,
                title=_text(row.get('title'), 300),
                direction_id=int(row['direction_id']) if row.get('direction_id') else None,
                status=ACCEPTED,
                answers={'notes': _text(row.get('notes'), 5000)} if row.get('notes') else {},
                moderator_comment='',
                submitted_at=created,
                decided_at=created,
                members=members,
                consents=[],
                files=[],
            )
            s.add(app)
            apps[app.id] = app
        await s.flush()

        for row in d['contest_stage_participations']:
            if int(row.get('participation_id') or 0) not in apps or int(row.get('stage_id') or 0) not in stage_events:
                self.skip('stage_participations', row.get('id'), 'нет заявки или этапа')
                continue
            s.add(
                StageParticipation(
                    id=int(row['id']),
                    stage_id=int(row['stage_id']),
                    application_id=int(row['participation_id']),
                    status=STAGE_STATUS.get(row.get('status'), 'admitted'),
                )
            )

        # шкалы и таблицы оценок
        levels: dict[int, ScaleLevel] = {}
        for row in d['contest_criterion_scales']:
            if int(row.get('contest_id') or 0) in events:
                s.add(Scale(id=int(row['id']), event_id=int(row['contest_id']), title=_text(row.get('title'), 200)))
        await s.flush()
        scales = {int(r['id']) for r in d['contest_criterion_scales'] if int(r.get('contest_id') or 0) in events}
        for row in d['contest_criterion_scale_levels']:
            if int(row.get('scale_id') or 0) not in scales:
                continue
            level = ScaleLevel(
                id=int(row['id']),
                scale_id=int(row['scale_id']),
                title=_text(row.get('title'), 200),
                points=_dec(row.get('point')),
                order=int(row.get('order') or 0),
            )
            s.add(level)
            levels[level.id] = level
        cards = {int(r['id']) for r in d['contest_scorecards'] if int(r.get('contest_id') or 0) in events}
        for row in d['contest_scorecards']:
            if int(row['id']) in cards:
                s.add(Scorecard(id=int(row['id']), event_id=int(row['contest_id']), title=_text(row.get('title'), 200)))
        await s.flush()
        for row in d['contest_criterion_categories']:
            if int(row.get('scorecard_id') or 0) in cards:
                s.add(
                    Category(
                        id=int(row['id']),
                        scorecard_id=int(row['scorecard_id']),
                        title=_text(row.get('title'), 200),
                        order=int(row.get('order') or 0),
                    )
                )
        await s.flush()
        criteria: dict[int, Criterion] = {}
        for row in d['contest_scorecard_criteria']:
            if int(row.get('scorecard_id') or 0) not in cards:
                continue
            criterion = Criterion(
                id=int(row['id']),
                scorecard_id=int(row['scorecard_id']),
                category_id=int(row['category_id']) if row.get('category_id') else None,
                title=_text(row.get('title'), 300),
                description=_text(row.get('description'), 5000),
                type='checklist' if row.get('type') == 'checklist' else 'scale',
                scale_id=int(row['scale_id']) if row.get('scale_id') and int(row['scale_id']) in scales else None,
                order=int(row.get('order') or 0),
            )
            s.add(criterion)
            criteria[criterion.id] = criterion
        await s.flush()
        options: dict[int, CriterionOption] = {}
        for row in d['contest_scorecard_criterion_options']:
            if int(row.get('criterion_id') or 0) not in criteria:
                continue
            option = CriterionOption(
                id=int(row['id']),
                criterion_id=int(row['criterion_id']),
                title=_text(row.get('title'), 300),
                points=_dec(row.get('point')),
                is_exclusive=bool(row.get('is_exclusive')),
                order=int(row.get('order') or 0),
            )
            s.add(option)
            options[option.id] = option
        await s.flush()

        # оценочные листы
        sheets = {}
        for row in d['contest_evaluation_sheets']:
            cid = int(row.get('contest_id') or 0)
            if cid not in events or int(row.get('scorecard_id') or 0) not in cards:
                self.skip('sheets', row.get('id'), 'нет конкурса или таблицы оценок')
                continue
            sheet = Sheet(
                id=int(row['id']),
                event_id=cid,
                stage_id=int(row['stage_id']) if row.get('stage_id') and int(row['stage_id']) in stage_events else None,
                scorecard_id=int(row['scorecard_id']),
                title=_text(row.get('title'), 200) or f'Лист {row["id"]}',
                status=SHEET_STATUS.get(row.get('status'), 'closed'),
                mode='mixed' if row.get('is_anonymous_enabled') else 'jury',
                rank_method='competition',
            )
            s.add(sheet)
            sheets[sheet.id] = sheet
            await s.flush()
            for nb_person in _ids(row.get('judges')):
                user_id = await self.judge_user(nb_person)
                if user_id:
                    s.add(SheetJudge(sheet_id=sheet.id, user_id=user_id))
                    await self._member(cid, user_id, 'judge')
            for nb_person in _ids(row.get('observers')):
                user_id = await self.judge_user(nb_person)
                if user_id:
                    await self._member(cid, user_id, 'observer')
        await s.flush()

        old_work_scores = {}
        works = {}
        tokens = set()
        for row in d['contest_evaluation_sheet_works']:
            if int(row.get('sheet_id') or 0) not in sheets or int(row.get('participation_id') or 0) not in apps:
                self.skip('works', row.get('id'), 'нет листа или заявки')
                continue
            token = row.get('public_token') or ''
            if not token or token in tokens:
                token = secrets.token_urlsafe(9)
            tokens.add(token)
            work = SheetWork(
                id=int(row['id']),
                sheet_id=int(row['sheet_id']),
                application_id=int(row['participation_id']),
                order=int(row.get('order') or 0),
                public_token=token,
            )
            s.add(work)
            works[work.id] = work
            old_work_scores[work.id] = row.get('score')
        await s.flush()

        evaluations = {}
        seen = set()
        for row in sorted(d['contest_evaluations'], key=lambda r: int(r['id'])):
            work_id = int(row.get('sheet_work_id') or 0)
            if work_id not in works:
                self.skip('evaluations', row.get('id'), 'нет работы')
                continue
            judge_id = None
            if not row.get('is_anonymous') and row.get('judge_id'):
                judge_id = await self.judge_user(int(row['judge_id']))
            if judge_id and (work_id, judge_id) in seen:
                self.skip('evaluations', row['id'], 'повтор оценки судьи')
                continue
            seen.add((work_id, judge_id))
            evaluation = Evaluation(
                id=int(row['id']),
                sheet_work_id=work_id,
                judge_id=judge_id,
                is_anonymous=bool(row.get('is_anonymous')) or judge_id is None,
                anonymous_name=_text(row.get('anonymous_name'), 100),
                comment=_text(row.get('comment'), 5000),
            )
            s.add(evaluation)
            evaluations[evaluation.id] = evaluation
        await s.flush()

        chosen: dict[int, list[int]] = defaultdict(list)
        for row in d['contest_evaluation_item_options']:
            option_id = int(row.get('option_id') or row.get('item_id') or 0)  # в NocoBase поле option_id
            if option_id in options:
                chosen[int(row.get('evaluation_item_id') or 0)].append(option_id)
        pairs = set()
        for row in d['contest_evaluation_items']:
            eid, crid = int(row.get('evaluation_id') or 0), int(row.get('criterion_id') or 0)
            if eid not in evaluations or crid not in criteria or (eid, crid) in pairs:
                self.skip('items', row.get('id'), 'нет оценки или критерия, либо повтор')
                continue
            pairs.add((eid, crid))
            criterion = criteria[crid]
            level = levels.get(int(row['level_id'])) if row.get('level_id') else None
            picked = [o for o in chosen.get(int(row['id']), []) if options[o].criterion_id == crid]
            if criterion.type == 'scale':
                score = Decimal(level.points) if level else None
            else:
                own = [o for o in options.values() if o.criterion_id == crid]
                picked = scoring.normalize_options(picked, own)
                score = sum((Decimal(options[o].points) for o in picked), Decimal(0)) if picked else None
            item = EvaluationItem(
                id=int(row['id']),
                evaluation_id=eid,
                criterion_id=crid,
                level_id=level.id if level else None,
                score=score,
                comment=_text(row.get('comment'), 5000),
            )
            s.add(item)
            await s.flush()
            for option_id in picked:
                s.add(EvaluationItemOption(item_id=item.id, option_id=option_id))
        await s.flush()

        # пересчёт всех листов новым сервисом
        s.expire_all()
        for sheet_id in sheets:
            sheet = await s.get(Sheet, sheet_id, populate_existing=True)
            recompute_sheet(sheet)
            for work in sheet.works:
                old = old_work_scores.get(work.id)
                if old is not None and work.score is not None and abs(_dec(old) - work.score) >= Decimal('0.01'):
                    self.report['score_changes'].append(
                        {'work_id': work.id, 'sheet_id': sheet.id, 'old': str(old), 'new': str(work.score)}
                    )
        await s.flush()

        self.report['counts'] = {
            'events': len(events),
            'applications': len(apps),
            'sheets': len(sheets),
            'works': len(works),
            'evaluations': len(evaluations),
            'items': len(pairs),
            'persons': len(self.person_ids),
            'judge_users': len(set(self.judge_users.values())),
        }
        self.report['skipped'] = {k: v for k, v in self.report['skipped'].items()}
        return self.report

    async def _member(self, event_id: int, user_id: int, role: str) -> None:
        exists = await self.session.scalar(
            select(EventMember.id).where(
                EventMember.event_id == event_id, EventMember.user_id == user_id, EventMember.role == role
            )
        )
        if not exists:
            self.session.add(EventMember(event_id=event_id, user_id=user_id, role=role))
            await self.session.flush()


async def load(session: AsyncSession, source: Path) -> dict:
    report = await Loader(session, source).run()
    (source / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report
