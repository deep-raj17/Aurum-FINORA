"""Human approvals, reproducibility hashes, and production release gates."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .models import AnalysisReport


class GateStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class ApprovalRole(StrEnum):
    MODEL_RISK = "model-risk"
    COMPLIANCE = "compliance"
    SECURITY = "security"
    DATA_OWNER = "data-owner"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ArtifactHashes(BaseModel):
    dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieval_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    code_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @property
    def reproducibility_hash(self) -> str:
        canonical = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


class ValidationGate(BaseModel):
    name: str
    status: GateStatus
    evidence: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent(self) -> ValidationGate:
        if self.status is GateStatus.PASS and self.blockers:
            raise ValueError("a passing gate cannot contain blockers")
        return self


class HumanApproval(BaseModel):
    role: ApprovalRole
    approver: str = Field(min_length=3)
    decision: ApprovalDecision
    rationale: str = Field(min_length=10)
    approved_at: datetime
    evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ProductionApprovalPacket(BaseModel):
    release_id: str
    hashes: ArtifactHashes
    gates: list[ValidationGate]
    approvals: list[HumanApproval] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def approval_hash(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def status(self) -> GateStatus:
        if any(gate.status is GateStatus.FAIL for gate in self.gates):
            return GateStatus.FAIL
        if any(gate.status is GateStatus.BLOCKED for gate in self.gates):
            return GateStatus.BLOCKED
        approved = {
            approval.role
            for approval in self.approvals
            if approval.decision is ApprovalDecision.APPROVED
            and approval.evidence_hash == self.hashes.reproducibility_hash
        }
        rejected = any(
            approval.decision is ApprovalDecision.REJECTED for approval in self.approvals
        )
        if rejected:
            return GateStatus.FAIL
        return GateStatus.PASS if approved == set(ApprovalRole) else GateStatus.BLOCKED

    def write(self, path: str | Path) -> str:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return self.approval_hash()


REQUIRED_DISCLAIMERS = {"Decision support only", "Not investment advice"}


def hash_files(paths: list[str | Path]) -> str:
    digest = hashlib.sha256()
    for value in sorted(Path(path).resolve(strict=True) for path in paths):
        digest.update(str(value).encode())
        with value.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def hash_retrieval_evidence(report: AnalysisReport) -> str:
    canonical = [
        {
            "origin": citation.origin,
            "published_at": citation.published_at.isoformat(),
            "excerpt": citation.excerpt,
        }
        for citation in sorted(report.citations, key=lambda item: (item.origin, item.published_at))
    ]
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def enforce_report_controls(report: AnalysisReport) -> None:
    if not report.audit.human_review_needed.lower().startswith("yes"):
        raise ValueError("report does not enforce human review")
    if not REQUIRED_DISCLAIMERS <= set(report.audit.regulatory_flags):
        raise ValueError("report omits required financial disclaimers")
    if not report.audit.input_hash or not report.audit.model_version:
        raise ValueError("report omits reproducibility identifiers")


def export_decision_log(
    reports: list[AnalysisReport],
    destination: str | Path,
    hashes: ArtifactHashes,
) -> str:
    for report in reports:
        enforce_report_controls(report)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = [
        {
            "run_id": report.audit.run_id,
            "forecast_start": report.audit.forecast_start.isoformat(),
            "target": report.forecast.target,
            "model_version": report.audit.model_version,
            "input_hash": report.audit.input_hash,
            "reproducibility_hash": hashes.reproducibility_hash,
            "human_review": report.audit.human_review_needed,
            "disclaimers": report.audit.regulatory_flags,
        }
        for report in reports
    ]
    content = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()
