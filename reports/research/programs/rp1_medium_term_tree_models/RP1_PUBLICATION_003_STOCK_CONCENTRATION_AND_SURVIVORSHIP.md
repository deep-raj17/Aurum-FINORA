# RP1 Publication 003: stock concentration and survivorship review

Status date: 2026-07-13

## Abstract

This publication tests whether RP1's 20-day tree-model stock evidence is broad or
concentrated. The stock subset is materially concentrated: the top 3 stocks explain
52.29% of positive Sharpe mass and 50.00% of validated rows; the top 5 explain 73.97%
of positive Sharpe mass and 72.22% of validated rows. Technology, healthcare, and a
small number of mega-cap growth stocks drive much of the evidence. All stocks in the
current universe are mega-cap names, so market-cap bucket analysis cannot distinguish
small, mid, large, and mega-cap behavior. The correct stock decision is
narrow-universe continuation, not broad stock-universe promotion.

## Research question

Do RP1's 20-day tree-model stock results depend on a small subset of symbols, sectors,
regimes, market periods, or feature families?

## Hypothesis

If 20-day tree-model stock evidence is robust, it should not depend primarily on one
or two symbols, one sector, one volatility/liquidity bucket, one market period, or one
feature family.

Failure condition: reject or narrow the stock hypothesis if most positive evidence is
concentrated in a small group of stocks or if required concentration dimensions cannot
be validated from the current artifact.

## Dataset

Primary source:

```text
reports/research/campaign_v1_results.csv
```

Metadata sources:

```text
data/fundamentals/*.csv
data/stocks/*.csv
```

Scope:

- Stock universe: 15 symbols
- Candidate rows: 45 stock rows for `LightGBM:20d`, `XGBoost:20d`, and `CatBoost:20d`
- Feature family: `technical_momentum_volatility_volume_lagged`
- Horizon: 20 days

## Methodology

This review derives:

- Sector from local fundamentals files
- Market-cap bucket from local fundamentals `marketCap`
- Volatility bucket from annualized daily return volatility in local stock history
- Liquidity bucket from median dollar volume in local stock history
- Aggregate contribution from positive Sharpe mass and validated-row share

No new models, features, dashboards, or architecture were added.

## Experimental design

1. Filter campaign rows to completed stock experiments for the three 20-day tree-model
   candidates.
2. Aggregate each stock across model families.
3. Rank stocks by positive Sharpe mass.
4. Compute top 1, 3, 5, and 10 contribution shares.
5. Group rows by sector, market-cap bucket, volatility bucket, and liquidity bucket.
6. Review model-specific and horizon-specific concentration.
7. Identify survivorship, universe, period, regime, and feature-family limitations.

## Results

### Aggregate stock concentration

Rows reviewed: 45. Validated rows: 18. Overall success rate: 40.00%.

| Top N stocks | Positive Sharpe share | Validated-row share | Stocks |
|---:|---:|---:|---|
| 1 | 20.20% | 16.67% | AAPL |
| 3 | 52.29% | 50.00% | AAPL, UNH, AMZN |
| 5 | 73.97% | 72.22% | AAPL, UNH, AMZN, NVDA, TSLA |
| 10 | 98.91% | 100.00% | AAPL, UNH, AMZN, NVDA, TSLA, MSFT, GOOGL, PG, JPM, HD |

This is concentrated. The result does not depend on only one symbol, but it does
depend heavily on the top 3-5 symbols.

### Stock-level evidence

