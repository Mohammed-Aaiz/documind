# DATABASE_AGENT

## Role

Database schema, migrations, ORM models, and operational DB scripts.

## Owns

-   `backend/migrations/**`
-   `backend/<feature>/models.py`
-   `backend/storage/database.py`
-   `backend/alembic.ini`
-   `backend/scripts/**`

## Must Not Touch

Trained weights, non-model feature implementation, frontend, `.env`, or
unrelated tests.

## Rules

PostgreSQL + pgvector is production truth. Alembic is the sanctioned
schema path. Maintain one linear migration head. Never use `create_all`
for application schema. Never downgrade/reset/drop/recreate a live
database without explicit permission.

## Verify

``` bash
cd backend
python -m alembic heads
python -m alembic history
python scripts/setup_db.py
```
