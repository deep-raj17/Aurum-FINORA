"""Fail-closed market-data quality engine with machine-readable reports."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from enum import StrEnum

import numpy as np
from pydantic import BaseModel, Field

from .contracts import MarketBar


class Severity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class QualityIssue(BaseModel):
    code: str
    severity: Severity
    message: str
    row: int | None = None


class MarketDataQualityReport(BaseModel):
    accepted: bool
    score: float = Field(ge=0, le=1)
    rows: int = Field(ge=0)
    issues: list[QualityIssue]
    duplicate_timestamps: int = Field(ge=0)
    outliers: int = Field(ge=0)
    holiday_or_weekend_gaps: int = Field(ge=0)
    currency: str | None = None

    def raise_if_rejected(self) -> None:
        if not self.accepted:
            messages = "; ".join(issue.message for issue in self.issues)
            raise DataQualityError(messages)


class DataQualityError(ValueError):
    """Raised when error-severity market-data defects are present."""


class MarketDataQualityEngine:
    def __init__(
        self,
        *,
        outlier_z_score: float = 8,
        maximum_business_gap_days: int = 5,
        reject_outliers: bool = False,
    ) -> None:
        if outlier_z_score <= 0 or maximum_business_gap_days < 1:
            raise ValueError("quality thresholds must be positive")
        self.outlier_z_score = outlier_z_score
        self.maximum_business_gap_days = maximum_business_gap_days
        self.reject_outliers = reject_outliers

    def validate(self, bars: list[MarketBar]) -> MarketDataQualityReport:
        issues: list[QualityIssue] = []
        if not bars:
            issues.append(
                QualityIssue(
                    code="EMPTY_DATASET",
                    severity=Severity.ERROR,
                    message="dataset contains no market bars",
                )
            )
            return self._report(bars, issues, 0, 0, 0)
        timestamps = [bar.timestamp for bar in bars]
        duplicate_count = sum(count - 1 for count in Counter(timestamps).values() if count > 1)
        if duplicate_count:
            issues.append(
                QualityIssue(
                    code="DUPLICATE_TIMESTAMP",
                    severity=Severity.ERROR,
                    message=f"{duplicate_count} duplicate timestamps detected",
                )
            )
        if timestamps != sorted(timestamps):
            issues.append(
                QualityIssue(
                    code="NON_CHRONOLOGICAL",
                    severity=Severity.ERROR,
                    message="timestamps are not in chronological order",
                )
            )
        currencies = {bar.currency for bar in bars if bar.currency}
        if len(currencies) > 1:
            issues.append(
                QualityIssue(
                    code="CURRENCY_MISMATCH",
                    severity=Severity.ERROR,
                    message=f"mixed currencies detected: {sorted(currencies)}",
                )
            )
        symbols = {bar.symbol for bar in bars}
        if len(symbols) > 1:
            issues.append(
                QualityIssue(
                    code="IDENTIFIER_MISMATCH",
                    severity=Severity.ERROR,
                    message=f"mixed symbols detected: {sorted(symbols)}",
                )
            )
        gap_count = 0
        for previous, current in zip(bars, bars[1:], strict=False):
            gap = current.timestamp.date() - previous.timestamp.date()
            if gap > timedelta(days=self.maximum_business_gap_days):
                gap_count += 1
                issues.append(
                    QualityIssue(
                        code="CALENDAR_GAP",
                        severity=Severity.WARNING,
                        message=(
                            f"{gap.days}-day gap between "
                            f"{previous.timestamp.date()} and {current.timestamp.date()}"
                        ),
                    )
                )
        outlier_count = self._outliers(bars)
        if outlier_count:
            issues.append(
                QualityIssue(
                    code="RETURN_OUTLIER",
                    severity=Severity.ERROR if self.reject_outliers else Severity.WARNING,
                    message=f"{outlier_count} extreme robust-z return outliers detected",
                )
            )
        split_warnings = 0
        for index, (previous, current) in enumerate(zip(bars, bars[1:], strict=False), start=1):
            ratio = current.close / previous.close
            if ratio < 0.35 or ratio > 3:
                split_warnings += 1
                issues.append(
                    QualityIssue(
                        code="POSSIBLE_UNADJUSTED_SPLIT",
                        severity=Severity.WARNING,
                        row=index,
                        message=f"close-price ratio {ratio:.4f} suggests a split adjustment",
                    )
                )
        missing_adjustments = sum(
            1
            for bar in bars
            if ((bar.dividend or 0) > 0 or (bar.split_coefficient or 1) != 1)
            and bar.adjusted_close is None
        )
        if missing_adjustments:
            issues.append(
                QualityIssue(
                    code="MISSING_CORPORATE_ACTION_ADJUSTMENT",
                    severity=Severity.ERROR,
                    message=(f"{missing_adjustments} dividend/split rows lack an adjusted close"),
                )
            )
        return self._report(
            bars,
            issues,
            duplicate_count,
            outlier_count,
            gap_count,
            extra_penalty=split_warnings,
        )

    def _outliers(self, bars: list[MarketBar]) -> int:
        if len(bars) < 5:
            return 0
        closes = np.asarray([bar.adjusted_close or bar.close for bar in bars])
        returns = np.diff(np.log(closes))
        median = float(np.median(returns))
        mad = float(np.median(np.abs(returns - median)))
        if mad <= 1e-12:
            return 0
        robust_z = np.abs(returns - median) / (1.4826 * mad)
        return int(np.sum(robust_z > self.outlier_z_score))

    @staticmethod
    def _report(
        bars: list[MarketBar],
        issues: list[QualityIssue],
        duplicates: int,
        outliers: int,
        gaps: int,
        extra_penalty: int = 0,
    ) -> MarketDataQualityReport:
        errors = sum(issue.severity is Severity.ERROR for issue in issues)
        warnings = sum(issue.severity is Severity.WARNING for issue in issues)
        score = max(0.0, 1 - errors * 0.25 - warnings * 0.03 - extra_penalty * 0.01)
        return MarketDataQualityReport(
            accepted=errors == 0,
            score=score,
            rows=len(bars),
            issues=issues,
            duplicate_timestamps=duplicates,
            outliers=outliers,
            holiday_or_weekend_gaps=gaps,
            currency=next((bar.currency for bar in bars if bar.currency), None),
        )
