# RP1 initial evidence review: medium-term tree models

Status date: 2026-07-13

## Abstract

This publication reviews whether FINORA's current campaign outputs justify deeper
robustness work on medium-term tree-model signals at a 20-day horizon. The evidence
supports continuing Research Program 1 for `LightGBM:20d`, `XGBoost:20d`, and
`CatBoost:20d`, with priority on ETFs, forex, selected indices, and selected stocks.
The evidence does not support paper observation, client-facing claims, automated
trading, or real-money use. The main failure modes are large drawdowns, weak crypto
results, possible asset concentration, small mutual-fund sample size, and incomplete
robustness testing.

This is an evidence review, not a product claim, investment recommendation, paper
trade approval, or real-money trading approval.

## Research question

Do the current FINORA campaign outputs justify deeper robustness work on 20-day
tree-model signals?

## Hypothesis

The current FINORA feature set may contain more useful medium-term information than
very short-term information, especially for tree-model decision rules at a 20-day
horizon.

Failure condition: reject or narrow the hypothesis if results are concentrated in a
small asset subset, fail refreshed data, fail realistic costs, break under regime or
window changes, or cannot pass stronger multiple-testing controls.

## Dataset

Source artifacts reviewed:

- `reports/research/campaign_v1_results.csv`
- `reports/research/campaign_v1_summary.md`
- `reports/research/signal_tear_sheets/phase13_signal_deep_dive_summary.csv`
- `reports/research/signal_tear_sheets/phase13_signal_deep_dive_summary.md`
- `docs/RESEARCH_PROGRAM_1_MEDIUM_TERM_TREE_MODELS.md`
- `docs/PHASE12_ROBUSTNESS_GENERALIZATION.md`

Dataset scope:

- 47 assets per candidate group in the current campaign output.
- Asset classes include crypto, ETFs, forex, indices, mutual funds, and stocks.
- Feature family: `technical_momentum_volatility_volume_lagged`.
- Candidate horizon: 20 days.

## Methodology

This review aggregates existing campaign and tear-sheet outputs. It does not rerun
the campaign, add models, add features, or change the architecture.

Candidate groups:

- `LightGBM:20d`
- `XGBoost:20d`
- `CatBoost:20d`

Metrics reviewed:

- Completed experiments
- Validated, inconclusive, and rejected rows
- Median Sharpe
- Median drawdown
- Median turnover
- Median bootstrap p-value
- Median probability of backtest overfitting
- Median deflated Sharpe
- Asset-class success counts
- Best and worst asset examples

## Experimental design

The experimental design is a secondary review of Phase 10 and Phase 13 outputs:

1. Select only the three 20-day tree-model candidates identified by Phase 13.
2. Compare aggregate candidate performance across all available assets.
3. Split each candidate by asset class to identify breadth and concentration.
4. Inspect best and worst asset examples to preserve both positive and negative
   evidence.
5. Decide whether the candidates should be rejected, deferred, continued for
   robustness research, or promoted.

Promotion threshold for this report is deliberately conservative: a candidate can
only continue to robustness research. It cannot move to paper observation until
Phase 12 and RP1 robustness work is complete.

## Results

### Summary decision

Continue research, but do not promote.

The current evidence is strong enough to justify a disciplined RP1 robustness program.
It is not strong enough for paper observation, customer-facing performance claims,
live trading, or commercial product claims about predictive power.

## Candidate group summary

| Candidate | Completed experiments | Validated | Inconclusive | Rejected | Assets tested | Median Sharpe | Median drawdown | Median turnover | Median bootstrap p | Median PBO | Median deflated Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LightGBM:20d | 47 | 25 | 0 | 22 | 47 | 1.0123 | -0.7101 | 1.0 | 0.0033 | 0.0264 | 0.8550 |
| XGBoost:20d | 47 | 24 | 1 | 22 | 47 | 1.1105 | -0.7101 | 1.0 | 0.0000 | 0.0000 | 0.9532 |
| CatBoost:20d | 47 | 22 | 0 | 25 | 47 | 0.6808 | -0.6994 | 5.0 | 0.0300 | 0.2163 | 0.5234 |

## Asset-class review

### LightGBM:20d

| Asset class | Successful / tested | Median Sharpe | Median bootstrap p | Read |
|---|---:|---:|---:|---|
| Crypto | 0 / 6 | -0.1614 | 0.6750 | Weak; reject for now. |
| ETFs | 6 / 9 | 1.4313 | 0.0000 | Promising; needs cost and regime review. |
| Forex | 5 / 6 | 1.2639 | 0.0017 | Promising; verify data quality and execution assumptions. |
| Indices | 3 / 7 | 0.6021 | 0.0600 | Mixed; continue only with stricter tests. |
| Mutual funds | 4 / 4 | 1.4446 | 0.0000 | Promising but sample is small. |
| Stocks | 7 / 15 | 0.1483 | 0.3300 | Mixed and likely asset-specific. |

### XGBoost:20d

