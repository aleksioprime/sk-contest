"""Схемы оценки: шкалы, таблицы оценок, листы, судьи и оценивание."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ORM(BaseModel):
    """Базовая схема для ответов, создаваемых из ORM-объектов."""

    model_config = ConfigDict(from_attributes=True)


# --- Шкалы и таблицы -------------------------------------------------------------------------


class LevelIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    points: Decimal = Field(ge=-1000, le=1000)


class LevelOut(ORM, LevelIn):
    id: int


class ScaleIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    levels: list[LevelIn] = Field(min_length=2, max_length=20)


class ScaleOut(ORM):
    id: int
    title: str
    levels: list[LevelOut]


class OptionIn(BaseModel):
    """Пункт чек-листа: баллы и признак взаимоисключающего пункта."""

    title: str = Field(min_length=1, max_length=300)
    points: Decimal = Field(ge=-1000, le=1000)
    is_exclusive: bool = False


class OptionOut(ORM, OptionIn):
    id: int


class CriterionIn(BaseModel):
    """Критерий таблицы оценок: шкала или чек-лист, вес и индекс категории."""

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default='', max_length=5000)
    type: str = Field(default='scale', pattern='^(scale|checklist)$')
    scale_id: int | None = None
    weight: Decimal = Field(default=Decimal(1), gt=0, le=100)
    category: int | None = Field(default=None, description='Номер категории в списке categories, с нуля')
    options: list[OptionIn] = []

    @model_validator(mode='after')
    def _kind(self):
        """Требует шкалу для критерия-шкалы и пункты для чек-листа."""
        if self.type == 'scale' and self.scale_id is None:
            raise ValueError(f'Для критерия «{self.title}» выберите шкалу')
        if self.type == 'checklist' and not self.options:
            raise ValueError(f'В чек-листе «{self.title}» нет пунктов')
        return self


class ScorecardIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    categories: list[str] = []
    criteria: list[CriterionIn] = Field(default=[], max_length=100)

    @model_validator(mode='after')
    def _categories(self):
        """Проверяет, что индексы категорий критериев существуют."""
        for criterion in self.criteria:
            if criterion.category is not None and not 0 <= criterion.category < len(self.categories):
                raise ValueError(f'У критерия «{criterion.title}» неизвестная категория')
        return self


class CategoryOut(ORM):
    id: int
    title: str


class CriterionOut(ORM):
    id: int
    title: str
    description: str
    type: str
    scale_id: int | None
    weight: Decimal
    category_id: int | None
    scale: ScaleOut | None
    options: list[OptionOut]


class ScorecardOut(ORM):
    id: int
    title: str
    categories: list[CategoryOut]
    criteria: list[CriterionOut]
    max_score: Decimal = Decimal(0)
    in_use: bool = False


# --- Листы -----------------------------------------------------------------------------------


class SheetBase(BaseModel):
    """Общие настройки листа: режим, способ подсчёта и ранжирования, дедлайн."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    stage_id: int | None = None
    mode: str | None = Field(default=None, pattern='^(jury|anonymous|mixed)$')
    aggregate: str | None = Field(default=None, pattern='^(avg|sum|median)$')
    rank_method: str | None = Field(default=None, pattern='^(competition|dense)$')
    rank_scope: str | None = Field(default=None, pattern='^(overall|direction)$')
    include_anonymous: bool | None = None
    deadline: datetime | None = None


class SheetCreate(SheetBase):
    title: str = Field(min_length=1, max_length=200)
    scorecard_id: int


class SheetUpdate(SheetBase):
    scorecard_id: int | None = None


class JudgeOut(BaseModel):
    user_id: int
    email: str | None
    full_name: str
    has_password: bool = False
    total: int
    scored: int
    reopened: bool


class JudgeAccess(BaseModel):
    """Открыт ли судье доступ к закрытому листу."""

    open: bool


class RemindResult(BaseModel):
    """Итог рассылки напоминаний: отправлено и без email."""

    sent: int
    no_email: int = Field(description='Судьи без email: им напоминание не ушло')


class JudgeCardsRequest(BaseModel):
    """Судьи, для которых нужны карточки входа."""

    user_ids: list[int] | None = None


class JudgeCard(BaseModel):
    """Карточка входа судьи по QR: ссылка, срок действия и работы для оценки."""

    user_id: int
    full_name: str
    login_url: str
    expires_at: datetime
    works: int


class WorkOut(BaseModel):
    id: int
    application_id: int
    number: int
    title: str
    direction: str
    participants: list[str]
    public_token: str
    score: Decimal | None
    rank: int | None
    is_scored: bool
    evaluations_total: int
    evaluations_scored: int
    anonymous_count: int


