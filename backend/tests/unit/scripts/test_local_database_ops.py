"""Operational safeguards only: no real database or process is touched."""
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock

import pytest

import config
from scripts import local_database_ops as ops


@pytest.mark.parametrize("url", [
    "postgresql+asyncpg://u:unused@remote.example:55433/documind",
    "postgresql+asyncpg://u:unused@localhost:5432/documind",
    "postgresql+asyncpg://u:unused@localhost:55433/documind_pilot_20261101",
])
def test_pilot_helper_rejects_wrong_server_or_product_pointing_to_pilot(monkeypatch, url):
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(database_url=url))
    with pytest.raises(ValueError):
        ops.pilot_database_url()


def test_pilot_url_changes_only_database_without_modifying_settings(monkeypatch):
    original = "postgresql+asyncpg://u:unused@localhost:55433/documind"
    settings = SimpleNamespace(database_url=original)
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    assert ops.pilot_database_url().endswith("/documind_pilot_20261101")
    assert settings.database_url == original


@pytest.mark.parametrize("version,opts", [(None, None), ("15", ""), ("16", '"wrong-cluster" "55433"')])
def test_missing_or_mismatched_cluster_never_starts_a_process(monkeypatch, tmp_path, version, opts):
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(
        database_url="postgresql+asyncpg://u:unused@localhost:55433/documind"))
    cluster, binary = tmp_path / "cluster", tmp_path / "pg_ctl.exe"
    cluster.mkdir(); binary.write_bytes(b"")
    if version is not None:
        (cluster / "PG_VERSION").write_text(version)
        (cluster / "postmaster.opts").write_text(opts)
    monkeypatch.setattr(ops, "CLUSTER", cluster)
    monkeypatch.setattr(ops, "PG_CTL", binary)
    run, popen = Mock(), Mock()
    monkeypatch.setattr(ops.subprocess, "run", run)
    monkeypatch.setattr(ops.subprocess, "Popen", popen)
    with pytest.raises(ValueError):
        ops.start_existing_cluster()
    run.assert_not_called(); popen.assert_not_called()


@pytest.mark.asyncio
async def test_unmarked_existing_database_is_never_migrated(monkeypatch):
    from sqlalchemy.ext import asyncio as sa_asyncio
    queries = []
    class Connection:
        async def execute(self, statement, *args):
            queries.append(str(statement))
            return SimpleNamespace(mappings=lambda: SimpleNamespace(one_or_none=lambda: {"marker": "foreign"}))
    class Context:
        async def __aenter__(self): return Connection()
        async def __aexit__(self, *args): pass
    engine = SimpleNamespace(connect=lambda: Context(), dispose=AsyncMock())
    monkeypatch.setattr(sa_asyncio, "create_async_engine", lambda *a, **k: engine)
    monkeypatch.setattr(ops, "pilot_database_url", lambda: "postgresql+asyncpg://u:unused@localhost:55433/" + ops.PILOT_NAME)
    migrate = Mock()
    monkeypatch.setattr(ops.subprocess, "run", migrate)
    with pytest.raises(ValueError, match="marker"):
        await ops.prepare_pilot()
    assert len(queries) == 1 and queries[0].lstrip().startswith("SELECT")
    migrate.assert_not_called()
    engine.dispose.assert_awaited_once()
