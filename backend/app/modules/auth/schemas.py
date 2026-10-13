from pydantic import BaseModel, EmailStr, Field

from app.modules.people.schemas import UserOut


class MagicLinkRequest(BaseModel):
    email: EmailStr
    next: str | None = Field(default=None, max_length=500)


class MagicLinkVerify(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class LoginResult(BaseModel):
    user: UserOut
    next: str = '/'


class Providers(BaseModel):
    magic_link: bool = True
    skolstream: bool


class Me(BaseModel):
    user: UserOut
