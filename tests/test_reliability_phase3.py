import sqlite3

import pytest

from aurum.disaster_recovery import (
    create_snapshot,
    restore_snapshot,
    verify_snapshot,
)
from aurum.reliability import CircuitBreaker, CircuitState, DependencyUnavailable
from aurum.storage import Repository


def test_circuit_breaker_degrades_opens_and_recovers() -> None:
    now = [0.0]
    breaker = CircuitBreaker(
        "qdrant", failure_threshold=2, recovery_seconds=10, clock=lambda: now[0]
    )

    def fail():
        raise ConnectionError("offline")

    assert breaker.call(fail, fallback=lambda exc: []).degraded
    assert breaker.call(fail, fallback=lambda exc: []).degraded
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(DependencyUnavailable, match="open"):
        breaker.call(lambda: ["never"])
    now[0] = 11
    result = breaker.call(lambda: ["recovered"])
    assert result.value == ["recovered"]
    assert breaker.state is CircuitState.CLOSED


def test_database_and_asset_disaster_recovery(tmp_path) -> None:
    database = tmp_path / "source.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE values_table(value TEXT)")
    connection.execute("INSERT INTO values_table VALUES('preserved')")
    connection.commit()
    connection.close()
    assets = tmp_path / "models"
    assets.mkdir()
    (assets / "model.bin").write_bytes(b"governed-model")
    snapshot = tmp_path / "snapshot"
    manifest = create_snapshot(database, [assets], snapshot)
    assert verify_snapshot(snapshot).snapshot_id == manifest.snapshot_id
    restored_db = tmp_path / "restore" / "database.sqlite3"
    restore_snapshot(snapshot, restored_db, tmp_path / "restored-assets")
    restored = sqlite3.connect(restored_db)
    assert restored.execute("SELECT value FROM values_table").fetchone()[0] == "preserved"
    restored.close()
    (snapshot / "database.sqlite3").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="integrity"):
        verify_snapshot(snapshot)


def test_database_failure_is_not_silently_replaced(tmp_path) -> None:
    repository = Repository(tmp_path / "failure.sqlite3")
    repository._connection.close()
    with pytest.raises(sqlite3.ProgrammingError):
        repository.list_reports()
