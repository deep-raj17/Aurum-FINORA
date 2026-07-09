from datetime import UTC, date, datetime

import pytest

from aurum.cli import main
from aurum.config import Settings
from aurum.data import CSVProvider, SyntheticProvider
from aurum.models import ForecastRequest
from aurum.monitoring import detect_drift
from aurum.reporting import render_markdown
from aurum.retrieval import Document
from aurum.service import FinoraService
from aurum.storage import Repository


def request() -> ForecastRequest:
    points = SyntheticProvider(seed=1).fetch("TEST", date(2025, 1, 1), date(2025, 4, 30))
    return ForecastRequest(
        target="TEST",
        values=[point.value for point in points],
        dates=[point.timestamp.date() for point in points],
        horizon=3,
        forecast_start=datetime(2025, 5, 1, tzinfo=UTC),
    )


def test_service_retrieves_persists_and_renders(tmp_path) -> None:
    repository = Repository(tmp_path / "test.sqlite3")
    service = FinoraService(Settings(database_path=str(tmp_path / "unused.sqlite3")), repository)
    service.add_evidence(
        Document(
            origin="Test filing",
            published_at=datetime(2025, 4, 1, tzinfo=UTC),
            text="TEST revenue growth improved while risk remained stable.",
        )
    )
    report = service.analyse(request(), "TEST revenue growth")
    restored = repository.get_report(report.audit.run_id)
    assert restored is not None
    assert restored.citations[0].origin == "Test filing"
    assert repository.verify_audit_chain()
    markdown = render_markdown(restored)
    assert "# FINORA report: TEST" in markdown
    assert report.audit.input_hash in markdown


def test_csv_provider_preserves_release_timestamp(tmp_path) -> None:
    path = tmp_path / "series.csv"
    path.write_text(
        "timestamp,value,entity,unit,release_timestamp\n"
        "2025-01-01T00:00:00Z,100,ABC,USD,2025-01-02T00:00:00Z\n",
        encoding="utf-8",
    )
    points = CSVProvider(path).fetch("ABC", date(2025, 1, 1), date(2025, 1, 2))
    assert points[0].release_timestamp.date() == date(2025, 1, 2)
    assert points[0].unit == "USD"


def test_drift_detects_large_distribution_change() -> None:
    report = detect_drift(list(range(100)), [value + 1000 for value in range(20)])
    assert report.drift_detected
    assert report.alerts


def test_cli_audit_uses_isolated_database(tmp_path, capsys) -> None:
    config = tmp_path / "settings.yaml"
    config.write_text(f"database_path: '{tmp_path / 'cli.sqlite3'}'\n", encoding="utf-8")
    result = main(["--config", str(config), "audit"])
    assert result == 0
    assert capsys.readouterr().out.strip() == "valid"


def test_repository_detects_tampered_chain(tmp_path) -> None:
    repository = Repository(tmp_path / "audit.sqlite3")
    repository.append_audit("one", {"x": 1})
    repository._connection.execute(  # noqa: SLF001 - intentional corruption test
        "UPDATE audit_events SET details = ? WHERE id = 1", ('{"x": 2}',)
    )
    repository._connection.commit()  # noqa: SLF001
    assert not repository.verify_audit_chain()


def test_request_rejects_release_day_observation() -> None:
    payload = request().model_dump()
    payload["dates"][-1] = payload["forecast_start"].date()
    with pytest.raises(ValueError, match="prior"):
        ForecastRequest.model_validate(payload)
