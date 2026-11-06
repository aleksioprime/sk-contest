"""Типы мероприятий: набор модулей, этапы и формы участия по умолчанию (docs/event-types.md)."""

MODULES = ('registration', 'stages', 'evaluation', 'results')

STATUSES = {
    'draft': 'Черновик',
    'registration': 'Регистрация',
    'running': 'Идёт',
    'results': 'Итоги',
    'archived': 'Архив',
}

# Из какого статуса в какие можно перейти
TRANSITIONS = {
    'draft': {'registration', 'running'},
    'registration': {'draft', 'running'},
    'running': {'registration', 'results'},
    'results': {'running', 'archived'},
    'archived': {'results'},
}

LEVELS = ('school', 'municipal', 'regional', 'national', 'international')
FORMATS = ('onsite', 'online', 'hybrid')
ROLES = ('organizer', 'moderator', 'judge', 'observer')


# Стартовое наполнение нового мероприятия; всё можно изменить в настройках
DEFAULT_STAGES = (('Заочный этап', 'remote'), ('Очная защита', 'onsite'))
DEFAULT_PARTICIPATION_FORMS = ('Устная защита', 'Стендовая защита')
LISTENER_PARTICIPATION_FORMS = ('Слушатель',)


def only_registration(modules: dict[str, bool]) -> bool:
    """Нужна только запись на событие: этапов, оценивания и итогов нет, анкета после подтверждения не требуется."""
    return not any(modules.get(module) for module in MODULES if module != 'registration')
