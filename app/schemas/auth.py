"""Schemas for authentication endpoints."""

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Request body for admin login."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class RegisterRequest(BaseModel):
    """Request body for client self-registration."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class ForgotPasswordRequest(BaseModel):
    """Request body to start password reset flow."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=255)


class ResetPasswordRequest(BaseModel):
    """Request body to complete password reset flow."""

    model_config = ConfigDict(str_strip_whitespace=True)

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=255)


class Token(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