| Stock | Validated rows | Mean Sharpe | Mean return | Sector | Volatility bucket | Liquidity bucket |
|---|---:|---:|---:|---|---|---|
| AAPL | 3 | 2.2076 | 0.6080 | Technology | medium | high |
| UNH | 3 | 1.9677 | 1.2502 | Healthcare | medium | low |
| AMZN | 3 | 1.5395 | 0.7274 | Consumer Cyclical | medium | high |
| NVDA | 3 | 1.4994 | 0.5253 | Technology | high | medium |
| TSLA | 1 | 0.8709 | 0.2605 | Consumer Cyclical | high | medium |
| MSFT | 1 | 0.8619 | 0.2298 | Technology | low | high |
| GOOGL | 2 | 0.0369 | 0.1145 | Communication Services | medium | medium |
| PG | 1 | 0.1315 | 0.0182 | Consumer Defensive | low | low |
| JPM | 1 | 0.4543 | 0.0739 | Financial Services | medium | medium |
| HD | 0 | -0.4284 | -0.1071 | Consumer Cyclical | low | low |
| META | 0 | -0.3995 | -0.1522 | Communication Services | high | high |
| BAC | 0 | -0.2858 | -0.1074 | Financial Services | high | medium |
| V | 0 | -0.0200 | -0.0149 | Financial Services | low | low |
| WMT | 0 | -0.9059 | -0.1621 | Consumer Defensive | low | low |
| MA | 0 | -2.0527 | -0.2123 | Financial Services | low | low |

### Sector concentration

| Sector | Validated / tested | Success rate | Median Sharpe | Read |
|---|---:|---:|---:|---|
| Communication Services | 2 / 6 | 33.33% | -0.1229 | Mixed; not broad. |
| Consumer Cyclical | 4 / 9 | 44.44% | 1.0123 | Mixed; AMZN/TSLA driven. |
| Consumer Defensive | 1 / 6 | 16.67% | -0.5273 | Weak. |
| Financial Services | 1 / 12 | 8.33% | -0.0390 | Weak. |
| Healthcare | 3 / 3 | 100.00% | 1.9677 | Strong but single stock, UNH. |
| Technology | 7 / 9 | 77.78% | 1.5681 | Strongest sector evidence. |

Technology and one healthcare name are the clearest drivers.

### Market-cap bucket

| Market-cap bucket | Validated / tested | Success rate | Median Sharpe | Read |
|---|---:|---:|---:|---|
| Mega cap | 18 / 45 | 40.00% | 0.1808 | Entire stock universe is mega cap. |

This test exposes a universe limitation: the current stock universe cannot validate
small-cap, mid-cap, or ordinary large-cap behavior.

### Volatility bucket

| Volatility bucket | Validated / tested | Success rate | Median Sharpe | Read |
|---|---:|---:|---:|---|
| High | 4 / 12 | 33.33% | 0.1611 | Mixed. |
| Low | 2 / 18 | 11.11% | -0.1948 | Weak. |
| Medium | 12 / 15 | 80.00% | 1.1709 | Strongest bucket. |

Medium-volatility mega caps drive much of the stock evidence.

### Liquidity bucket

| Liquidity bucket | Validated / tested | Success rate | Median Sharpe | Read |
|---|---:|---:|---:|---|
| High | 7 / 12 | 58.33% | 1.0916 | Strongest liquidity bucket. |
| Low | 4 / 18 | 22.22% | -0.1948 | Weak. |
| Medium | 7 / 15 | 46.67% | 1.0662 | Mixed-positive. |

High and medium liquidity stocks behave better than low-liquidity names in this
universe.

### Model-specific concentration

| Model | Validated / tested | Top 1 positive Sharpe share | Top 3 positive Sharpe share | Top 5 positive Sharpe share | Top drivers |
|---|---:|---:|---:|---:|---|
| LightGBM:20d | 7 / 15 | 18.13% | 50.53% | 77.57% | UNH, AAPL, NVDA, MSFT, TSLA |
| XGBoost:20d | 5 / 15 | 21.25% | 56.95% | 83.00% | UNH, AAPL, NVDA, TSLA, AMZN |
| CatBoost:20d | 6 / 15 | 22.63% | 57.36% | 81.00% | AAPL, AMZN, UNH, PG, NVDA |

All three model families show concentration in the same small set of names: AAPL,
UNH, AMZN, and NVDA recur repeatedly.

### Horizon-specific concentration

