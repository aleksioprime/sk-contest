from datetime import datetime

from pydantic import BaseModel, Field


class MemberIn(BaseModel):
    role: str = Field(pattern='^(participant|supervisor)$')
    full_name: str = Field(min_length=1, max_length=300)
    email: str = Field(default='', max_length=255)
    grade: str = Field(default='', max_length=20)
    organization: str = Field(default='', max_length=300)


class MemberOut(MemberIn):
    id: int
    person_id: int | None


class ApplicationSave(BaseModel):
    title: str = Field(default='', max_length=300)
    direction_id: int | None = None
    participation_form_id: int | None = None
    answers: dict = {}
    members: list[MemberIn] = []
    consents: list[str] = []


class FileRef(BaseModel):
    id: int
    name: str
    size: int
    url: str
    field_key: str


class ConsentOut(BaseModel):
    key: str
    version: str
    title: str
    accepted_at: datetime


class Ref(BaseModel):
    id: int
    title: str


class EventRef(BaseModel):
    id: int
    slug: str
    title: str


class ApplicationOut(BaseModel):
    id: int
    number: int
    event: EventRef
    status: str
    title: str
    direction: Ref | None
    participation_form: Ref | None
    answers: dict
    members: list[MemberOut]
    consents: list[ConsentOut]
    files: list[FileRef]
    moderator_comment: str
    applicant_email: str
    applicant_name: str
    created_at: datetime
    submitted_at: datetime | None
    decided_at: datetime | None
    can_edit: bool = False
    can_submit: bool = False
    can_withdraw: bool = False


class ApplicationListItem(BaseModel):
    id: int
    number: int
    title: str
    status: str
    direction: str
    participants: list[str]
    supervisors: list[str]
    applicant_email: str
    submitted_at: datetime | None


class ApplicationPage(BaseModel):
    items: list[ApplicationListItem]
    total: int
    counts: dict[str, int]


class Decision(BaseModel):
    status: str = Field(pattern='^(accepted|needs_changes|rejected|submitted)$')
    comment: str = Field(default='', max_length=5000)


class BulkDecision(Decision):
    ids: list[int] = Field(min_length=1, max_length=500)


class PublicForm(BaseModel):
    event: EventRef
    form: dict
    directions: list[Ref]
    participation_forms: list[Ref]
    registration_open: bool
    registration_closes_at: datetime | None
