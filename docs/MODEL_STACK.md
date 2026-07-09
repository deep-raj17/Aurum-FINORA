# FINORA-MoE model stack

## Routed specialists

| Priority | Expert | Purpose | Runtime boundary |
|---|---|---|---|
| Primary | PatchTST | Patch-based long-context forecasting | NeuralForecast adapter |
| Primary | iTransformer | Inverted-token multivariate forecasting | NeuralForecast adapter |
| Multi-horizon | Temporal Fusion Transformer | Covariate-aware interpretable horizons | NeuralForecast adapter |
| Multi-horizon | TiDE | Dense multivariate multi-horizon forecasting | NeuralForecast adapter |
| Foundation | Chronos | Zero-shot/probabilistic foundation forecast | Lazy Chronos adapter |
| Tabular alpha/risk | LightGBM | Nonlinear tabular quantile signals | Direct horizon adapter |
| Tabular alpha/risk | XGBoost | Nonlinear tabular quantile signals | Direct horizon adapter |
| Tabular alpha/risk | CatBoost | Robust tabular quantile signals | Direct horizon adapter |
| Text | FinBERT | Financial sentiment embeddings/probabilities | Existing sentiment adapter |
| Graph | Graph Attention Network | Entity, ownership, supply-chain and contagion context | `GraphAttentionExpert` |

All specialist outputs must include model/weight versions, feature cutoff, data
lineage, availability, and validation identifiers. The common MoE input is a
same-width embedding; raw model output is preserved separately for audit.

## Baselines and retained compatibility

LSTM, GRU, vanilla RNN, and simple Transformer models are baseline-only. Statistical
baselines and the existing N-HiTS integration remain available for compatibility and
benchmarking, but are not members of the default FINORA-MoE router.

## Validation required for every promoted expert

Each asset-class/horizon promotion requires:

- purged walk-forward validation;
- both rolling-window and expanding-window reports;
- regime-specific performance and stress backtests;
- conformal coverage and calibration ECE;
- transaction-cost- and slippage-adjusted returns;
- Sharpe, Sortino, Calmar, and maximum drawdown;
- comparison with simple baselines and the incumbent;
- reproducible dataset, feature, code, weight, and report hashes.

The existing `production_validation.py` supplies expanding/rolling chronological
records, regime metrics, calibration ECE, and cost-aware strategy metrics.
`backtest.py` supplies net returns, Sharpe, Sortino, Calmar, and drawdown.

## Optional dependency policy

Heavy runtimes and weights are lazy-loaded. Configuration alone does not prove an
expert is active. Missing dependencies, malformed outputs, stale data, or absent
model approvals make that expert unavailable and therefore masked by the router.
