from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from auth.schemas import LoginRequest, TokenResponse, UserProfile
from auth.models import User
from config import get_settings
from storage.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user with email/password and return JWT token."""
    result = await db.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        user=UserProfile(
            name=user.name,
            email=user.email,
            avatarUrl=user.avatar_url,
        ),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(current_user: CurrentUser):
    """Logout current user.

    Strategy: Stateless JWT — the client discards the token.
    No server-side revocation is performed. Tokens expire
    naturally via the exp claim.
    """
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: CurrentUser):
    """Return the current authenticated user's profile."""
    return UserProfile(
        name=current_user.name,
        email=current_user.email,
        avatarUrl=current_user.avatar_url,
    )
