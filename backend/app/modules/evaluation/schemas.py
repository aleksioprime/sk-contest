from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ORM(BaseModel):
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
    title: str = Field(min_length=1, max_length=300)
    points: Decimal = Field(ge=-1000, le=1000)
    is_exclusive: bool = False


class OptionOut(ORM, OptionIn):
    id: int


class CriterionIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default='', max_length=5000)
    type: str = Field(default='scale', pattern='^(scale|checklist)$')
    scale_id: int | None = None
    weight: Decimal = Field(default=Decimal(1), gt=0, le=100)
    category: int | None = Field(default=None, description='Номер категории в списке categories, с нуля')
    options: list[OptionIn] = []

    @model_validator(mode='after')
    def _kind(self):
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
    title: str | None = Field(default=None, min_length=1, max_length=200)
    stage_id: int | None = None
    mode: str | None = Field(default=None, pattern='^(jury|anonymous|mixed)$')
    aggregate: str | None = Field(default=None, pattern='^(avg|sum|median)$')
    rank_method: str | None = Field(default=None, pattern='^(competition|dense)$')
    include_anonymous: bool | None = None
    deadline: datetime | None = None


class SheetCreate(SheetBase):
    title: str = Field(min_length=1, max_length=200)
    scorecard_id: int


class SheetUpdate(SheetBase):
    scorecard_id: int | None = None


class JudgeOut(BaseModel):
    user_id: int
    email: str
    full_name: str
    total: int
    scored: int


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
    include_anonymous: bool
    deadline: datetime | None
    judges: list[JudgeOut]
    works: list[WorkOut]


class SheetListItem(BaseModel):
    id: int
    title: str
    status: str
    mode: str
    works: int
    judges: int
    progress: int


class AddWorks(BaseModel):
    application_ids: list[int] | None = None
    direction_ids: list[int] | None = None
    statuses: list[str] = ['accepted']


class SetJudges(BaseModel):
    emails: list[EmailStr] = Field(max_length=200)
    force: bool = Field(default=False, description='Удалить и выставленные оценки убираемых судей')


class Distribute(BaseModel):
    mode: str = Field(pattern='^(all|per_work)$')
    per_work: int = Field(default=3, ge=1, le=50)


class SheetStatus(BaseModel):
    status: str = Field(pattern='^(draft|active|closed)$')


# --- Оценка ----------------------------------------------------------------------------------


class CriterionValue(BaseModel):
    level_id: int | None = None
    option_ids: list[int] | None = None
    comment: str | None = Field(default=None, max_length=5000)
    clear: bool = False


class EvaluationComment(BaseModel):
    comment: str = Field(default='', max_length=10000)


class ItemOut(BaseModel):
    criterion_id: int
    level_id: int | None
    option_ids: list[int]
    score: Decimal | None
    comment: str


class MySheet(BaseModel):
    id: int
    title: str
    status: str
    deadline: datetime | None
    event_title: str
    total: int
    scored: int


class JudgeWork(BaseModel):
    evaluation_id: int
    number: int
    title: str
    direction: str
    participants: list[str]
    score: Decimal | None
    is_scored: bool


class WorkInfo(BaseModel):
    number: int
    title: str
    direction: str
    participation_form: str
    participants: list[str]
    supervisors: list[str]
    answers: list[dict] = []
    files: list[dict] = []


class EvaluationBundle(BaseModel):
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
    name: str = Field(default='', max_length=100)

    @field_validator('name')
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class AnonymousStarted(BaseModel):
    token: str
    evaluation: EvaluationBundle


class PublicWork(BaseModel):
    sheet_title: str
    event_title: str
    open: bool
    work: WorkInfo
