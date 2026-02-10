"""Authentication-related Pydantic models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """Request model for login."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)

    @field_validator("username", "password")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class LoginResponse(BaseModel):
    """Response model for successful login."""

    message: str
    redirect_url: str


class SessionInfo(BaseModel):
    """Session information."""

    authenticated: bool
    username: Optional[str] = None
    login_time: Optional[datetime] = None
    ip: Optional[str] = None


class LogoutResponse(BaseModel):
    """Response model for logout."""

    message: str
