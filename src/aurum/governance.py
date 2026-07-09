"""Audit construction and fail-closed output policy."""

from __future__ import annotations

import hashlib
from datetime import timedelta

from .models import AuditBlock, Citation, Confidence, ForecastRequest


class GovernanceError(ValueError):
    pass


def verify_temporal_grounding(citations: list[Citation], request: ForecastRequest) -> None:
    contaminated = [c.origin for c in citations if c.published_at >= request.forecast_start]
    if contaminated:
        raise GovernanceError(
            "lookahead contamination: sources published at/after forecast start: "
            + ", ".join(contaminated)
        )


def build_audit(
    request: ForecastRequest,
    *,
    model_version: str,
    citations: list[Citation],
    limitations: list[str],
) -> AuditBlock:
    verify_temporal_grounding(citations, request)
    source_names = sorted({citation.origin for citation in citations})
    input_hash = hashlib.sha256(
        request.model_dump_json(exclude={"forecast_start"}).encode()
    ).hexdigest()
    run_id = f"finora-{request.forecast_start:%Y%m%d}-{input_hash[:12]}"
    return AuditBlock(
        model_version=model_version,
        data_sources_used=source_names or ["user-supplied time series"],
        retrieval_timestamp=max(
            (citation.retrieved_at for citation in citations),
            default=request.forecast_start,
        ),
        forecast_start=request.forecast_start,
        forecast_end=request.forecast_start.date() + timedelta(days=request.horizon),
        confidence_level=Confidence.MEDIUM if len(request.values) >= 60 else Confidence.LOW,
        hallucination_risk=Confidence.LOW if citations else Confidence.MEDIUM,
        human_review_needed="Yes — required before capital allocation or client distribution",
        regulatory_flags=["Decision support only", "Not investment advice"],
        limitations=limitations,
        run_id=run_id,
        input_hash=input_hash,
        code_version=model_version,
    )
