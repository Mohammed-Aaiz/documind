import asyncio
import os
import sys

# Running a file inside scripts/ puts only scripts/ on sys.path, so the backend
# package root (which holds storage/) must be added explicitly.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import text

from storage.database import engine


async def main():
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()

            print("DB CONNECTION: PASS")
            print("SERVER:", version)

    except Exception as exc:
        print("DB CONNECTION: FAIL")
        print(type(exc).__name__ + ":", exc)

    finally:
        await engine.dispose()


asyncio.run(main())