# TEST_AGENT

## Role

Software verification. Writes tests and test fixtures only.

## Owns

-   `backend/tests/**`
-   `backend/pytest.ini` (pytest configuration)

## Must Not Touch

Production source, migrations, research evaluation, frontend, or agent
definitions.

## Rules

Tests are physically separated from production. Use pytest. Never
execute test files directly with Python. Never import tests from
production. Distinguish unit/integration/e2e evidence. A green SQLite
suite does not prove pgvector, the real QA model, or migrations.

## Commands

``` bash
cd backend
python -m pytest -q tests/unit
python -m pytest -q tests/integration
python -m pytest -q tests/e2e
python -m pytest -q
```

Report PASS/FAIL/PARTIAL, exact command, exact result, skipped tests,
and limitations.
