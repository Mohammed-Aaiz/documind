"""Provision a fresh DocuMind database.

Applies every Alembic migration up to ``head`` (``000_create_base_tables``
through the latest revision), creating all base tables and enabling the
pgvector extension.

Usage:
    cd backend && python scripts/setup_db.py

The database targeted is the application's configured ``DATABASE_URL``
(from ``.env`` / the environment), falling back to the value in
``alembic.ini`` -- see ``migrations/env.py``.
"""

import os
import subprocess
import sys


def _backend_dir() -> str:
    """The backend package root -- the parent of this script's directory.

    Alembic must run with the backend directory as its working directory so it
    finds ``alembic.ini`` and ``migrations/``; the script itself lives one level
    deeper in ``scripts/``.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    backend_dir = _backend_dir()

    print("Running DocuMind database setup...")
    print(f"  working dir: {backend_dir}")
    print(f"  interpreter: {sys.executable}")

    # Invoke Alembic through the current interpreter's module entry point so
    # the migration runs in the same Python environment as this script (a
    # bare ``alembic`` executable may not be on PATH).  ``alembic upgrade``
    # reads the application DATABASE_URL via migrations/env.py.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=backend_dir,
    )

    if result.stdout:
        print(result.stdout)
    if result.returncode == 0:
        print("Database setup complete")
        if result.stderr:
            print(result.stderr)
    else:
        print("Database setup failed")
        if result.stderr:
            print(result.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
