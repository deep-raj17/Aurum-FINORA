"""Rule-transparent macro regime classification scaffolding."""

from __future__ import annotations

from pydantic import BaseModel


class MacroInputs(BaseModel):
    real_growth: float
    inflation: float
    inflation_trend: float
    policy_rate_change: float


class MacroAssessment(BaseModel):
    regime: str
    monetary_stance: str
    rationale: list[str]


def classify_regime(data: MacroInputs) -> MacroAssessment:
    if data.real_growth < 0 and data.inflation > 3:
        regime = "stagflationary"
    elif data.real_growth < 0:
        regime = "recessionary"
    elif data.inflation_trend < 0 and data.real_growth >= 0:
        regime = "disinflationary expansion"
    else:
        regime = "expansionary"
    stance = (
        "hawkish"
        if data.policy_rate_change > 0
        else "dovish"
        if data.policy_rate_change < 0
        else "neutral"
    )
    return MacroAssessment(
        regime=regime,
        monetary_stance=stance,
        rationale=[
            f"real growth input={data.real_growth:.2f}",
            f"inflation input={data.inflation:.2f}",
            f"inflation trend input={data.inflation_trend:.2f}",
        ],
    )
