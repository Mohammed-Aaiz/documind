"""Auth request/response Pydantic schemas."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


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
