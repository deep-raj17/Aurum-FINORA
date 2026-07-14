# RP1 Publication 004: ETF and forex robustness review

Status date: 2026-07-13

## Abstract

This publication reviews RP1's ETF and forex evidence for the three 20-day tree-model
candidates. ETF and forex evidence remains stronger than stock evidence in the current
campaign. LightGBM and XGBoost show the strongest ETF profile; all three model
families show strong forex breadth except for persistent JPY failure. However, the
current artifact does not contain per-window, per-regime, feature-ablation,
hyperparameter, or retraining-frequency results. Therefore ETF and forex candidates
may continue as robustness candidates, but no candidate qualifies for paper
observation.

## Research question

Do ETF and forex 20-day tree-model candidates remain robust after reviewing
cross-asset stability, drawdown, turnover, cost stress, statistical strength, and
failure cases?

## Hypothesis

ETF and forex candidates should survive across multiple assets, remain positive after
realistic and stressed cost proxies, avoid excessive drawdown, show acceptable
statistical evidence, and have plausible economic rationale.

Failure condition: defer or reject candidates that depend on one asset, fail stressed
costs, fail broad asset coverage, show unacceptable drawdowns, or lack required
out-of-sample and regime-conditioned evidence.

## Dataset

Source artifact:

```text
reports/research/campaign_v1_results.csv
```

Scope:

- Asset classes: ETFs and forex
- Horizon: 20 days
- Models: `LightGBM`, `XGBoost`, `CatBoost`
- ETF rows: 9 per model
- Forex rows: 6 per model

## Methodology

This review uses existing campaign outputs to analyze:

- Cross-asset success rate
- Median Sharpe
- Median drawdown
- Median turnover
- Median trading cost
- Bootstrap p-value
- PBO
- Deflated Sharpe
- Accuracy, ROC-AUC, and F1 as weak calibration proxies
- Stressed-cost return survival using existing `trading_cost`

Cost stress method:

```text
stressed_return = strategy_return - (cost_multiplier - 1) * trading_cost
```

This is a rough stress proxy. It is not a full re-backtest.

## Experimental design

1. Filter completed 20-day ETF and forex rows for each tree model.
2. Compare model-level aggregate statistics.
3. Inspect every ETF and forex asset result.
4. Apply 1x, 2x, 5x, and 10x cost-stress proxies.
5. Identify failure cases.
6. Decide whether candidates should be rejected, deferred, continued, treated as
   robustness candidates, or moved toward paper observation.

## Results

### ETF aggregate review

| Model | Validated / tested | Median Sharpe | Median drawdown | Median turnover | Median cost | Median bootstrap p | Median PBO | Median deflated Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LightGBM:20d | 6 / 9 | 1.4313 | -0.6034 | 1.0 | 0.0008 | 0.0000 | 0.0000 | 1.2739 |
| XGBoost:20d | 6 / 9 | 1.4647 | -0.6352 | 1.0 | 0.0008 | 0.0000 | 0.0000 | 1.3073 |
| CatBoost:20d | 4 / 9 | 0.6808 | -0.6352 | 7.0 | 0.0056 | 0.0300 | 0.2163 | 0.5234 |

ETF read:

- LightGBM and XGBoost are stronger than CatBoost.
- Drawdowns remain large.
- CatBoost has weaker breadth and higher turnover.
- XLE is a repeated failure case.

### ETF asset results

| Model | Strong cases | Failure or weak cases |
|---|---|---|
| LightGBM:20d | XLK, QQQ, VOO, VTI, SPY, IWM | XLF, DIA, XLE |
| XGBoost:20d | XLK, QQQ, VOO, SPY, VTI, IWM | DIA, XLE, XLF |
| CatBoost:20d | VOO, SPY, XLK, VTI | DIA, IWM, QQQ, XLF, XLE |

### Forex aggregate review

| Model | Validated / tested | Median Sharpe | Median drawdown | Median turnover | Median cost | Median bootstrap p | Median PBO | Median deflated Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LightGBM:20d | 5 / 6 | 1.2639 | -0.2558 | 3.0 | 0.0024 | 0.0017 | 0.0132 | 1.1065 |
| XGBoost:20d | 5 / 6 | 1.2639 | -0.2590 | 4.0 | 0.0032 | 0.0000 | 0.0000 | 1.1065 |
| CatBoost:20d | 5 / 6 | 1.1985 | -0.2590 | 4.0 | 0.0032 | 0.0000 | 0.0000 | 1.0412 |

Forex read:

- Forex breadth is strong across all three models.
- JPY is the persistent failure case.
- INR and AUDUSD are leading positives.
- Drawdowns are materially lower than ETF drawdowns in the current aggregate results.

### Forex asset results

| Model | Strong cases | Failure case |
|---|---|---|
| LightGBM:20d | INR=X, AUDUSD=X, CAD=X, EURUSD=X, GBPUSD=X | JPY=X |
| XGBoost:20d | AUDUSD=X, INR=X, CAD=X, EURUSD=X, GBPUSD=X | JPY=X |
| CatBoost:20d | INR=X, AUDUSD=X, EURUSD=X, CAD=X, GBPUSD=X | JPY=X |

## Cost-stress review

### ETF cost stress

| Model | 1x positive returns | 2x positive returns | 5x positive returns | 10x positive returns | 10x median stressed return |
|---|---:|---:|---:|---:|---:|
| LightGBM:20d | 8 / 9 | 8 / 9 | 8 / 9 | 7 / 9 | 0.2561 |
| XGBoost:20d | 8 / 9 | 8 / 9 | 8 / 9 | 8 / 9 | 0.2610 |
| CatBoost:20d | 7 / 9 | 7 / 9 | 7 / 9 | 4 / 9 | -0.0092 |