| Asset class | Successful / tested | Median Sharpe | Median bootstrap p | Read |
|---|---:|---:|---:|---|
| Crypto | 1 / 6 | -0.6667 | 0.9300 | Weak; reject broad crypto scope for now. |
| ETFs | 6 / 9 | 1.4647 | 0.0000 | Promising; needs cost and regime review. |
| Forex | 5 / 6 | 1.2639 | 0.0000 | Promising; verify data quality and execution assumptions. |
| Indices | 3 / 7 | 0.6021 | 0.0433 | Mixed; continue only with stricter tests. |
| Mutual funds | 4 / 4 | 1.4446 | 0.0000 | Promising but sample is small. |
| Stocks | 5 / 15 | 0.1483 | 0.3733 | Mixed and likely asset-specific. |

### CatBoost:20d

| Asset class | Successful / tested | Median Sharpe | Median bootstrap p | Read |
|---|---:|---:|---:|---|
| Crypto | 0 / 6 | -0.9950 | 0.9900 | Weak; reject for now. |
| ETFs | 4 / 9 | 0.6808 | 0.0300 | Mixed; weaker than LightGBM/XGBoost. |
| Forex | 5 / 6 | 1.1985 | 0.0000 | Promising; verify data quality and execution assumptions. |
| Indices | 4 / 7 | 1.2707 | 0.0033 | Promising; needs regime and drawdown review. |
| Mutual funds | 3 / 4 | 1.2246 | 0.0017 | Promising but sample is small. |
| Stocks | 6 / 15 | 0.4362 | 0.0933 | Mixed and likely asset-specific. |

## Best and worst examples

### LightGBM:20d

Best examples:

| Asset | Class | Classification | Sharpe | Strategy return | Max drawdown | Bootstrap p |
|---|---|---|---:|---:|---:|---:|
| INR=X | forex | validated | 2.8184 | 0.1518 | -0.0609 | 0.0000 |
| XLK | etfs | validated | 2.3736 | 1.0743 | -0.6352 | 0.0000 |
| QQQ | etfs | validated | 2.0416 | 0.5995 | -0.5944 | 0.0000 |
| AUDUSD=X | forex | validated | 2.0210 | 0.1245 | -0.1015 | 0.0000 |
| UNH | stocks | validated | 1.9677 | 1.2502 | -0.7431 | 0.0000 |

Worst examples:

| Asset | Class | Classification | Sharpe | Strategy return | Max drawdown | Bootstrap p |
|---|---|---|---:|---:|---:|---:|
| ADA-USD | crypto | rejected | -2.0798 | -0.7133 | -0.9999 | 1.0000 |
| MA | stocks | rejected | -2.0759 | -0.2138 | -0.8143 | 1.0000 |
| ETH-USD | crypto | rejected | -1.3818 | -0.4778 | -0.9984 | 1.0000 |
| ^NSEI | indices | rejected | -1.2831 | -0.2078 | -0.8623 | 0.9967 |
| JPY=X | forex | rejected | -1.0538 | -0.0567 | -0.3698 | 1.0000 |

### XGBoost:20d

Best examples:

| Asset | Class | Classification | Sharpe | Strategy return | Max drawdown | Bootstrap p |
|---|---|---|---:|---:|---:|---:|
| AUDUSD=X | forex | validated | 2.4946 | 0.1462 | -0.0728 | 0.0000 |
| XLK | etfs | validated | 2.3736 | 1.0743 | -0.6352 | 0.0000 |
| INR=X | forex | validated | 2.3035 | 0.1318 | -0.0609 | 0.0000 |
| QQQ | etfs | validated | 2.0416 | 0.5995 | -0.5944 | 0.0000 |
| UNH | stocks | validated | 1.9677 | 1.2502 | -0.7431 | 0.0000 |

Worst examples:

| Asset | Class | Classification | Sharpe | Strategy return | Max drawdown | Bootstrap p |
|---|---|---|---:|---:|---:|---:|
| MA | stocks | rejected | -2.0759 | -0.2138 | -0.8143 | 1.0000 |
| JPY=X | forex | rejected | -1.9842 | -0.0934 | -0.4965 | 1.0000 |
| ADA-USD | crypto | rejected | -1.7829 | -0.6764 | -0.9998 | 1.0000 |
| HD | stocks | rejected | -1.6420 | -0.3506 | -0.9703 | 1.0000 |
| ^BSESN | indices | rejected | -1.4495 | -0.2366 | -0.8781 | 1.0000 |

### CatBoost:20d

Best examples:

| Asset | Class | Classification | Sharpe | Strategy return | Max drawdown | Bootstrap p |
|---|---|---|---:|---:|---:|---:|
| AAPL | stocks | validated | 2.8694 | 0.7775 | -0.3675 | 0.0000 |
| AMZN | stocks | validated | 2.4353 | 1.2559 | -0.5985 | 0.0000 |
| UNH | stocks | validated | 1.9677 | 1.2502 | -0.7431 | 0.0000 |
| INR=X | forex | validated | 1.6536 | 0.1006 | -0.0762 | 0.0000 |
| ^IXIC | indices | validated | 1.6230 | 0.4446 | -0.5688 | 0.0000 |

Worst examples:

