# Интеграция со SkolStream

SkolStream — платформа учебного процесса гимназии (`~/develop/skolstream`, Django + DRF, UUID-ключи).
Источник истины для учеников, сотрудников, классов и подразделений. Внешние участники ведутся в SK Contest.

## Что берём

| SkolStream | Поля | SK Contest |
|---|---|---|
| `users.User` | UUID, ФИО с отчеством, email, пол, `dnevnik_id`, `is_active`, группы-роли | `persons` (student, employee) + учётная запись |
| `academics.StudyGroup` | учебный год, параллель, буква, ученики, сотрудники | `classes`, `persons.current_class` |
| `users.Department` | название, академическое, сотрудники | `departments` |
| `academics.AcademicYear` | годы и периоды | привязка мероприятия к учебному году |
| `projects.Project` | название, описание, ученики, руководители, кафедры, файлы | источник работы при подаче заявки |
| `events.Event`, `EventParticipation` | уровень, этап, руководитель, результат, достижение | запись итогов в портфолио |

## Вход

- SkolStream — OAuth2-провайдер на `django-oauth-toolkit` (`/o/`), вместо стандартного токена выдаёт SimpleJWT (`core/oauth2.py`).
- SK Contest регистрируется как приложение (authorization code). Обмен кода на токен идёт на backend, затем запрос профиля, поиск персоны по `skolstream_id`.
- OIDC не настроен (id_token закомментирован в `core/models.py`), поэтому профиль берём через API.

Настройка (подробно — `docs/guides/dev/oauth-apps.md` в SkolStream):
- [ ] OAuth2-приложение SK Contest в админке SkolStream: Confidential, Authorization code,
      redirect `https://contest.skolhub.ru/api/v1/auth/skolstream/callback`, включить «Skip authorization»;
- [ ] в Coolify: `SKOLSTREAM__CLIENT_ID`, `SKOLSTREAM__CLIENT_SECRET` (`SKOLSTREAM__BASE_URL` по умолчанию `https://skolstream.sk.ru`).

SK Contest запрашивает только `scope=read`, передаёт PKCE и представляется
`SK-Contest/1.0 (+<APP_URL>)`: шлюз перед SkolStream отклоняет типовые заголовки библиотек.
Вход запрещён персонам, отключённым в SkolStream (`is_active=false` после синхронизации), кроме
администраторов SK Contest — ошибка синхронизации не должна запереть их снаружи.

## Синхронизация

Выгрузка справочника SkolStream — `GET /api/v1/integrations/directory/` со служебным токеном
(`docs/guides/dev/directory-export.md` в SkolStream). Токен создаётся в админке SkolStream
(«Токены выгрузки справочника»), в Coolify — `SKOLSTREAM__DIRECTORY_TOKEN`.

Расписание (`backend/app/workers/main.py`, `people/sync.py`):
- изменения — каждые 10 минут, от `generated_at` прошлого ответа SkolStream (его часы);
- полный срез — ночью в 03:00: отключает пропавших, чистит журнал запусков старше 30 дней;
- по кнопке в разделе «Люди»;
- запуск, висящий дольше 30 минут, считается оборвавшимся и не блокирует следующие;
- полный срез с пустым списком пользователей никого не отключает (вероятный сбой SkolStream).

Правила:
- upsert по UUID;
- пропавшие в SkolStream записи получают `is_active=false` и не удаляются (на них ссылаются заявки и оценки);
- поля из SkolStream в SK Contest только для чтения, локально редактируются только внешние персоны;
- внешнего, который позже появился в SkolStream, сливаем по email;
- роли SkolStream не переносим, права назначаются в SK Contest.

## Портфолио

После публикации итогов worker создаёт в SkolStream `Event` (уровень `school`, учебный год, кафедры) с направлениями и этапами
и `EventParticipation` для каждого внутреннего участника: результат («Победитель», «Призёр», место, балл), руководитель, статус `confirmed`.
В SkolStream есть импорт `event/<id>/participations/import/`, формат нужно сверить.

## Контракт выгрузки справочников

SK Contest вызывает `GET {SKOLSTREAM__BASE_URL}/api/v1/integrations/directory/` с заголовком
`Authorization: Token {SKOLSTREAM__DIRECTORY_TOKEN}`. Параметр `updated_since` (ISO 8601) — только изменённые записи;
без него — полный срез. Клиент: `backend/app/modules/people/skolstream.py`, применение: `apply_directory` в
`backend/app/modules/people/service.py`.

```json
{
  "academic_years": [
    {"id": "uuid", "name": "2026/2027", "is_current": true, "date_start": "2026-09-01", "date_end": "2027-06-30"}
  ],
  "classes": [
    {"id": "uuid", "academic_year_id": "uuid", "grade": 9, "letter": "А", "name": "9А"}
  ],
  "departments": [
    {"id": "uuid", "name": "Кафедра естественных наук"}
  ],
  "users": [
    {
      "id": "uuid",
      "email": "ivanova@example.ru",
      "last_name": "Иванова", "first_name": "Анна", "middle_name": "Сергеевна",
      "gender": "female",
      "is_active": true,
      "is_student": true,
      "is_employee": false,
      "class_ids": ["uuid"],
      "department_ids": []
    }
  ]
}
```

Поведение SK Contest:
- запись ищется по `id` (UUID SkolStream), поля перезаписываются;
- при полном срезе пользователи, классы и подразделения, которых нет в ответе, помечаются неактивными;
- внешние участники (зарегистрированные по email) синхронизацией не затрагиваются;
- результат каждого запуска сохраняется в `sync_runs` и виден в разделе «Люди».

Профиль при входе берётся из `GET /api/v1/user/me`: используются `id`, `email`, ФИО, `gender`, `is_student`,
`is_employee`, `student_groups[].id`.
