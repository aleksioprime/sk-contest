# Интеграция со SkolStream

SkolStream — платформа учебного процесса гимназии (`~/develop/skolstream`, Django + DRF, UUID-ключи).
Источник истины для учеников, сотрудников, классов и подразделений. Внешние участники ведутся в SK Events.

## Что берём

| SkolStream | Поля | SK Events |
|---|---|---|
| `users.User` | UUID, ФИО с отчеством, email, пол, `dnevnik_id`, `is_active`, группы-роли | `persons` (student, employee) + учётная запись |
| `academics.StudyGroup` | учебный год, параллель, буква, ученики, сотрудники | `classes`, `persons.current_class` |
| `users.Department` | название, академическое, сотрудники | `departments` |
| `academics.AcademicYear` | годы и периоды | привязка мероприятия к учебному году |
| `projects.Project` | название, описание, ученики, руководители, кафедры, файлы | источник работы при подаче заявки |
| `events.Event`, `EventParticipation` | уровень, этап, руководитель, результат, достижение | запись итогов в портфолио |

## Вход

- SkolStream — OAuth2-провайдер на `django-oauth-toolkit` (`/o/`), вместо стандартного токена выдаёт SimpleJWT (`core/oauth2.py`).
- SK Events регистрируется как приложение (authorization code). Обмен кода на токен идёт на backend, затем запрос профиля, поиск персоны по `skolstream_id`.
- OIDC не настроен (id_token закомментирован в `core/models.py`), поэтому профиль берём через API.

Нужно в SkolStream:
- [ ] зарегистрировать OAuth2-приложение SK Events (UAT и PROD), redirect `https://app.events.skolhub.ru/auth/skolstream/callback`;
- [ ] включить `PKCE_REQUIRED`;
- [ ] эндпоинт профиля текущего пользователя (если нет): id, ФИО, email, тип, класс, подразделения.

## Синхронизация

`JWTBackend` выдаёт токен только для пользователя, поэтому `client_credentials` не сработает. Варианты:

1. Служебный пользователь с правами только на чтение и обычные эндпоинты `user/`, `group/`, `department/employees/`, `year/`. Быстро, но зависит от пагинации и прав UI.
2. **Рекомендуется:** отдельный эндпоинт выгрузки `/api/integrations/v1/directory/?updated_since=` со статическим токеном. Отдаёт пользователей, классы, подразделения, связи одним срезом.

Правила:
- upsert по UUID, ночью и по кнопке;
- пропавшие в SkolStream записи получают `is_active=false` и не удаляются (на них ссылаются заявки и оценки);
- поля из SkolStream в SK Events только для чтения, локально редактируются только внешние персоны;
- внешнего, который позже появился в SkolStream, сливаем по email;
- роли SkolStream не переносим, права назначаются в SK Events.

## Портфолио

После публикации итогов worker создаёт в SkolStream `Event` (уровень `school`, учебный год, кафедры) с направлениями и этапами
и `EventParticipation` для каждого внутреннего участника: результат («Победитель», «Призёр», место, балл), руководитель, статус `confirmed`.
В SkolStream есть импорт `event/<id>/participations/import/`, формат нужно сверить.
