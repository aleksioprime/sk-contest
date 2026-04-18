from __future__ import annotations

import asyncio
import time

from fastapi import HTTPException

from src.core.nocobase import nocobase


class AnonymousEvaluationService:
    CACHE_TTL_SECONDS = 300.0

    def __init__(self):
        self._context_cache: dict[str, dict] = {}

    @staticmethod
    def _key(value: int | str) -> str:
        return str(value)

    @staticmethod
    def _normalize_score(value) -> float | None:
        if value is None:
            return None
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None

    def _points_equal(self, left, right) -> bool:
        left_norm = self._normalize_score(left)
        right_norm = self._normalize_score(right)
        if left_norm is None and right_norm is None:
            return True
        if left_norm is None or right_norm is None:
            return False
        return abs(left_norm - right_norm) < 1e-9

    @staticmethod
    def _levels_equal(left, right) -> bool:
        if left is None and right is None:
            return True
        if left is None or right is None:
            return False
        return str(left) == str(right)

    def _cleanup_cache(self):
        now = time.monotonic()
        expired_tokens = [
            token
            for token, context in self._context_cache.items()
            if context.get('_expires_at', 0) <= now
        ]
        for token in expired_tokens:
            self._context_cache.pop(token, None)

    def _get_cached_context(self, token: str) -> dict | None:
        self._cleanup_cache()
        return self._context_cache.get(token)

    def _save_cached_context(self, token: str, context: dict):
        context['_expires_at'] = time.monotonic() + self.CACHE_TTL_SECONDS
        self._context_cache[token] = context

    async def _get_work_by_token(self, token: str) -> dict:
        work = await nocobase.get(
            'contest_evaluation_sheet_works',
            filter={'public_token': token},
            appends='stage_participation,stage_participation.participation,stage_participation.participation.participants,stage_participation.participation.supervisors',
            pageSize=1,
        )
        if not work:
            raise HTTPException(status_code=404, detail='Ссылка недействительна: работа не найдена')
        return work

    async def _get_sheet(self, sheet_id: int | str) -> dict:
        sheet = await nocobase.get_by_id('contest_evaluation_sheets', sheet_id)
        if not sheet:
            raise HTTPException(status_code=404, detail='Оценочный лист не найден')
        return sheet

    def _assert_sheet_allows_anonymous(self, sheet: dict):
        if not sheet.get('is_anonymous_enabled'):
            raise HTTPException(status_code=403, detail='Анонимная оценка для листа отключена')

        status = sheet.get('status')
        if status and status != 'active':
            raise HTTPException(status_code=403, detail='Лист недоступен для анонимной оценки')

    async def _get_anonymous_evaluation(self, sheet_work_id: int | str) -> dict | None:
        evaluations = await nocobase.list(
            'contest_evaluations',
            filter={'sheet_work_id': sheet_work_id, 'is_anonymous': True},
            sort='-id',
            pageSize=20,
        )
        if not isinstance(evaluations, list):
            return None

        for evaluation in evaluations:
            if evaluation.get('judge_id') is None:
                return evaluation

        return evaluations[0] if evaluations else None

    async def _create_anonymous_evaluation(self, sheet_work_id: int | str) -> dict:
        attempts = [
            {'sheet_work_id': sheet_work_id, 'is_anonymous': True},
            {'sheet_work': sheet_work_id, 'is_anonymous': True},
        ]

        last_error = None
        for payload in attempts:
            try:
                return await nocobase.create('contest_evaluations', payload)
            except HTTPException as exc:
                last_error = exc

        if last_error:
            raise last_error
        raise HTTPException(status_code=500, detail='Не удалось создать анонимную оценку')

    async def _ensure_context(self, token: str) -> dict:
        cached = self._get_cached_context(token)
        if cached and cached.get('work') and cached.get('sheet') and cached.get('evaluation'):
            return cached

        work = await self._get_work_by_token(token)
        sheet = await self._get_sheet(work['sheet_id'])
        self._assert_sheet_allows_anonymous(sheet)

        evaluation = await self._get_anonymous_evaluation(work['id'])
        if not evaluation:
            evaluation = await self._create_anonymous_evaluation(work['id'])

        context = {
            'work': work,
            'sheet': sheet,
            'evaluation': evaluation,
            'criteria': None,
            'criteria_by_id': {},
            'items_by_criterion': None,
            'levels_by_id': {},
            'categories': None,
            'levels': None,
        }
        self._save_cached_context(token, context)
        return context

    async def _get_criteria(self, scorecard_id: int | str) -> list[dict]:
        criteria = await nocobase.list(
            'contest_scorecard_criteria',
            filter={'scorecard_id': scorecard_id},
            sort='order,id',
            pageSize=1000,
        )
        return criteria if isinstance(criteria, list) else []

    async def _get_categories(self, category_ids: list[int | str]) -> list[dict]:
        if not category_ids:
            return []
        categories = await nocobase.list(
            'contest_criterion_categories',
            filter={'id': {'$in': category_ids}},
            sort='order,id',
            pageSize=1000,
        )
        return categories if isinstance(categories, list) else []

    async def _get_levels(self, scale_ids: list[int | str]) -> list[dict]:
        if not scale_ids:
            return []
        levels = await nocobase.list(
            'contest_criterion_scale_levels',
            filter={'scale_id': {'$in': scale_ids}},
            sort='order,id',
            pageSize=1000,
        )
        return levels if isinstance(levels, list) else []

    async def _get_items(self, evaluation_id: int | str) -> list[dict]:
        items = await nocobase.list(
            'contest_evaluation_items',
            filter={'evaluation_id': evaluation_id},
            sort='id',
            pageSize=2000,
        )
        return items if isinstance(items, list) else []

    async def _ensure_criteria(self, token: str, context: dict) -> list[dict]:
        if context.get('criteria') is not None:
            return context['criteria']

        criteria = await self._get_criteria(context['sheet']['scorecard_id'])
        context['criteria'] = criteria
        context['criteria_by_id'] = {
            self._key(criterion['id']): criterion
            for criterion in criteria
            if criterion.get('id') is not None
        }
        self._save_cached_context(token, context)
        return criteria

    async def _ensure_items(self, token: str, context: dict) -> dict[str, dict]:
        if context.get('items_by_criterion') is not None:
            return context['items_by_criterion']

        items = await self._get_items(context['evaluation']['id'])
        items_by_criterion: dict[str, dict] = {}
        for item in items:
            criterion_id = item.get('criterion_id')
            if criterion_id is None:
                continue
            items_by_criterion[self._key(criterion_id)] = item

        context['items_by_criterion'] = items_by_criterion
        self._save_cached_context(token, context)
        return items_by_criterion

    async def _get_criterion_from_context(self, token: str, context: dict, criterion_id: int) -> dict:
        await self._ensure_criteria(token, context)
        criterion = context['criteria_by_id'].get(self._key(criterion_id))
        if criterion:
            return criterion

        # Fallback for stale cache edge-case
        criterion = await nocobase.get(
            'contest_scorecard_criteria',
            filter={'id': criterion_id, 'scorecard_id': context['sheet']['scorecard_id']},
            pageSize=1,
        )
        if not criterion:
            raise HTTPException(status_code=404, detail='Критерий не найден в этом листе')

        context['criteria'] = (context.get('criteria') or []) + [criterion]
        context['criteria_by_id'][self._key(criterion['id'])] = criterion
        self._save_cached_context(token, context)
        return criterion

    async def _get_or_create_item(self, token: str, context: dict, criterion_id: int) -> dict:
        items_by_criterion = await self._ensure_items(token, context)
        criterion_key = self._key(criterion_id)

        existing = items_by_criterion.get(criterion_key)
        if existing:
            return existing

        attempts = [
            {'evaluation_id': context['evaluation']['id'], 'criterion_id': criterion_id},
            {'evaluation': context['evaluation']['id'], 'criterion': criterion_id},
        ]
        last_error = None
        for payload in attempts:
            try:
                created_item = await nocobase.create('contest_evaluation_items', payload)
                items_by_criterion[criterion_key] = created_item
                self._save_cached_context(token, context)
                return created_item
            except HTTPException as exc:
                last_error = exc

        if last_error:
            raise last_error
        raise HTTPException(status_code=500, detail='Не удалось создать строку критерия')

    async def _get_level_cached(self, token: str, context: dict, level_id: int) -> dict:
        level_key = self._key(level_id)
        cached_level = context.get('levels_by_id', {}).get(level_key)
        if cached_level:
            return cached_level

        level = await nocobase.get_by_id('contest_criterion_scale_levels', level_id)
        if not level:
            raise HTTPException(status_code=404, detail='Уровень шкалы не найден')

        levels_by_id = context.get('levels_by_id') or {}
        levels_by_id[self._key(level.get('id', level_id))] = level
        context['levels_by_id'] = levels_by_id
        self._save_cached_context(token, context)
        return level

    @staticmethod
    def _sorted_items(items_by_criterion: dict[str, dict]) -> list[dict]:
        return sorted(
            items_by_criterion.values(),
            key=lambda item: (str(item.get('id', '')), str(item.get('criterion_id', ''))),
        )

    async def get_bundle(self, token: str) -> dict:
        context = await self._ensure_context(token)
        criteria = await self._ensure_criteria(token, context)

        category_ids = sorted({criterion['category_id'] for criterion in criteria if criterion.get('category_id') is not None})
        scale_ids = sorted({criterion['scale_id'] for criterion in criteria if criterion.get('scale_id') is not None})

        categories_task = None
        levels_task = None

        if context.get('categories') is None:
            categories_task = asyncio.create_task(self._get_categories(category_ids))
        if context.get('levels') is None:
            levels_task = asyncio.create_task(self._get_levels(scale_ids))

        await self._ensure_items(token, context)

        tasks = [task for task in [categories_task, levels_task] if task is not None]
        if tasks:
            results = await asyncio.gather(*tasks)
            index = 0
            if categories_task is not None:
                context['categories'] = results[index]
                index += 1
            if levels_task is not None:
                context['levels'] = results[index]

        if context.get('levels'):
            levels_by_id = context.get('levels_by_id') or {}
            for level in context['levels']:
                if level.get('id') is not None:
                    levels_by_id[self._key(level['id'])] = level
            context['levels_by_id'] = levels_by_id

        self._save_cached_context(token, context)

        return {
            'token': token,
            'sheet': context['sheet'],
            'work': context['work'],
            'evaluation': context['evaluation'],
            'criteria': criteria,
            'categories': context.get('categories') or [],
            'levels': context.get('levels') or [],
            'items': self._sorted_items(context.get('items_by_criterion') or {}),
        }

    async def set_level(self, token: str, criterion_id: int, level_id: int | None) -> dict:
        context = await self._ensure_context(token)
        criterion = await self._get_criterion_from_context(token, context, criterion_id)
        item = await self._get_or_create_item(token, context, criterion_id)

        new_level_id = None
        new_score = None
        if level_id is not None:
            level = await self._get_level_cached(token, context, level_id)
            if criterion.get('scale_id') is not None and str(level.get('scale_id')) != str(criterion.get('scale_id')):
                raise HTTPException(status_code=400, detail='Уровень не относится к шкале этого критерия')
            new_level_id = level_id
            new_score = level.get('point')

        old_level_id = item.get('level_id')
        old_score = item.get('score')

        if self._levels_equal(old_level_id, new_level_id) and self._points_equal(old_score, new_score):
            return {'item': item, 'evaluation': context['evaluation']}

        updated_item = await nocobase.update(
            'contest_evaluation_items',
            item['id'],
            {'level_id': new_level_id, 'score': new_score},
        )

        item_merged = {**item, **updated_item, 'level_id': new_level_id, 'score': new_score}
        context['items_by_criterion'][self._key(criterion_id)] = item_merged

        self._save_cached_context(token, context)
        return {
            'item': item_merged,
            'evaluation': context['evaluation'],
        }

    async def set_item_comment(self, token: str, criterion_id: int, comment: str | None) -> dict:
        context = await self._ensure_context(token)
        await self._get_criterion_from_context(token, context, criterion_id)
        item = await self._get_or_create_item(token, context, criterion_id)

        updated_item = await nocobase.update(
            'contest_evaluation_items',
            item['id'],
            {'comment': comment},
        )

        item_merged = {**item, **updated_item, 'comment': comment}
        context['items_by_criterion'][self._key(criterion_id)] = item_merged
        self._save_cached_context(token, context)

        return {'item': item_merged}

    async def set_evaluation_comment(self, token: str, comment: str | None) -> dict:
        context = await self._ensure_context(token)

        updated_evaluation = await nocobase.update(
            'contest_evaluations',
            context['evaluation']['id'],
            {'comment': comment},
        )

        context['evaluation'] = {**context['evaluation'], **updated_evaluation, 'comment': comment}
        self._save_cached_context(token, context)
        return {'evaluation': context['evaluation']}


anonymous_evaluation_service = AnonymousEvaluationService()
