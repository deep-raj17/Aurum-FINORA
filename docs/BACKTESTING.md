# Backtesting policy

`aurum.backtest.evaluate_strategy` is the deterministic vectorized validator. It lags
positions, applies commissions and slippage, and reports gross/net return, Sharpe,
Sortino, Calmar, drawdown, turnover, win rate, profit factor, benchmark returns,
bootstrap significance and an overfitting proxy.

The optional event-driven path uses Backtrader:

```powershell
pip install -e ".[backtesting]"
python scripts/backtest_backtrader.py ohlcv.csv `
  --commission-bps 10 --slippage-bps 5
```

Every study must use chronological out-of-sample periods, disclose strategy count and
selection, compare buy-and-hold and a simple benchmark, include costs, report every
material regime, and retain failures. A positive backtest is not evidence of future
alpha and never bypasses human model-risk/compliance approval.
