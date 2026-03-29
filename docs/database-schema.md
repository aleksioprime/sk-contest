# Структура базы данных

Описание таблиц NocoBase, используемых в приложении «Жюри SK».

---

## Конкурсы

### contests — Конкурсы

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `title` | string | Название конкурса |
| `description` | text | Описание |
| `files` | attachment | Файлы конкурса |

### contest_directions — Направления конкурса

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `contest_id` | FK → contests | Конкурс |
| `title` | string | Название направления |

### contest_stages — Этапы конкурса

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `contest_id` | FK → contests | Конкурс |
| `title` | string | Название этапа |
| `date_start` | date | Дата начала |
| `date_end` | date | Дата окончания |

### contest_performance_types — Формы защиты

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `contest_id` | FK → contests | Конкурс |
| `title` | string | Название формы защиты |

---

## Заявки

### contest_participations — Заявки

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `contest_id` | FK → contests | Конкурс |
| `title` | string | Название заявки |
| `direction_id` | FK → contest_directions | Направление |
| `supervisors` | M2M → persons | Руководители |
| `participants` | M2M → persons | Участники |

### contest_stage_participations — Заявки на этапах

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `participation_id` | FK → contest_participations | Заявка |
| `stage_id` | FK → contest_stages | Этап |
| `status` | string | Статус |
| `direction_id` | FK → contest_directions | Направление |

---

## Таблицы оценок и критерии

### contest_scorecards — Таблицы оценок

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `contest_id` | FK → contests | Конкурс |
| `title` | string | Название таблицы оценок |

### contest_scorecard_criteria — Критерии таблиц оценок

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `scorecard_id` | FK → contest_scorecards | Таблица оценок |
| `title` | string | Название критерия |
| `order` | integer | Порядок отображения |
| `scale_id` | FK → contest_criterion_scales | Шкала |
| `category_id` | FK → contest_criterion_categories | Категория |

### contest_criterion_categories — Категории критериев

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `scorecard_id` | FK → contest_scorecards | Таблица оценок |
| `title` | string | Название категории |
| `description` | text | Описание |

### contest_criterion_scales — Шкалы критериев

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `contest_id` | FK → contests | Конкурс |
| `title` | string | Название шкалы |

### contest_criterion_scale_levels — Уровни шкалы критериев

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `scale_id` | FK → contest_criterion_scales | Шкала |
| `title` | string | Название уровня |
| `point` | number | Баллы |
| `order` | integer | Порядок отображения |

---

## Оценочные листы и оценки

### contest_evaluation_sheets — Оценочные листы

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `contest_id` | FK → contests | Конкурс |
| `stage_id` | FK → contest_stages | Этап конкурса |
| `scorecard_id` | FK → contest_scorecards | Таблица оценок |
| `status` | string | Статус (`active` / `inactive` / `archived`) |
| `judges` | M2M → persons | Судьи оценочного листа |

### contest_evaluation_sheet_works — Работы оценочного листа

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `sheet_id` | FK → contest_evaluation_sheets | Оценочный лист |
| `stage_participation_id` | FK → contest_stage_participations | Работа на этапе |
| `score` | number | Итоговый балл |
| `rank` | integer | Место (ранг) |

### contest_evaluations — Оценки работ

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `sheet_work_id` | FK → contest_evaluation_sheet_works | Работа оценочного листа |
| `judge_id` | FK → persons | Судья (`person.id`, не `user.id`) |
| `score` | number | Итоговый балл судьи |
| `comment` | text | Общий комментарий к работе |

### contest_evaluation_items — Оценки работ по критериям

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор |
| `evaluation_id` | FK → contest_evaluations | Оценка работы |
| `criterion_id` | FK → contest_scorecard_criteria | Критерий |
| `level_id` | FK → contest_criterion_scale_levels | Выбранный уровень |
| `score` | number | Баллы за критерий |
| `comment` | text | Комментарий к критерию |

---

## Справочники

### persons — Персоны

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Идентификатор (используется как `judge_id` в оценках) |
| `user_id` | FK → users | Связанный пользователь NocoBase |
| `full_name` | string | Полное имя |
| `short_name` | string | Краткое имя |

---

## Связи между таблицами

```
contests
├── contest_directions
├── contest_stages
├── contest_performance_types
├── contest_participations
│   ├── participants (M2M → persons)
│   ├── supervisors (M2M → persons)
│   └── contest_stage_participations
├── contest_scorecards
│   ├── contest_scorecard_criteria
│   │   ├── category → contest_criterion_categories
│   │   └── scale → contest_criterion_scales
│   │       └── contest_criterion_scale_levels
│   └── contest_criterion_categories
├── contest_criterion_scales
│   └── contest_criterion_scale_levels
└── contest_evaluation_sheets
    ├── judges (M2M → persons)
    ├── scorecard → contest_scorecards
    └── contest_evaluation_sheet_works
        ├── stage_participation → contest_stage_participations
        └── contest_evaluations
            ├── judge → persons
            └── contest_evaluation_items
                ├── criterion → contest_scorecard_criteria
                └── level → contest_criterion_scale_levels
```
