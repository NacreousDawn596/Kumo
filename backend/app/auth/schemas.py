"""Auth request/response schemas."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9_\-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SchoolAppStartRequest(BaseModel):
    redirect_uri: str | None = None


class SchoolAppAssertionRequest(BaseModel):
    assertion: str


class TokenResponse(BaseModel):
    user_id: str
