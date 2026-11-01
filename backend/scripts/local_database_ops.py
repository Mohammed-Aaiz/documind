"""Start the existing local cluster or prepare the isolated educational pilot DB.

Never initializes, resets, drops or downgrades a database. Credentials remain in
memory, resolved through the existing settings; no environment file is written.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

PILOT_NAME = "documind_pilot_20261101"
PILOT_MARKER = "documind-isolated-pilot-20261101"
CLUSTER = BACKEND / ".pgdata"
PG_CTL = Path("C:/pg/pg16/pgsql/bin/pg_ctl.exe")


def pilot_database_url() -> str:
    """Return the dedicated target in memory; callers must never print it."""
    from config import get_settings
    from sqlalchemy.engine import make_url
    original = make_url(get_settings().database_url)
    if original.host not in {"localhost", "127.0.0.1"} or original.port != 55433:
        raise ValueError("This research helper accepts only the verified local server on 55433")
    if original.database == PILOT_NAME:
        raise ValueError("The application configuration must not point at the pilot database")
    target = original.set(database=PILOT_NAME)
    if target == original or target.database in {"postgres", "template0", "template1", "documind"}:
        raise ValueError("Research target is not isolated")
    return target.render_as_string(hide_password=False)


def start_existing_cluster() -> None:
    """Start only the verified existing PG16 cluster, with logs outside PGDATA."""
    from config import get_settings
    from sqlalchemy.engine import make_url
    url = make_url(get_settings().database_url)
    if url.host not in {"localhost", "127.0.0.1"} or url.port != 55433:
        raise ValueError("Configured database is not this local cluster; no process was started")
    if not PG_CTL.is_file() or not (CLUSTER / "PG_VERSION").is_file():
        raise ValueError("Existing local PostgreSQL installation/data are missing; initialization is forbidden")
    if (CLUSTER / "PG_VERSION").read_text().strip() != "16":
        raise ValueError("Existing cluster version does not match the verified PostgreSQL installation")
    opts = (CLUSTER / "postmaster.opts").read_text(encoding="utf-8").replace("\\", "/")
    if CLUSTER.as_posix().casefold() not in opts.casefold() or '"55433"' not in opts:
        raise ValueError("Existing cluster identity differs from the verified application cluster")
    status = subprocess.run([str(PG_CTL), "-D", str(CLUSTER), "status"], capture_output=True)
    if status.returncode == 0:
        print("Existing PostgreSQL cluster is already running.")
        return
    if status.returncode != 3:
        raise ValueError("PostgreSQL status could not be established safely")
    # New-session detached helper avoids terminating the postmaster when the
    # terminal/tool exits. No log is kept inside PGDATA during recovery fsync.
    command = [str(PG_CTL), "-D", str(CLUSTER), "-l", str(BACKEND / "pg-daily-runtime.log"),
               "-o", "-h 127.0.0.1 -p 55433", "-t", "120", "-w", "start"]
    with (BACKEND / "pg-start-output.log").open("ab") as out, (BACKEND / "pg-start-error.log").open("ab") as err:
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if os.name == "nt" else 0
        subprocess.Popen(command, cwd=BACKEND, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                         creationflags=flags, close_fds=True)
    print("Existing PostgreSQL startup requested; wait for readiness before using the app.")


async def inspect_database(url: str) -> dict:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            name = (await connection.execute(text("SELECT current_database()"))).scalar_one()
            head = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
            counts = {}
            for table in ("users", "documents", "document_chunks"):
                counts[table] = (await connection.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
            return {"database": name, "migration": head, "counts": counts}
    finally:
        await engine.dispose()


async def prepare_pilot() -> dict:
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine
    target = make_url(pilot_database_url())
    admin = create_async_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            row = (await connection.execute(text("SELECT oid, shobj_description(oid,'pg_database') AS marker "
                "FROM pg_database WHERE datname=:name"), {"name": PILOT_NAME})).mappings().one_or_none()
            if row is None:
                # The database name is a hard-coded identifier, never user input.
                await connection.execute(text(f'CREATE DATABASE "{PILOT_NAME}"'))
                await connection.execute(text(f'COMMENT ON DATABASE "{PILOT_NAME}" IS \'{PILOT_MARKER}\''))
            elif row["marker"] != PILOT_MARKER:
                raise ValueError("Existing target lacks the exact isolated-pilot marker; no migration or writes allowed")
    finally:
        await admin.dispose()
    env = os.environ.copy()
    env["DATABASE_URL"] = target.render_as_string(hide_password=False)
    # Alembic env.py reads this process-only override; the application .env stays unchanged.
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND,
                            env=env, capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Isolated pilot migration failed; database preserved for diagnosis")
    return await inspect_database(target.render_as_string(hide_password=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "verify", "prepare-pilot", "verify-pilot"))
    args = parser.parse_args()
    try:
        if args.command == "start":
            start_existing_cluster()
            return
        if args.command == "prepare-pilot":
            result = asyncio.run(prepare_pilot())
        else:
            from config import get_settings
            url = pilot_database_url() if args.command == "verify-pilot" else get_settings().database_url
            result = asyncio.run(inspect_database(url))
        print(json.dumps(result))
    except Exception as exc:
        # Connection strings/driver errors are deliberately not printed.
        parser.exit(1, f"Database operation did not complete ({type(exc).__name__}); check local readiness/permissions.\n")


if __name__ == "__main__":
    main()
