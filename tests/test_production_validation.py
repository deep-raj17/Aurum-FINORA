from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest
from pydantic import ValidationError

from aurum.model_risk import (
    ApprovalDecision,
    ApprovalRole,
    ArtifactHashes,
    GateStatus,
    HumanApproval,
    ProductionApprovalPacket,
    ValidationGate,
    enforce_report_controls,
    export_decision_log,
    hash_files,
    hash_retrieval_evidence,
)
from aurum.models import ForecastRequest
from aurum.pipeline import FinoraPipeline
from aurum.production_validation import (
    CalibrationDataset,
    CalibrationRecord,
    ConformalCalibrator,
    MarketRegime,
    WindowMode,
    classify_regime,
    evaluate_calibration_dataset,
    walk_forward_records,
)


def test_walk_forward_calibration_and_regime_report() -> None:
    values = 100 * np.exp(np.cumsum(np.random.default_rng(7).normal(0.001, 0.01, 180)))
    dates = [date(2025, 1, 1) + timedelta(days=index) for index in range(len(values))]

    def predictor(train, horizon):
        estimate = float(train[-1])
        return estimate, estimate * 0.95, estimate * 1.05

    records = walk_forward_records(
        values, dates, predictor, minimum_train_size=60, mode=WindowMode.ROLLING, rolling_window=90
    )
    dataset = CalibrationDataset(
        name="controlled",
        version="1",
        records=records,
        source_hashes=["a" * 64],
    )
    report = evaluate_calibration_dataset(dataset, window_mode=WindowMode.ROLLING)
    assert report.overall.observations == len(records)
    assert report.strategy.trading_cost >= 0
    assert len(report.dataset_hash) == 64


def test_conformal_calibrator_and_regime_guards() -> None:
    calibrator = ConformalCalibrator(0.8)
    calibrator.fit([1, 2, 3, 4, 5], [1, 2.1, 2.9, 4.2, 5])
    low, high = calibrator.interval([3])
    assert low[0] <= 3 <= high[0]
    with pytest.raises(ValueError):
        classify_regime([1] * 5)
    bull = np.exp(np.linspace(0, 0.2, 60))
    assert classify_regime(bull) is MarketRegime.BULL


def test_human_approval_is_fail_closed() -> None:
    hashes = ArtifactHashes(
        dataset_sha256="a" * 64,
        model_sha256="b" * 64,
        retrieval_sha256="c" * 64,
        code_sha256="d" * 64,
    )
    packet = ProductionApprovalPacket(
        release_id="finora-1",
        hashes=hashes,
        gates=[ValidationGate(name="tests", status=GateStatus.PASS)],
    )
    assert packet.status() is GateStatus.BLOCKED
    packet.approvals = [
        HumanApproval(
            role=role,
            approver=f"{role.value} reviewer",
            decision=ApprovalDecision.APPROVED,
            rationale="Reviewed the complete validation evidence.",
            approved_at="2026-07-01T00:00:00Z",
            evidence_hash=hashes.reproducibility_hash,
        )
        for role in ApprovalRole
    ]
    assert packet.status() is GateStatus.PASS


def test_approval_failure_branches_and_decision_log(tmp_path) -> None:
    hashes = ArtifactHashes(
        dataset_sha256="a" * 64,
        model_sha256="b" * 64,
        retrieval_sha256="c" * 64,
        code_sha256="d" * 64,
    )
    with pytest.raises(ValidationError, match="passing gate"):
        ValidationGate(name="bad", status=GateStatus.PASS, blockers=["unresolved"])
    failed = ProductionApprovalPacket(
        release_id="failed",
        hashes=hashes,
        gates=[ValidationGate(name="security", status=GateStatus.FAIL)],
    )
    assert failed.status() is GateStatus.FAIL
    blocked = ProductionApprovalPacket(
        release_id="blocked",
        hashes=hashes,
        gates=[ValidationGate(name="gpu", status=GateStatus.BLOCKED)],
    )
    assert blocked.status() is GateStatus.BLOCKED
    assert len(blocked.write(tmp_path / "approval.json")) == 64
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"artifact")
    assert len(hash_files([artifact])) == 64

    start = datetime(2026, 1, 1, tzinfo=UTC)
    values = np.linspace(100, 120, 80).tolist()
    request = ForecastRequest(
        target="TEST",
        values=values,
        dates=[start.date() - timedelta(days=80 - index) for index in range(80)],
        horizon=1,
        forecast_start=start,
    )
    report = FinoraPipeline().run(request)
    enforce_report_controls(report)
    assert len(hash_retrieval_evidence(report)) == 64
    digest = export_decision_log([report], tmp_path / "decisions.jsonl", hashes)
    assert len(digest) == 64


def test_calibration_dataset_persistence_and_validation_guards(tmp_path) -> None:
    record = CalibrationRecord(
        origin=date(2025, 1, 1),
        target_date=date(2025, 1, 2),
        actual=2,
        prediction=1.9,
        lower=1.5,
        upper=2.5,
        previous=1.8,
        regime=MarketRegime.SIDEWAYS,
    )
    dataset = CalibrationDataset(
        name="calibration", version="1", records=[record], source_hashes=["a" * 64]
    )
    assert len(dataset.write_jsonl(tmp_path / "calibration.jsonl")) == 64
    with pytest.raises(RuntimeError, match="fitted"):
        ConformalCalibrator().interval([1])
    with pytest.raises(ValueError, match="five"):
        ConformalCalibrator().fit([1], [1])
