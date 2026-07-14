# RP1 Phase B Robustness Plan

Status date: 2026-07-13

Status: planned. Not yet executed.

## Purpose

RP1 Phase B defines the next evidence-generation stage after RP1 Publications 003 and
004. Its purpose is to determine whether any 20-day tree-model candidate remains
credible after deeper robustness testing.

This is not a software-build phase. It must not add models, dashboards, broker APIs,
trading automation, new architecture, or commercial claims.

## Current Evidence State

FINORA has not proven that it predicts markets.

FINORA has shown that it can:

- build research datasets
- generate hypotheses
- train and compare multiple model families
- reject weak hypotheses
- identify concentration risk
- produce reproducible research publications
- preserve governance and research memory

The current evidence is useful because it rejects broad overclaims.

## Key Finding From Publication 003

The apparent stock evidence is concentrated.

Publication 003 found that the stock subset is driven heavily by:

- AAPL
- UNH
- AMZN
- NVDA
- TSLA

The stock decision remains:

```text
narrow-universe continuation
```

This means the stock result must not be promoted as a broad stock-market result.

## Key Finding From Publication 004

ETF and forex evidence is stronger than the broad stock evidence, but still not ready
for paper observation.

Current decisions:

| Asset group | Current read | Decision |
|---|---|---|
| Stocks | Concentrated in a small subset of mega-cap names | Narrow-universe continuation |
| ETFs | More stable than stocks, but incomplete robustness evidence | Continue robustness |
| Forex | Promising screening evidence with JPY failure | Continue robustness |

No candidate is approved for paper observation.

## Phase B Research Question

Do the 20-day tree-model ETF and forex candidates, and the narrowed stock subset,
survive deeper robustness checks across regimes, time windows, costs, features,
retraining choices, hyperparameter neighborhoods, and multiple-testing controls?

## Candidate Scope

### Primary Robustness Candidates

- `LightGBM:20d` ETFs
- `XGBoost:20d` ETFs
- `LightGBM:20d` forex
- `XGBoost:20d` forex
- `CatBoost:20d` forex

### Lower-Priority Or Deferred Candidates

- `CatBoost:20d` ETFs
- Broad stock universe
- XLE ETF scope
- JPY forex scope

### Narrow-Stock Continuation Candidates

Stocks may be reviewed only as a narrowed universe, not as broad-market evidence:

- AAPL
- UNH
- AMZN
- NVDA
- TSLA

## Required Robustness Work

Phase B must produce evidence for:

- fresh out-of-sample testing
- multiple time windows
- bull, bear, sideways, high-volatility, and low-volatility regimes
- rolling-window and expanding-window stability
- realistic transaction costs
- stressed transaction costs
- retraining-frequency sensitivity
- nearby hyperparameter stability
- feature-family ablations
- calibration evidence where probabilities are interpreted
- White Reality Check or comparable multiple-testing control
- SPA-style or comparable robustness test where applicable
- explicit failure conditions

## Planned Publication Sequence

| Publication | Purpose | Required decision |
|---|---|---|
| RP1 Publication 005 | ETF and forex robustness rerun design and execution | Reject, defer, continue research, or paper-observation candidate |
| RP1 Publication 006 | Cross-regime robustness | Determine whether candidates survive regime slicing |
| RP1 Publication 007 | Rolling-window and retraining-frequency robustness | Determine temporal stability |
| RP1 Publication 008 | Transaction-cost and slippage stress | Determine cost sensitivity |
| RP1 Publication 009 | Feature-ablation and feature-stability review | Determine feature dependence |
| RP1 Publication 010 | Statistical correction and final RP1 decision | Final RP1 decision |

Publication numbers may change if negative-result reports are inserted. Negative and
inconclusive findings should be published, not hidden.

## Entry Gates

Phase B execution should not begin until the RP1 protocol and Phase 3 validation
requirements are satisfied.

Required gates:

- RP1 research protocol exists
- dataset manifest issue with `latest` is resolved or explicitly quarantined
- dataset hashes are recorded
- chronological split tests pass
- leakage-prevention tests pass
- publication-unsafe random-split paths are not used
- purge/embargo behavior for 20-day targets is validated
- stable seed policy is defined
- artifact schema is complete

## Paper Observation Gate

No candidate may move to paper observation unless all of the following are true:

- evidence is out-of-sample
- realistic costs survive
- stressed costs survive
- multiple assets survive
- multiple regimes survive
- time-window stability is acceptable
- retraining-frequency stability is acceptable
- nearby hyperparameter stability is acceptable
- feature-ablation results do not invalidate the candidate
- statistical evidence survives multiple-testing controls
- economic rationale is plausible
- failure conditions are explicit

Paper observation remains human-reviewed and non-automatic.

## Failure Conditions

A candidate should be rejected or deferred if:

- performance depends on one asset
- performance depends on one regime
- performance depends on one market period
- performance disappears after realistic or stressed costs
- performance breaks under nearby hyperparameters
- performance breaks under retraining-frequency changes
- feature ablations show dependence on a fragile or unavailable feature
- calibration is poor when probabilities are used
- multiple-testing correction removes statistical support
- results cannot be reproduced from frozen artifacts

## Expected Final RP1 Decisions

Final RP1 outcomes must use one of these decisions:

- reject
- defer
- continue research
- robustness candidate
- paper-observation candidate

No report may claim alpha. No signal may be promoted from narrow or fragile evidence.

## Next Action

The next concrete artifact should be:

```text
reports/research/programs/rp1_medium_term_tree_models/RP1_PUBLICATION_005_ETF_FOREX_ROBUSTNESS_RERUN.md
```

That publication should contain true rerun evidence, not only aggregate analysis of
the existing campaign CSV.

## Phase B Conclusion

FINORA is commercially and scientifically stronger when it rejects weak evidence.
RP1 Phase B exists to determine whether any current 20-day tree-model candidate is
robust enough to deserve human-reviewed paper observation.

Current conclusion:

```text
Research robustness should continue.
Paper observation is not ready.
No market-prediction claim is justified.
```
