import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 255 or not _EMAIL.match(v):
        raise ValueError("invalid email address")
    return v


class LoginIn(BaseModel):
    email: str
    password: str = Field(max_length=200)

    @field_validator("email")
    @classmethod
    def _clean_email(cls, v: str) -> str:
        return _email(v)


class MfaVerifyIn(BaseModel):
    challenge_token: str
    code: str = Field(min_length=6, max_length=8)


class EnrollIn(BaseModel):
    challenge_token: str


class ConfirmIn(BaseModel):
    enroll_token: str
    code: str = Field(min_length=6, max_length=8)


class PasswordChangeIn(BaseModel):
    old_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)


class UserCreateIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=200)
    role: Literal["salesperson", "admin", "owner"] = "salesperson"
    password: str = Field(max_length=200)

    @field_validator("email")
    @classmethod
    def _clean_email(cls, v: str) -> str:
        return _email(v)
