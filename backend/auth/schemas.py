"""Auth request/response Pydantic schemas."""

import re

from pydantic import BaseModel, Field, field_validator


def normalize_email(value: str) -> str:
    """Canonical login identifier; intentionally excludes quoted/local-only email."""
    email = value.strip().casefold()
    if len(email) > 255 or email.count("@") != 1:
        raise ValueError("Enter a valid email address")
    local, domain = email.rsplit("@", 1)
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Enter a valid email address") from exc
    if (
        not local or len(local) > 64 or local.startswith(".") or local.endswith(".")
        or ".." in local or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)
        or "." not in domain or len(domain) > 253
        or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in domain.split("."))
    ):
        raise ValueError("Enter a valid email address")
    canonical = f"{local}@{domain}"
    if len(canonical) > 255:
        raise ValueError("Enter a valid email address")
    return canonical


class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=72, repr=False)

    @field_validator("email")
    @classmethod
    def canonical_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def bounded_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class RegisterRequest(LoginRequest):
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=72, repr=False)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        name = value.strip()
        if not name or any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise ValueError("Enter a display name without control characters")
        return name


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserProfile"


class UserProfile(BaseModel):
    """Matches the frontend UserProfile shape."""
    name: str
    email: str
    avatarUrl: str | None = None


# Forward reference resolution
TokenResponse.model_rebuild()
