"""Типы мероприятий: набор модулей, этапы и формы участия по умолчанию (docs/event-types.md)."""

MODULES = ('landing', 'registration', 'stages', 'evaluation', 'results')

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


def _modules(*enabled: str) -> dict[str, bool]:
    return {module: module in enabled for module in MODULES}


EVENT_TYPES = {
    'project_contest': {
        'title': 'Конкурс проектов',
        'description': 'Заявки с работами, жюри по критериям, этапы и итоговый рейтинг',
        'modules': _modules('landing', 'registration', 'stages', 'evaluation', 'results'),
        'stages': [('Заочный этап', 'remote'), ('Очная защита', 'onsite')],
        'participation_forms': ['Устная защита', 'Стендовая защита'],
    },
    'conference': {
        'title': 'Конференция',
        'description': 'Секции, доклады и слушатели, программа и сертификаты',
        'modules': _modules('landing', 'registration', 'stages', 'results'),
        'stages': [('Приём тезисов', 'remote'), ('Конференция', 'onsite')],
        'participation_forms': ['Доклад', 'Стендовый доклад', 'Слушатель'],
    },
    'creative': {
        'title': 'Творческий конкурс',
        'description': 'Работы в медиа, жюри и зрительское голосование',
        'modules': _modules('landing', 'registration', 'evaluation', 'results'),
        'stages': [('Приём работ', 'remote')],
        'participation_forms': ['Индивидуальная работа', 'Коллективная работа'],
    },
    'open_event': {
        'title': 'Открытое событие',
        'description': 'Лекция, мастер-класс или день открытых дверей с регистрацией слушателей',
        'modules': _modules('landing', 'registration'),
        'stages': [],
        'participation_forms': ['Слушатель'],
    },
    'selection': {
        'title': 'Отбор',
        'description': 'Анкета, оценка комиссией и собеседование',
        'modules': _modules('landing', 'registration', 'stages', 'evaluation', 'results'),
        'stages': [('Анкета', 'remote'), ('Собеседование', 'onsite')],
        'participation_forms': [],
    },
}