ETF cost-stress read:

- XGBoost survives the rough ETF cost-stress proxy best.
- LightGBM remains positive in most ETF cases.
- CatBoost weakens materially under 10x cost stress.

### Forex cost stress

| Model | 1x positive returns | 2x positive returns | 5x positive returns | 10x positive returns | 10x median stressed return |
|---|---:|---:|---:|---:|---:|
| LightGBM:20d | 5 / 6 | 5 / 6 | 5 / 6 | 5 / 6 | 0.0528 |
| XGBoost:20d | 5 / 6 | 5 / 6 | 5 / 6 | 5 / 6 | 0.0443 |
| CatBoost:20d | 5 / 6 | 5 / 6 | 5 / 6 | 4 / 6 | 0.0344 |

Forex cost-stress read:

- LightGBM and XGBoost remain positive across 5 of 6 forex assets even under the rough
  10x cost proxy.
- CatBoost weakens but does not fully fail.
- JPY remains the central failure case.

## Calibration proxy review

The current artifact does not contain probability calibration curves, Brier scores,
or reliability diagrams. Accuracy, ROC-AUC, and F1 are only weak classification
proxies.

| Asset class | Model | Median accuracy | Median ROC-AUC | Median F1 |
|---|---|---:|---:|---:|
| ETFs | LightGBM:20d | 0.5595 | 0.5000 | 0.7176 |
| ETFs | XGBoost:20d | 0.5595 | 0.5000 | 0.7176 |
| ETFs | CatBoost:20d | 0.4643 | 0.4609 | 0.6341 |
| Forex | LightGBM:20d | 0.6905 | 0.5000 | 0.5381 |
| Forex | XGBoost:20d | 0.6905 | 0.5000 | 0.5360 |
| Forex | CatBoost:20d | 0.6845 | 0.5189 | 0.4143 |

Calibration remains unresolved. Strong Sharpe evidence with weak ROC-AUC suggests the
candidate may depend on payoff asymmetry, thresholding, or backtest mechanics rather
than clean directional classification.

## Requested robustness dimensions

| Dimension | Current status | Decision impact |
|---|---|---|
| Multiple time windows | Not available in aggregate artifact | Blocks paper observation. |
| Bull/bear/sideways regimes | Regime labels exist, but not regime-conditioned metrics | Blocks paper observation. |
| Volatility regimes | Regime labels exist, but not split metrics | Blocks paper observation. |
| Realistic costs | Included in current backtest outputs | Supports continued research. |
| Stressed costs | Rough proxy reviewed here | Supports LightGBM/XGBoost more than CatBoost. |
| Retraining frequencies | Not available | Blocks paper observation. |
| Nearby hyperparameters | Not available | Blocks paper observation. |
| Feature ablations | Not available | Blocks paper observation. |

## Statistical tests

Represented in the current artifact:

- Bootstrap p-value
- Deflated Sharpe
- PBO
- Baseline comparison
- Cost-aware returns

Still required:

- White Reality Check
- SPA test
- Refreshed out-of-sample data
- Per-regime statistical significance
- Time-window stability
- Feature-ablation stability

## Failure analysis

ETF failures:

- XLE is weak or rejected across all model families.
- CatBoost has weaker ETF breadth and cost-stress resilience.
- ETF drawdowns are large across the candidate set.

Forex failures:

- JPY fails across all model families.
- Forex results may depend on currency-specific macro regimes not separated in the
  current artifact.

General failures:

- No per-window validation.
- No true probability calibration.
- No feature-ablation evidence.
- No hyperparameter-neighborhood evidence.
- No paper-observation record.

## Economic interpretation

ETF evidence may reflect sector/factor rotation and broad index momentum at a
medium-term horizon. The strongest ETF cases include technology-heavy or broad-market
funds such as XLK, QQQ, SPY, VOO, and VTI.

Forex evidence may reflect slower macro, liquidity, and trend effects in selected
currency pairs. INR and AUDUSD appear especially strong in the current artifact, but
JPY failure suggests the mechanism is not universal.

These interpretations are plausible but not yet proven.

## Limitations

- This publication analyzes existing campaign outputs; it does not rerun the campaign.
- Cost stress is a proxy, not a full re-backtest.
- No per-regime metrics are available.
- No per-time-window metrics are available.
- No feature ablations are available.
- No nearby hyperparameter tests are available.
- No retraining-frequency tests are available.
- No out-of-sample refresh has been performed here.

## Decision

ETF/forex final decision: robustness candidate.

Continue research on:

- `LightGBM:20d` ETFs and forex
- `XGBoost:20d` ETFs and forex
- `CatBoost:20d` forex

Defer or lower priority:

- `CatBoost:20d` ETFs
- XLE ETF scope
- JPY forex scope

No candidate may be promoted to paper observation yet.

## Paper-observation blockers

Before any ETF or forex candidate can become a paper-observation candidate, FINORA
must produce evidence for:

- Refreshed out-of-sample data
- Multiple surviving assets
- Multiple surviving regimes
- Realistic and stressed transaction costs through full re-backtest
- White Reality Check or comparable multiple-testing control
- SPA or comparable robustness test
- Time-window stability
- Retraining-frequency stability
- Nearby hyperparameter stability
- Feature-ablation stability
- Plausible economic rationale with explicit failure conditions

## Next experiment

Publish RP1 Publication 005 as a true robustness rerun design and execution report for
ETF and forex candidates. It should produce per-window, per-regime, cost-stressed,
feature-ablated, and retraining-frequency evidence rather than relying on aggregate
campaign rows.
