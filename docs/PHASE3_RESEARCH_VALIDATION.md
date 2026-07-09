# Phase 3A research validation

FINORA Phase 3A is a **research and engineering validation**, not authorization for
financial decisions. Real-data runs must be chronological, reproducible, cost-aware,
regime-specific, and tied to immutable dataset/model/evidence hashes.

## Run

```powershell
python scripts/run_research_validation.py `
  --provider yahoo --symbol AAPL --model xgboost `
  --window expanding --output reports/research
```

Credentialed provider choices are `alpha-vantage`, `tiingo`, and `finnhub`; they fail
closed unless their `.env` key is populated. Models are XGBoost, LightGBM, Chronos,
PatchTST, TFT, and N-HiTS. Optional dependencies must be installed before selecting
their path.

The pipeline validates OHLCV, derives lagged return/volatility/momentum/volume features,
runs expanding or rolling walk-forward validation, records regime slices, calibrates
interval evidence, executes lagged transaction-cost-adjusted signals, and writes
versioned JSON/JSONL evidence under `reports/research/`.

Reports include MAE, RMSE, MAPE, directional accuracy, coverage ECE, Sharpe, Sortino,
Calmar, maximum drawdown, turnover, costs, and net returns. Alpha must not be claimed
without benchmark comparison, out-of-sample and regime evidence, transaction costs,
adequate sample size, and model-risk review.