| Horizon | Validated / tested | Success rate | Median Sharpe |
|---|---:|---:|---:|
| 1d | 0 / 45 | 0.00% | -0.8907 |
| 5d | 8 / 45 | 17.78% | 0.4525 |
| 10d | 11 / 45 | 24.44% | 0.0615 |
| 20d | 18 / 45 | 40.00% | 0.1808 |

The stock evidence is horizon-specific. The 20-day horizon is strongest, but the
median Sharpe remains modest and concentration remains high.

### Regime-specific concentration

The campaign rows contain a `regimes` field, but the current stock rows are tagged
with the same combined regime set rather than separate regime-conditioned metrics.
Therefore regime-specific concentration cannot be measured from the current aggregate
artifact.

Required next artifact: regime-conditioned stock publication.

### Market-period concentration

The current campaign output does not expose per-window or per-period performance
metrics. Market-period concentration cannot be directly measured from the aggregate
CSV.

Required next artifact: rolling or expanding-window stock stability publication.

### Feature-family concentration

All reviewed rows use one feature family:

```text
technical_momentum_volatility_volume_lagged
```

Therefore the stock result is fully dependent on one feature family. No feature
ablation evidence exists yet.

## Statistical tests

Represented in the source artifact:

- Bootstrap p-values
- Deflated Sharpe
- PBO
- Baseline comparison
- Cost-adjusted backtest outputs

Not yet sufficient:

- White Reality Check
- SPA test
- Feature ablation
- Per-regime statistical tests
- Per-window statistical tests

## Failure analysis

The stock evidence fails as a broad stock-universe claim:

- The top 5 names explain 73.97% of positive Sharpe mass.
- Financial Services is weak despite four tested symbols.
- Consumer Defensive is weak.
- Communication Services is mixed and not robust.
- Healthcare appears strong only because UNH is strong.
- All stocks are mega-cap names, so market-cap generalization is untested.
- Regime and market-period concentration cannot be measured from current aggregate
  outputs.

The evidence does not fail completely. It supports a narrower hypothesis around
selected mega-cap technology, selected consumer cyclical, and UNH-like defensive
healthcare behavior.

## Economic interpretation

The result may reflect slower medium-term adjustment in high-liquidity mega-cap
growth and quality names. Technology strength may reflect trend persistence, sector
rotation, and liquidity-driven institutional flows. UNH's repeated validation may
reflect idiosyncratic defensive healthcare behavior.

This interpretation is provisional. It is not enough to support a broad stock signal.

## Survivorship and universe bias

The current stock universe is a hand-picked set of large, currently prominent names.
It is not a point-in-time index membership universe. It likely contains survivorship
and selection bias.

Specific limitations:

- No delisted stocks.
- No small-cap or mid-cap stocks.
- No point-in-time S&P 500 membership.
- No sector-balanced sampling.
- No explicit liquidity-screen history.
- Market-cap values are current local fundamentals, not point-in-time values.

This bias blocks broad stock-universe claims.

## Limitations

- No per-regime stock metrics.
- No per-window stock metrics.
- No feature ablation.
- No point-in-time universe construction.
- No delisted-stock inclusion.
- No sector-balanced sample.
- No paper-observation evidence.

## Decision

Final stock decision: narrow-universe continuation.

Do not reject all stock research, but reject broad stock-universe claims. Continue
only on a narrowed stock hypothesis centered on:

- AAPL
- UNH
- AMZN
- NVDA
- selected high/medium-liquidity mega-cap technology and consumer cyclical names

Financial Services, Consumer Defensive, and broad market-cap generalization should be
deferred or rejected until a better universe is built.

Do not proceed to paper observation from stock evidence.

## Next experiment

Publish a stock regime/window stability study before any stock candidate can advance.

Minimum required next tests:

- Per-regime stock metrics
- Rolling or expanding-window stability by ticker
- Feature ablation for technical, momentum, volatility, volume, and lagged features
- Point-in-time universe review
- Delisted-stock/survivorship-bias plan
- Sector-balanced rerun
