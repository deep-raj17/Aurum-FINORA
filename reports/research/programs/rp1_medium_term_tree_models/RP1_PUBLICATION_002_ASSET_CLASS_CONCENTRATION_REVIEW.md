# RP1 Publication 002: asset-class concentration review for 20-day tree models

Status date: 2026-07-13

## Abstract

This publication reviews whether RP1's three 20-day tree-model candidates are broadly
supported across asset classes or concentrated in narrow subsets. The evidence
supports continued robustness work for ETFs and forex, cautious small-sample review
for mutual funds, selective review for indices and stocks, and rejection of broad
crypto scope under the current hypothesis. The result strengthens RP1 as a research
program but does not justify paper observation or real-money use.

## Research question

Are the `LightGBM:20d`, `XGBoost:20d`, and `CatBoost:20d` candidates supported across
multiple asset classes, or are the apparent signals concentrated in narrow groups?

## Hypothesis

Medium-term 20-day tree-model signals should show evidence across multiple asset
classes if the underlying feature set captures durable medium-term market structure.

Failure condition: narrow or reject the hypothesis if validated rows are concentrated
in only one asset class, if an asset class fails consistently, or if successful groups
show unacceptable drawdowns or weak statistical evidence.

## Dataset

Source artifact:

```text
reports/research/campaign_v1_results.csv
```

Candidate groups:

- `LightGBM:20d`
- `XGBoost:20d`
- `CatBoost:20d`

Scope:

- 47 completed experiments per candidate group
- Asset classes: crypto, ETFs, forex, indices, mutual funds, stocks
- Feature family: `technical_momentum_volatility_volume_lagged`
- Horizon: 20 days

## Methodology

For each candidate group, this review aggregates:

- Validated rows by asset class
- Tested rows by asset class
- Asset-class success rate
- Share of validated rows by asset class
- Median Sharpe
- Median drawdown
- Median bootstrap p-value
- Validated asset list

No new model, feature, API, dashboard, or architecture was added.

## Experimental design

1. Filter campaign rows to completed 20-day experiments for each candidate model.
2. Split rows by asset class.
3. Count validated rows and total tested rows.
4. Compute asset-class success rate and validation share.
5. Review whether the candidate appears broad, narrow, or failed by asset class.
6. Assign a research decision for the next RP1 step.

## Results

### LightGBM:20d

| Asset class | Validated / tested | Success rate | Share of validated rows | Median Sharpe | Median drawdown | Median bootstrap p | Read |
|---|---:|---:|---:|---:|---:|---:|---|
| Crypto | 0 / 6 | 0.0000 | 0.0000 | -0.1614 | -0.9276 | 0.6750 | Reject broad scope. |
| ETFs | 6 / 9 | 0.6667 | 0.2400 | 1.4313 | -0.6034 | 0.0000 | Continue robustness. |
| Forex | 5 / 6 | 0.8333 | 0.2000 | 1.2639 | -0.2558 | 0.0017 | Continue robustness. |
| Indices | 3 / 7 | 0.4286 | 0.1200 | 0.6021 | -0.7250 | 0.0600 | Mixed; narrow review. |
| Mutual funds | 4 / 4 | 1.0000 | 0.1600 | 1.4446 | -0.5999 | 0.0000 | Promising but small sample. |
| Stocks | 7 / 15 | 0.4667 | 0.2800 | 0.1483 | -0.7634 | 0.3300 | Mixed; require concentration review. |

Validated assets:

```text
INR=X, XLK, QQQ, AUDUSD=X, UNH, AAPL, NVDA, ^IXIC, MSFT, VOO, VTI,
FXAIX, SWPPX, VFIAX, SPY, VTSAX, ^GSPC, TSLA, IWM, CAD=X, ^RUT,
EURUSD=X, GOOGL, AMZN, GBPUSD=X
```

### XGBoost:20d

| Asset class | Validated / tested | Success rate | Share of validated rows | Median Sharpe | Median drawdown | Median bootstrap p | Read |
|---|---:|---:|---:|---:|---:|---:|---|
| Crypto | 1 / 6 | 0.1667 | 0.0417 | -0.6667 | -0.9157 | 0.9300 | Reject broad scope. |
| ETFs | 6 / 9 | 0.6667 | 0.2500 | 1.4647 | -0.6352 | 0.0000 | Continue robustness. |
| Forex | 5 / 6 | 0.8333 | 0.2083 | 1.2639 | -0.2590 | 0.0000 | Continue robustness. |
| Indices | 3 / 7 | 0.4286 | 0.1250 | 0.6021 | -0.7250 | 0.0433 | Mixed; narrow review. |
| Mutual funds | 4 / 4 | 1.0000 | 0.1667 | 1.4446 | -0.5999 | 0.0000 | Promising but small sample. |
| Stocks | 5 / 15 | 0.3333 | 0.2083 | 0.1483 | -0.8143 | 0.3733 | Mixed; require concentration review. |

Validated assets:

