from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from auth.dependencies import CurrentUser
from auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserProfile
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


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        user=UserProfile(name=user.name, email=user.email, avatarUrl=user.avatar_url),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create an account and authenticate it; email verification is not offered."""
    duplicate = await db.execute(select(User.id).where(func.lower(User.email) == body.email).limit(1))
    if duplicate.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    hashed = await run_in_threadpool(pwd_context.hash, body.password)
    user = User(name=body.name, email=body.email, hashed_password=hashed)
    db.add(user)
    try:
        await db.flush()
        await db.refresh(user)
        response = _token_response(user)
        await db.commit()
    except IntegrityError as exc:
        # The unique email constraint arbitrates simultaneous registration.
        # Never return database diagnostics or include the submitted password.
        await db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    return response


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user with email/password and return JWT token."""
    result = await db.execute(
        select(User).where(func.lower(User.email) == body.email).limit(1)
    )
    user = result.scalar_one_or_none()

    if user is None or not await run_in_threadpool(verify_password, body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return _token_response(user)


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
