# Внедрение критериев типа Checklist (NocoBase + проект)

## Цель
Добавить в систему второй тип критерия оценивания:
- `scale` (текущий вариант): выбор одного уровня шкалы;
- `checklist` (новый вариант): выбор нескольких пунктов, где итоговый балл по критерию = сумма баллов выбранных пунктов.

Пример: критерий `Актуальность`, где есть набор пунктов `0/1`, и судья отмечает применимые пункты.

## 1) Изменения в NocoBase (модель данных)

### 1.1 `contest_scorecard_criteria`
Добавить поле:
- `type` (string/enum): `scale` | `checklist`, значение по умолчанию `scale`.

Смысл:
- для `type=scale` используется существующее поле `scale_id`;
- для `type=checklist` `scale_id` может быть пустым.

### 1.2 Новая коллекция `contest_scorecard_criterion_options`
Поля:
- `criterion_id` (belongsTo -> `contest_scorecard_criteria`)
- `title` (string)
- `point` (number)
- `order` (integer)
- `is_exclusive` (boolean, default `false`)

Назначение:
- хранит пункты чек-листа критерия;
- `is_exclusive=true` для взаимоисключающих пунктов (например, пункт `*0`).

### 1.3 `contest_evaluation_items`
Добавить связь:
- `selected_options` (manyToMany -> `contest_scorecard_criterion_options`).

Важно:
- в NocoBase промежуточная таблица для many-to-many создаётся автоматически;
- вручную создавать join-таблицу не требуется.

## 2) Правила бизнес-логики

### 2.1 Сохранение оценок
- `scale`: как сейчас, хранится `level_id` и `score = level.point`.
- `checklist`:
  - `level_id = null`;
  - `selected_options` = выбранные пункты;
  - `score` в `contest_evaluation_items` = сумма `point` выбранных пунктов.

### 2.2 Взаимоисключающие пункты
Если выбран пункт с `is_exclusive=true`:
- все прочие пункты этого критерия должны сниматься.

Если после этого выбран любой обычный пункт:
- exclusive-пункт должен сниматься.

### 2.3 Завершённость оценки
`evaluation.is_scored=true`, если по каждому критерию есть заполнение:
- для `scale`: выбран уровень;
- для `checklist`: выбран хотя бы один пункт.

## 3) Изменения в backend проекта

Файлы:
- `backend/src/services/anonymous_evaluation_service.py`
- judge/viewer API-ручки (если есть отдельные роуты для сохранения item).

Что добавить:
- загрузку `criterion.type` и options для checklist;
- метод сохранения выбранных options по критерию (`set_options` или `toggle_option`);
- пересчёт `contest_evaluation_items.score` после изменения выбора;
- валидацию:
  - option принадлежит текущему criterion;
  - criterion принадлежит scorecard текущего листа;
  - соблюдение `is_exclusive`;
- обновление расчёта `evaluation.score` и статусов `is_scored` после изменений.

## 4) Изменения во frontend проекта

### 4.1 Judge-экран (`EvaluationView.vue`)
- Если `criterion.type === "scale"`: оставляем текущий UI кнопок уровней.
- Если `criterion.type === "checklist"`:
  - показываем список чекбоксов с баллами;
  - отображаем сумму по критерию;
  - отправляем изменения через новый API (options).

### 4.2 Viewer-экран (`ViewerEvaluationView.vue`)
- Для checklist-критерия показывать:
  - выбранные пункты;
  - сумму баллов по критерию.

### 4.3 Анонимный режим (`AnonymousEvaluationView.vue`)
- Аналогично judge-режиму: поддержка выбора пунктов checklist и комментариев.

## 5) Совместимость и миграция

### 5.1 Обратная совместимость
- Все существующие критерии считать `type=scale` (дефолт).
- Текущие формы и листы продолжают работать без изменений.

### 5.2 Порядок внедрения
1. Добавить поля/коллекции/связи в NocoBase.
2. Реализовать backend-логику для checklist.
3. Добавить frontend-рендер checklist в judge/viewer/anonymous.
4. Протестировать смешанные scorecard (часть scale, часть checklist).
5. Включить для нужных конкурсов.

## 6) Проверки (чек-лист)
- Критерий `scale` работает как раньше.
- Критерий `checklist` суммирует выбранные пункты корректно.
- `is_exclusive` работает взаимно-исключающе.
- `evaluation.score` корректно пересчитывается.
- `work.score/rank` и отчёты не ломаются.
- Viewer и anonymous корректно отображают выбранные пункты.
