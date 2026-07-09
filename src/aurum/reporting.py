"""Human-readable, citation-preserving FINORA report rendering."""

from __future__ import annotations

from .models import AnalysisReport


def render_markdown(report: AnalysisReport) -> str:
    forecast = report.forecast
    intervals = {interval.level: interval for interval in forecast.intervals}
    lines = [
        f"# FINORA report: {forecast.target}",
        "",
        "## Executive summary",
        "",
        report.executive_summary,
        "",
        "## Forecast",
        "",
        f"- Horizon: {forecast.horizon} {forecast.frequency} periods",
        f"- Selected model: `{forecast.model_used}`",
        f"- Point forecast: {forecast.point_forecast:.6f}",
        f"- 80% interval: [{intervals[0.8].lower:.6f}, {intervals[0.8].upper:.6f}]",
        f"- 95% interval: [{intervals[0.95].lower:.6f}, {intervals[0.95].upper:.6f}]",
        f"- Distribution: {forecast.distribution_assumption}",
        f"- Out-of-sample RMSE: {forecast.validation.rmse:.6f}",
        f"- Directional accuracy: {forecast.validation.directional_accuracy:.1%}",
        "",
        "## Evidence",
        "",
    ]
    lines.extend(
        [f"- {citation.excerpt} {citation.label()}" for citation in report.citations]
        or ["- No external evidence used; analysis is limited to the supplied series."]
    )
    lines.extend(["", "## Scenarios", ""])
    for scenario in report.scenarios:
        lines.append(
            f"- **{scenario.name} ({scenario.probability:.0%})**: "
            f"[{scenario.expected_range.lower:.6f}, {scenario.expected_range.upper:.6f}]"
        )
    lines.extend(
        [
            "",
            "## Risk flags",
            "",
            *[f"- {risk}" for risk in forecast.key_risks],
            "",
            "## What would change this view",
            "",
            *[f"- {condition}" for condition in report.what_would_change_this_view],
            "",
            "## Audit block",
            "",
            f"- Run ID: `{report.audit.run_id}`",
            f"- Model version: `{report.audit.model_version}`",
            f"- Input hash: `{report.audit.input_hash}`",
            f"- Confidence: {report.audit.confidence_level.value}",
            f"- Hallucination risk: {report.audit.hallucination_risk.value}",
            f"- Human review: {report.audit.human_review_needed}",
            f"- Limitations: {'; '.join(report.audit.limitations)}",
        ]
    )
    return "\n".join(lines) + "\n"
