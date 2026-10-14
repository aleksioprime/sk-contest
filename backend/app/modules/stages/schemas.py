from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class SlotIn(BaseModel):
    title: str = Field(default='', max_length=200)
    room: str = Field(default='', max_length=100)
    starts_at: datetime
    ends_at: datetime | None = None

    @model_validator(mode='after')
    def _order(self):
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError('Окончание слота раньше начала')
        return self


class SlotOut(SlotIn):
    id: int
    participants: int = 0


class ParticipantOut(BaseModel):
    id: int
    application_id: int
    number: int
    title: str
    direction: str
    direction_id: int | None
    participants: list[str]
    status: str
    score: Decimal | None
    rank: int | None
    slot_id: int | None
    slot_order: int
    note: str
    proposal: str | None = None


class ParticipantUpdate(BaseModel):
    status: str | None = Field(default=None, pattern='^(admitted|scheduled|evaluated|passed|not_passed|withdrawn)$')
    slot_id: int | None = None
    slot_order: int | None = None
    note: str | None = Field(default=None, max_length=2000)
    clear_slot: bool = False


class StageRule(BaseModel):
    type: str = Field(default='manual', pattern='^(top_n|threshold|manual)$')
    n: int | None = Field(default=None, ge=1)
    per_direction: bool = True
    threshold: Decimal | None = None
    rank_scope: str = Field(default='direction', pattern='^(direction|overall)$')
    score_combine: str = Field(default='avg', pattern='^(avg|sum|max)$')


class StageOverview(BaseModel):
    stage_id: int
    title: str
    rule: StageRule
    has_next: bool
    next_title: str | None
    participants: list[ParticipantOut]
    slots: list[SlotOut]


class AdvanceApply(BaseModel):
    decisions: dict[int, str]


class Nomination(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    application_ids: list[int] = Field(default=[], max_length=200)


class Awards(BaseModel):
    # direction — места и награды в каждом направлении; overall — один общий рейтинг
    rank_scope: str = Field(default='direction', pattern='^(direction|overall)$')
    nominations: list[Nomination] = Field(default=[], max_length=50)
    winners: int = Field(default=1, ge=0, le=10)
    prize_places: int = Field(default=3, ge=0, le=20)
    stage_id: int | None = None
    signatory: str = Field(default='', max_length=200)
    signatory_title: str = Field(default='', max_length=200)
    date_text: str = Field(default='', max_length=100)

    @model_validator(mode='after')
    def _places(self):
        if self.prize_places < self.winners:
            raise ValueError('Призовых мест не может быть меньше числа победителей')
        return self


class ResultRow(BaseModel):
    application_id: int
    number: int
    title: str
    direction: str
    participants: list[str]
    score: Decimal | None
    rank: int | None
    award: str
    nominations: list[str] = []


class EventResults(BaseModel):
    published_at: datetime | None
    stage_id: int | None
    awards: Awards
    rows: list[ResultRow]


class PublicWinner(BaseModel):
    rank: int | None
    award: str
    title: str
    participants: list[str]


class PublicDirectionResults(BaseModel):
    direction: str
    winners: list[PublicWinner]
    nomination: bool = False