class SheetOut(BaseModel):
    id: int
    event_id: int
    stage_id: int | None
    scorecard_id: int
    scorecard_title: str
    title: str
    status: str
    mode: str
    aggregate: str
    rank_method: str
    rank_scope: str
    include_anonymous: bool
    deadline: datetime | None
    judges: list[JudgeOut]
    works: list[WorkOut]


class SheetListItem(BaseModel):
    """Лист в списке: число работ и судей, прогресс оценивания."""

    id: int
    title: str
    status: str
    mode: str
    works: int
    judges: int
    progress: int


class AddWorks(BaseModel):
    """Добавление работ в лист: источник и фильтры по заявкам, номерам, направлениям и статусам."""

    source: str = Field(default='accepted', pattern='^(accepted|stage)$', description='stage — участники этапа листа')
    application_ids: list[int] | None = None
    numbers: list[int] | None = Field(
        default=None, max_length=1000, description='Номера заявок, например работы одного дня'
    )
    direction_ids: list[int] | None = None
    statuses: list[str] = ['accepted']


class JudgeIn(BaseModel):
    """Судья, добавляемый в лист: существующий пользователь или новый по ФИО и email."""

    user_id: int | None = Field(default=None, description='Существующий пользователь из базы')
    full_name: str = Field(default='', max_length=300)
    email: EmailStr | None = None
    password: str | None = Field(
        default=None, min_length=8, max_length=200, description='Пароль для входа; задаётся только новым судьям'
    )

    @model_validator(mode='after')
    def _identity(self):
        """Нормализует ФИО и требует ФИО или email для нового судьи."""
        self.full_name = ' '.join(self.full_name.split())
        if not self.user_id and not self.full_name and not self.email:
            raise ValueError('Укажите ФИО или email судьи')
        return self


class UserSearchItem(BaseModel):
    """Пользователь в результатах поиска судей."""

    id: int
    full_name: str
    email: str | None
    has_password: bool


class SetJudges(BaseModel):
    """Новый состав судей листа; force разрешает удалить уже выставленные оценки."""

    judges: list[JudgeIn] = Field(max_length=200)
    force: bool = Field(default=False, description='Удалить и выставленные оценки убираемых судей')


class Distribute(BaseModel):
    """Способ распределения работ между судьями."""

    mode: str = Field(pattern='^(all|per_work)$')
    per_work: int = Field(default=3, ge=1, le=50)


class SheetStatus(BaseModel):
    status: str = Field(pattern='^(draft|active|closed)$')


# --- Оценка ----------------------------------------------------------------------------------


class CriterionValue(BaseModel):
    """Значение критерия, выставленное судьёй: уровень шкалы или пункты чек-листа; clear сбрасывает."""

    level_id: int | None = None
    option_ids: list[int] | None = None
    comment: str | None = Field(default=None, max_length=5000)
    clear: bool = False


class EvaluationComment(BaseModel):
    comment: str = Field(default='', max_length=10000)


class ItemOut(BaseModel):
    """Сохранённая оценка по критерию."""

    criterion_id: int
    level_id: int | None
    option_ids: list[int]
    score: Decimal | None
    comment: str


class MySheet(BaseModel):
    """Лист в кабинете судьи с прогрессом."""

    id: int
    title: str
    status: str
    editable: bool
    deadline: datetime | None
    event_title: str
    total: int
    scored: int


class JudgeWork(BaseModel):
    """Работа в списке судьи с его оценкой."""

    evaluation_id: int
    number: int
    title: str
    direction: str
    participants: list[str]
    score: Decimal | None
    is_scored: bool


class WorkInfo(BaseModel):
    """Сведения о работе для судьи: участники, ответы анкеты и файлы."""

    number: int
    title: str
    direction: str
    participation_form: str
    participants: list[str]
    supervisors: list[str]
    answers: list[dict] = []
    files: list[dict] = []


class EvaluationBundle(BaseModel):
    """Всё для экрана оценки: работа, таблица, выставленные значения и соседние работы."""

    evaluation_id: int
    sheet_id: int
    sheet_title: str
    event_title: str
    editable: bool
    work: WorkInfo
    scorecard: ScorecardOut
    items: list[ItemOut]
    score: Decimal | None
    is_scored: bool
    comment: str
    anonymous_name: str = ''
    prev_id: int | None = None
    next_id: int | None = None


class AnonymousStart(BaseModel):
    """Начало анонимной оценки: имя оценщика."""

    name: str = Field(default='', max_length=100)

    @field_validator('name')
    @classmethod
    def _strip(cls, value: str) -> str:
        """Убирает пробелы по краям имени."""
        return value.strip()


class AnonymousStarted(BaseModel):
    """Результат начала анонимной оценки: токен и оценка."""

    token: str
    evaluation: EvaluationBundle


class PublicWork(BaseModel):
    """Работа по публичной ссылке с признаком открытого оценивания."""

    sheet_title: str
    event_title: str
    open: bool
    work: WorkInfo
