# Структура базы данных

**Конкурсы (contests):**
- Название (title)
- Описание (description)
- Файлы (files)

**Направления конкурса (contest_directions):**
- Конкурс (contest_id)
- Название (title)

**Этапы конкурса (contest_stages):**
- Конкурс (contest_id)
- Название (title)
- Дата начала (date_start)
- Дата окончания (date_end)

**Формы защиты (contest_performance_types):**
- Конкурс (contest_id)
- Название (title)

**Участники (contest_participations):**
- Конкурс (contest_id)
- Название (title)
- Супервайзеры (supervisors) - ManyToMany к persons
- Участники (participants) - ManyToMany к persons
- Направление (direction_id)
- Внешний участник (is_external)
- Примечание (notes)

**Участники на этапах (contest_stage_participations):**
- Участник (participation_id)
- Этап (stage_id)
- Направление (direction_id)
- Статус (status)
- Название (title)

**Таблицы оценок (contest_scorecards):**
- Конкурс (contest_id)
- Название (title)

**Критерии таблиц оценок (contest_scorecard_criteria):**
- Таблица оценок (scorecard_id)
- Название (title)
- Порядок (order)
- Шкала (scale_id)
- Категория (category_id)
- Описание (description)

**Категории критериев (contest_criterion_categories):**
- Таблица оценок (scorecard_id)
- Название (title)
- Порядок (order)

**Шкалы критериев (contest_criterion_scales):**
- Конкурс (contest_id)
- Название (title)

**Уровни шкалы критериев (contest_criterion_scale_levels):**
- Шкала (scale_id)
- Название (title)
- Баллы (point)
- Порядок (order)

**Оценочные листы (contest_evaluation_sheets):**
- Конкурс (contest_id)
- Этап конкурса (stage_id)
- Судьи (judges) - ManyToMany к persons
- Наблюдатели (observers) - ManyToMany к persons
- Таблица оценок (scorecard_id)
- Название (title)
- Статус (status):
    - active - Активный
    - inactive - Неактивный
    - archived - Архивный
- Анонимная оценка (is_anonymous_enabled)

**Работы оценочного листа (contest_evaluation_sheet_works):**
- Оценочный лист (sheet_id)
- Работа на этапе конкурса (stage_participation_id)
- Публичный токен (public_token)
- Баллы (score)
- Ранг (rank)
- Порядок (order)
- Оценено (is_scored)

**Оценки работ (contest_evaluations):**
- Работа оценочного листа (sheet_work_id)
- Судья (judge_id)
- Анонимная оценка (is_anonymous)
- Баллы (score)
- Комментарий (comment)
- Оценено (is_scored)

**Оценки работ по критериям (contest_evaluation_items):**
- Оценка работы (evaluation_id)
- Критерий (criterion_id)
- Уровень (level_id)
- Баллы (score)
- Комментарий (comment)