# Старая система: NocoBase

Аудит 13.10.2026 (`flow.skolhub.ru`, только чтение). Код фронтенда и BFF — ветка `archive/nocobase-v1`.
Документ нужен для переноса данных и чтобы новый подсчёт повторял старые формулы, но без их ошибок.

## Объём

Инстанс общий с опросами, тестами и нагрузкой учителей: 59 коллекций, конкурсам принадлежат 19.

| Сущность | Записей |
|---|---|
| contests | 4 |
| contest_stages / directions | 6 / 12 |
| contest_participations | 281 (86 внешних) |
| contest_stage_participations | 72 (все `accepted`) |
| contest_scorecards / criteria | 8 / 66 (не больше 12 на таблицу) |
| contest_evaluation_sheets | 24 (23 в архиве) |
| contest_evaluation_sheet_works | 325 (235 без `stage_participation_id`) |
| contest_evaluations | 3 111 (1 812 анонимных) |
| contest_evaluation_items | 22 604 |
| persons / users | 1 305 / 305; 1 046 персон с `skolstream_id` |

## Модель

Как в `docs/database.md` архивной ветки, плюс:
- `contest_evaluation_sheet_works.stage_participation_id`, `is_scored`;
- `contest_participations.project_id → projects` (коллекция пуста);
- `contest_stage_participations.status`: accepted, evaluated, passed, not_passed;
- `persons`: `type[]` (student, employee, external), `skolstream_id`, `dnevnik_id`, `current_class_id`, `departments`;
- m2m через junction-таблицы: судьи листа `t_1jhfpv4gumn`, наблюдатели `t_u2bo69j8mu1`, участники заявки `t_j8t7dujoabi`, руководители `t_c17vqug5s15`;
- брошенные junction-таблицы `t_o0dvifansya`, `t_qxqhd8rzdm1`.

ID — snowflake `bigint` (около 3,6·10¹⁴, укладываются в безопасный диапазон JS).

## Формулы из workflows

| Что | Формула |
|---|---|
| Балл критерия, scale | `item.score = level.point` |
| Балл критерия, checklist | `item.score = Σ option.point`, нет выбранных → `null` |
| Оценка судьи | `evaluation.score = Σ item.score` по заполненным; `is_scored` = все items заполнены |
| Балл работы | `work.score = round(avg(evaluation.score where is_scored), 2)`; `work.is_scored` = все оценки `is_scored` |
| Ранг | по убыванию `score`, стандартный 1-1-3; при равенстве порядок не определён |

Автоматические действия:
- работа добавлена в лист → оценка на каждого судьи листа + `public_token` (8 символов `Math.random`);
- оценка создана → пустой item на каждый критерий таблицы.

## Ошибки, которые нельзя переносить

- Узлы «Выбрать записи» ограничены `pageSize: 20`. У 36 работ больше 20 оценок, у 24 из них балл посчитан по первым 20 (расхождение до 0,33). При импорте баллы пересчитывать заново.
- Автоматический ранг выключен, у 54 оценённых работ ранга нет. Фронтенд считал плотный ранг 1-1-2 с разбивкой по `order`.
- Кнопка «Удаление нулевых ответов» удаляла оценки с баллом 0 без журнала.

## Перенос

- Переносить только конкурсные коллекции и персоны, на которые они ссылаются.
- Сохранять ID. Персоны сопоставлять со SkolStream по `skolstream_id`, внешних — по email и ФИО.
- После импорта пересчитать `evaluation.score`, `work.score`, `rank` новым сервисом и сохранить отчёт о расхождениях.
- Доступ к БД: контейнер `postgres-sqmxcid4dudu798swhzfnwbw` на сервере Coolify; API: ключ в `NOCOBASE_API_KEY`.
