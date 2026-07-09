"""Chronological, cost-aware backtesting utilities."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel


class BacktestResult(BaseModel):
    annualised_return_gross: float
    annualised_return_net: float
    sharpe_gross: float
    sharpe_net: float
    sortino_net: float
    max_drawdown: float
    calmar_net: float
    win_rate: float
    profit_factor: float
    turnover: float
    trading_cost: float
    observations: int
    average_gain_loss: float = 0.0
    alpha_t_stat: float = 0.0
    bootstrap_p_value: float = 1.0
    buy_hold_return: float = 0.0
    momentum_return: float = 0.0
    probability_backtest_overfit: float | None = None


def _annualised_return(returns: np.ndarray, factor: int) -> float:
    wealth = float(np.prod(1 + returns))
    return wealth ** (factor / len(returns)) - 1 if wealth > 0 else -1.0


def _sharpe(returns: np.ndarray, factor: int) -> float:
    sigma = float(np.std(returns, ddof=1))
    return float(np.mean(returns) / sigma * np.sqrt(factor)) if sigma else 0.0


def evaluate_strategy(
    asset_returns: list[float],
    positions: list[float],
    *,
    round_trip_bps: float = 10,
    slippage_bps: float = 5,
    annualisation_factor: int = 252,
    bootstrap_samples: int = 500,
    strategies_tested: int = 1,
    seed: int = 42,
) -> BacktestResult:
    returns = np.asarray(asset_returns, dtype=float)
    weights = np.asarray(positions, dtype=float)
    if len(returns) != len(weights) or len(returns) < 2:
        raise ValueError("returns and positions must align and contain at least 2 rows")
    # Positions are lagged to make the information set explicit.
    executed = np.r_[0.0, weights[:-1]]
    gross = executed * returns
    changes = np.abs(np.diff(np.r_[0.0, executed]))
    cost_rate = (round_trip_bps + slippage_bps) / 10_000
    costs = changes * cost_rate
    net = gross - costs
    wealth = np.cumprod(1 + net)
    drawdowns = wealth / np.maximum.accumulate(wealth) - 1
    downside = net[net < 0]
    downside_sigma = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    annual_net = _annualised_return(net, annualisation_factor)
    losses = -net[net < 0].sum()
    gains = net[net > 0]
    loss_rows = -net[net < 0]
    standard_error = float(np.std(net, ddof=1) / np.sqrt(len(net)))
    alpha_t_stat = float(np.mean(net) / standard_error) if standard_error else 0.0
    rng = np.random.default_rng(seed)
    centered = net - np.mean(net)
    boot_means = np.array(
        [
            np.mean(rng.choice(centered, len(centered), replace=True))
            for _ in range(bootstrap_samples)
        ]
    )
    bootstrap_p = float(np.mean(boot_means >= np.mean(net)))
    momentum = np.r_[0.0, np.sign(returns[:-1])] * returns
    pbo = (
        float(1 - (1 - min(1.0, bootstrap_p)) ** strategies_tested)
        if strategies_tested > 1
        else None
    )
    return BacktestResult(
        annualised_return_gross=_annualised_return(gross, annualisation_factor),
        annualised_return_net=annual_net,
        sharpe_gross=_sharpe(gross, annualisation_factor),
        sharpe_net=_sharpe(net, annualisation_factor),
        sortino_net=float(np.mean(net) / downside_sigma * np.sqrt(annualisation_factor))
        if downside_sigma
        else 0.0,
        max_drawdown=float(drawdowns.min()),
        calmar_net=annual_net / abs(float(drawdowns.min())) if drawdowns.min() else 0.0,
        win_rate=float(np.mean(net > 0)),
        profit_factor=float(net[net > 0].sum() / losses) if losses else float("inf"),
        turnover=float(changes.sum()),
        trading_cost=float(costs.sum()),
        observations=len(net),
        average_gain_loss=float(np.mean(gains) / np.mean(loss_rows))
        if len(gains) and len(loss_rows)
        else 0.0,
        alpha_t_stat=alpha_t_stat,
        bootstrap_p_value=bootstrap_p,
        buy_hold_return=_annualised_return(returns, annualisation_factor),
        momentum_return=_annualised_return(momentum, annualisation_factor),
        probability_backtest_overfit=pbo,
    )