| Asset | Class | Classification | Sharpe | Strategy return | Max drawdown | Bootstrap p |
|---|---|---|---:|---:|---:|---:|
| XLE | etfs | rejected | -2.7435 | -0.4308 | -0.9828 | 1.0000 |
| ADA-USD | crypto | rejected | -2.3973 | -0.7447 | -1.0000 | 1.0000 |
| GOOGL | stocks | rejected | -2.1144 | -0.6097 | -0.9986 | 1.0000 |
| MA | stocks | rejected | -2.0064 | -0.2092 | -0.8105 | 1.0000 |
| WMT | stocks | rejected | -1.9440 | -0.3017 | -0.9561 | 1.0000 |

## What the evidence supports

The current evidence supports these narrow conclusions:

- The 20-day horizon is a reasonable focus for the next robustness program.
- LightGBM and XGBoost have the strongest broad 20-day profile in the current
  campaign.
- CatBoost has strong single-asset examples but weaker median evidence and higher
  median turnover.
- ETFs, forex, and mutual funds deserve focused review.
- Crypto should be rejected or excluded from this hypothesis until new evidence
  explains why it should behave differently.
- Stocks appear mixed and should be studied by asset, sector, and concentration
  rather than treated as a broad validated universe.

## What the evidence does not support

The current evidence does not support:

- Real-money trading.
- Automated trading.
- Client-facing recommendations.
- Paid performance claims.
- A claim that FINORA predicts markets.
- Promotion to paper observation before Phase 12 and RP1 robustness work.

## Statistical tests

Completed or present in source artifacts:

- Bootstrap p-value review
- Deflated Sharpe review
- Probability of Backtest Overfitting review
- Baseline comparison in the campaign outputs
- Asset and regime breadth check in Phase 13 outputs

Still required before any paper-observation decision:

- White Reality Check or comparable multiple-testing control
- SPA or comparable robustness test where appropriate
- Refreshed-data rerun
- Cost and slippage sensitivity review
- Rolling and expanding-window stability review
- Regime-conditioned statistical review

## Failure analysis

Observed failures:

- Crypto is weak across all three 20-day tree-model candidates.
- Stocks are mixed and likely asset-specific rather than broadly validated.
- Some best examples have large drawdowns, which weakens practical usefulness.
- CatBoost has higher median turnover than LightGBM and XGBoost, making it more
  vulnerable to costs and slippage.
- Mutual-fund results look promising but are based on only four tested assets.
- Several worst examples have bootstrap p-values near 1.0 and severe drawdowns,
  indicating clear rejection cases.

Rejected or narrowed scopes:

- Reject broad crypto scope for this hypothesis until new evidence explains why it
  should be reopened.
- Do not treat the stock universe as broadly validated; require sector and
  concentration review.
- Do not promote any candidate to paper observation from this report alone.

## Economic interpretation

The provisional economic mechanism is that a 20-day horizon may reduce daily noise
and allow slower behavioral, liquidity, volatility-clustering, and sector-rotation
effects to appear.

The evidence is consistent with that hypothesis in parts of ETFs, forex, mutual
funds, indices, and selected stocks. It is not consistent with a universal
cross-asset edge because crypto fails and the stock universe is mixed.

This mechanism remains provisional. RP1 must either strengthen it through robustness
and failure analysis or narrow the hypothesis to specific asset classes where the
mechanism is plausible.

## Limitations

- Median drawdowns are large across all three candidate groups.
- Some strong examples may be concentrated in specific assets.
- The campaign may contain selection bias because RP1 starts from surviving groups.
- Crypto weakness indicates the hypothesis is not universally cross-asset.
- Mutual-fund results are promising but based on a small sample.
- CatBoost's higher median turnover may make it more sensitive to costs and slippage.
- The current review is based on existing campaign outputs, not refreshed data.
- White Reality Check, SPA, refreshed-data validation, and paper observation are not
  complete.

## Decision

Proceed with RP1 robustness analysis on:

- `LightGBM:20d`
- `XGBoost:20d`
- `CatBoost:20d`

Prioritize:

1. ETFs and forex for LightGBM/XGBoost.
2. Indices, forex, and selected stocks for CatBoost.
3. Mutual funds only as a small-sample supporting review.
4. Stocks only after concentration and sector review.

Do not proceed to paper observation yet.

## Next experiment

Before any paper-observation decision, RP1 should produce:

1. Asset concentration review for every validated 20-day tree-model result.
2. Sector/category review for the stock subset.
3. Regime-conditioned performance review.
4. Transaction-cost and slippage sensitivity review.
5. Rolling and expanding-window stability review.
6. Refreshed-data rerun using the same architecture and no new models.
7. Multiple-testing review using White Reality Check or a comparable control.
8. Probability of Backtest Overfitting review.
9. Economic interpretation note for each surviving asset class.
10. Explicit rejection memo for crypto under this hypothesis unless new evidence
    justifies reopening it.

## Commercial implication

This report strengthens FINORA's commercial story only in one specific way: it shows
that FINORA can convert broad campaign outputs into a disciplined research decision.

It does not prove market alpha or customer value. Customer value still requires
repeatable reports, user feedback, time-saved evidence, and long-term paper
observation records.