```text
AUDUSD=X, XLK, INR=X, QQQ, UNH, AAPL, XRP-USD, ^IXIC, VOO, SPY, VTI,
FXAIX, SWPPX, VFIAX, NVDA, VTSAX, ^GSPC, IWM, CAD=X, ^RUT, EURUSD=X,
AMZN, GOOGL, GBPUSD=X
```

### CatBoost:20d

| Asset class | Validated / tested | Success rate | Share of validated rows | Median Sharpe | Median drawdown | Median bootstrap p | Read |
|---|---:|---:|---:|---:|---:|---:|---|
| Crypto | 0 / 6 | 0.0000 | 0.0000 | -0.9950 | -0.9374 | 0.9900 | Reject broad scope. |
| ETFs | 4 / 9 | 0.4444 | 0.1818 | 0.6808 | -0.6352 | 0.0300 | Mixed; lower priority. |
| Forex | 5 / 6 | 0.8333 | 0.2273 | 1.1985 | -0.2590 | 0.0000 | Continue robustness. |
| Indices | 4 / 7 | 0.5714 | 0.1818 | 1.2707 | -0.6994 | 0.0033 | Continue robustness with drawdown review. |
| Mutual funds | 3 / 4 | 0.7500 | 0.1364 | 1.2246 | -0.6028 | 0.0017 | Promising but small sample. |
| Stocks | 6 / 15 | 0.4000 | 0.2727 | 0.4362 | -0.7634 | 0.0933 | Mixed; require concentration review. |

Validated assets:

```text
AAPL, AMZN, UNH, INR=X, ^IXIC, VOO, PG, AUDUSD=X, SPY, FXAIX, NVDA,
VTSAX, ^GSPC, XLK, ^DJI, ^RUT, EURUSD=X, CAD=X, JPM, VFIAX, GBPUSD=X,
VTI
```

## Statistical tests

Tests represented in this review:

- Bootstrap p-value summaries by asset class
- Median Sharpe by asset class
- Median drawdown by asset class
- Cross-asset-class breadth review

Still required:

- White Reality Check or comparable multiple-testing control
- SPA or comparable robustness test
- Refreshed-data rerun
- Transaction-cost and slippage sensitivity
- Rolling and expanding-window stability
- Regime-conditioned review by asset class

## Failure analysis

Crypto fails the current RP1 hypothesis:

- LightGBM validates 0 of 6 crypto rows.
- CatBoost validates 0 of 6 crypto rows.
- XGBoost validates only 1 of 6 crypto rows and has weak median Sharpe.

Stocks are not broadly validated:

- LightGBM validates 7 of 15 stock rows.
- XGBoost validates 5 of 15 stock rows.
- CatBoost validates 6 of 15 stock rows.
- Median stock Sharpe remains weak relative to ETF and forex results.

Mutual funds are promising but underpowered:

- All three candidates show positive mutual-fund evidence.
- Only 4 mutual-fund rows are tested per candidate, so this should be treated as
  supporting evidence rather than primary proof.

Drawdown remains a practical concern:

- ETF, index, mutual-fund, and stock drawdowns are large enough to block promotion
  until cost, sizing, and risk controls are studied.

## Economic interpretation

The results are most consistent with a medium-term structure hypothesis in ETFs and
forex. ETFs may reflect slower sector and factor rotation. Forex may reflect slower
macro, liquidity, and trend effects. Mutual-fund evidence is directionally consistent
but too small-sample to carry the hypothesis.

The crypto failure suggests the current feature family does not capture the dominant
medium-term drivers of the sampled crypto assets, or that the crypto regime is too
unstable for this hypothesis.

Stocks likely need sector-level and idiosyncratic concentration analysis before any
broad conclusion is possible.

## Limitations

- This publication uses existing campaign outputs and does not rerun models.
- The asset universe is limited to the current local manifest.
- Mutual-fund evidence is sample-limited.
- Drawdown is not yet decomposed by time period or regime.
- Transaction costs and slippage have not been stress-tested at the asset-class level.
- No paper-observation evidence exists.
- No result authorizes live trading or client-facing recommendations.

## Decision

Continue RP1 robustness work, but narrow the next tests:

1. Continue ETFs and forex for LightGBM and XGBoost.
2. Continue forex and indices for CatBoost.
3. Keep mutual funds as small-sample supporting evidence.
4. Move stocks to a sector and asset-concentration review before broader claims.
5. Reject broad crypto scope for the current RP1 hypothesis.

Do not proceed to paper observation yet.

## Next experiment

Publish RP1 Publication 003 as a sector and asset-concentration review for the stock
subset of `LightGBM:20d`, `XGBoost:20d`, and `CatBoost:20d`.

That publication should answer:

- Which stock tickers are driving the apparent signal?
- Are results sector-concentrated?
- Do the same tickers validate across multiple model families?
- Are failures explainable by asset-specific behavior?
- Should stocks remain in RP1 or be narrowed to selected names only?
