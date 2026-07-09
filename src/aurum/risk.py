"""Transparent, dependency-light market risk metrics."""

from __future__ import annotations

import numpy as np

from .models import RiskMetrics


def calculate_risk(
    values: list[float],
    annualisation_factor: int = 252,
    *,
    benchmark_values: list[float] | None = None,
    bid_ask_bps: float = 0,
    stress_multiplier: float = 3,
) -> RiskMetrics:
    prices = np.asarray(values, dtype=float)
    if np.any(prices <= 0):
        raise ValueError("risk metrics require strictly positive price/index levels")
    returns = np.diff(np.log(prices))
    if len(returns) < 10:
        raise ValueError("at least 11 levels are required")
    ten_day = returns * np.sqrt(10)
    threshold = float(np.quantile(ten_day, 0.01))
    tail = ten_day[ten_day <= threshold]
    centered = returns - np.mean(returns)
    std = max(float(np.std(returns, ddof=1)), 1e-12)
    skewness = float(np.mean(centered**3) / std**3)
    excess_kurtosis = float(np.mean(centered**4) / std**4 - 3)
    beta = None
    if benchmark_values is not None:
        benchmark = np.diff(np.log(np.asarray(benchmark_values, dtype=float)))
        aligned = min(len(benchmark), len(returns))
        benchmark = benchmark[-aligned:]
        asset = returns[-aligned:]
        variance = float(np.var(benchmark, ddof=1))
        beta = float(np.cov(asset, benchmark, ddof=1)[0, 1] / variance) if variance else None
    liquidity_penalty = bid_ask_bps / 10_000
    running_max = np.maximum.accumulate(prices)
    drawdowns = prices / running_max - 1
    underwater = drawdowns < 0
    longest = current = 0
    for flag in underwater:
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return RiskMetrics(
        var_99_10d=float(max(0, -threshold)),
        cvar_99_10d=float(max(0, -tail.mean())) if len(tail) else float(max(0, -threshold)),
        max_drawdown=float(drawdowns.min()),
        drawdown_duration=longest,
        annualised_volatility=float(np.std(returns, ddof=1) * np.sqrt(annualisation_factor)),
        observations=len(returns),
        skewness=skewness,
        excess_kurtosis=excess_kurtosis,
        beta=beta,
        liquidity_adjusted_var=float(max(0, -threshold) + liquidity_penalty),
        stress_loss=float(max(0, -threshold) * stress_multiplier),
    )
