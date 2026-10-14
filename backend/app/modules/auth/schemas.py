from pydantic import BaseModel, EmailStr, Field

from app.modules.people.schemas import UserOut


class MagicLinkRequest(BaseModel):
    email: EmailStr
    next: str | None = Field(default=None, max_length=500)
    captcha_token: str | None = Field(default=None, max_length=4000)


class PasswordLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    next: str | None = Field(default=None, max_length=500)


class PasswordChange(BaseModel):
    current_password: str | None = Field(default=None, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class MagicLinkVerify(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class LoginResult(BaseModel):
    user: UserOut
    next: str = '/'


class Providers(BaseModel):
    magic_link: bool = True
    skolstream: bool
    captcha_site_key: str | None = None


class Me(BaseModel):
    user: UserOut
    judge_mode: bool = False
    has_password: bool = False
