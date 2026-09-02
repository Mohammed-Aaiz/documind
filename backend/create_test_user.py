#!/usr/bin/env python3
"""Create a test user in the PostgreSQL database.

Usage:
    python create_test_user.py
    python create_test_user.py --email admin@test.com --password Secret123! --name "Admin User"

Requires the .env file to be configured with DATABASE_URL.
"""

import argparse
import asyncio
import uuid

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
