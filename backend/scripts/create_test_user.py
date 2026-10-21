#!/usr/bin/env python3
"""Create a test user in the PostgreSQL database.

Usage:
    python scripts/create_test_user.py
    python scripts/create_test_user.py --email admin@test.com --password Secret123! --name "Admin User"

Requires the .env file to be configured with DATABASE_URL.
"""

import argparse
import asyncio
import os
import sys
import uuid

# Running a file inside scripts/ puts only scripts/ on sys.path, so the backend
# package root (which holds auth/, storage/, ...) must be added explicitly.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from passlib.context import CryptContext
from sqlalchemy import select

# Import all models so SQLAlchemy resolves relationships
from auth.models import User  # noqa: F401
from documents.models import Document, DocumentChunk  # noqa: F401
from chat.models import ChatSession, ChatMessage  # noqa: F401
from verification.models import VerificationResult  # noqa: F401
from reliability.models import SourceRef  # noqa: F401
from user.models import UserSettings  # noqa: F401
from storage.database import async_session

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_user(email: str, password: str, name: str) -> User:
    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User {email} already exists (id={existing.id}). Skipping.")
            return existing

        user = User(
            id=uuid.uuid4(),
            email=email,
            name=name,
            hashed_password=pwd_context.hash(password),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        print(f"Created user: {user.email} (id={user.id})")
        return user


def main():
    parser = argparse.ArgumentParser(description="Create a test user")
    parser.add_argument("--email", default="test@documind.io", help="User email")
    parser.add_argument("--password", default="TestPass123!", help="User password")
    parser.add_argument("--name", default="Test User", help="User display name")
    args = parser.parse_args()

    asyncio.run(create_user(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
