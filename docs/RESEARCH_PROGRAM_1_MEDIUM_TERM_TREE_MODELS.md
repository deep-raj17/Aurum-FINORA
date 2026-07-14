# Research Program 1: Medium-Term Tree Model Investigation

Status date: 2026-07-09

## Program Thesis

Phase 13 selected three paper-trading observation candidates:

- `LightGBM:20d`
- `XGBoost:20d`
- `CatBoost:20d`

This does not prove alpha. It suggests a focused research hypothesis:

```text
The current FINORA feature set may contain more useful medium-term information than
very short-term information, especially for tree-model decision rules at a 20-day
horizon.
```

This is a hypothesis, not a conclusion.

## Program Objective

Determine whether medium-term tree-model signals are robust enough to become
human-reviewed paper-trading candidates.

The goal is evidence, not more architecture.

## Frozen Architecture Rule

Do not add:

- New forecasting models
- New LLMs
- New databases
- New dashboards
- New APIs
- New execution systems
- New broker integrations

Use the current FINORA research platform. Code changes are allowed only when a
research result proves the current tooling cannot answer a necessary question.

## Research Questions

1. Why did 20-day tree-model groups survive while 1-day groups failed?
2. Which features contribute most to the surviving 20-day signals?
3. Which assets and asset classes drive the results?
4. Which sectors or categories are most stable?
5. Which regimes support the signal?
6. Which regimes break the signal?
7. Does the signal survive stricter holdout periods?
8. Does the signal survive refreshed data?
9. Does the signal survive higher transaction costs?
10. Does the signal survive retraining and walk-forward changes?
11. Does the signal generalize to new markets, including Indian equities if approved
    data is available?
12. Is there a plausible economic explanation?

## Required Analyses

### Feature Attribution

For each candidate group:

- Rank feature importance.
- Identify unstable or noisy features.
- Compare feature importance across assets.
- Compare feature importance across regimes.
- Remove weak features only when evidence supports removal.

### Asset And Sector Review

For each candidate group:

- Rank performance by asset.
- Rank performance by asset class.
- Identify whether results are concentrated in a narrow subset.
- Reject narrow signals unless there is a plausible economic reason.

### Regime Review

Evaluate separately in:

- Bull markets
- Bear markets
- Sideways markets
- High-volatility periods
- Low-volatility periods
- Crisis-like periods where data permits

### Stability Review

Test:

- Rolling retraining
- Expanding-window retraining
- Different train/test split points
- Different transaction-cost assumptions
- Different slippage assumptions
- Different minimum training lengths

### Statistical Review

Before any paper-trading step, compute or document:

- Bootstrap confidence
- Deflated Sharpe
- Probability of backtest overfitting
- White Reality Check or comparable multiple-testing control
- SPA or comparable robustness test where appropriate

## Rejection Rules

Reject or defer a candidate if:

- It works on only one asset without a strong economic reason.
- It works in only one regime without a declared regime-specific scope.
- It fails after realistic transaction costs.
- It depends on a small number of extreme observations.
- It breaks under small retraining or split changes.
- It has no plausible economic explanation.
- It cannot be reproduced from the research registry and journal.

## Output Artifacts

Expected outputs:

```text
reports/research/programs/rp1_medium_term_tree_models/
```

Expected report types:

- Feature importance report
- Asset-class stability report
- Regime stability report
- Transaction-cost sensitivity report
- Statistical validation report
- Final program decision memo

## Promotion Gate

A candidate can move toward paper trading only if it survives:

- Phase 12 robustness review
- This Research Program 1 deep dive
- Human interpretation review
- Decision-review template preparation

Paper trading remains manual, human-reviewed, and non-automatic.

Before promotion, each accepted candidate must document:

- Cross-asset robustness.
- Cross-regime robustness.
- Temporal robustness.
- Cost robustness after realistic transaction costs, slippage, and turnover.
- Statistical robustness under predefined validation tests.
- Economic plausibility.
- Failure condition: what evidence, market change, or metric deterioration would
  invalidate the signal or trigger re-evaluation.

## Current Decision

FINORA is finished as a software engineering build for now. The next six months should
focus on disciplined research around the medium-term tree-model hypothesis.

Success should be measured by:

- Hypotheses tested
- Experiments completed
- Signals rejected
- Robustness analyses performed
- Paper-trading decisions reviewed

Not by the number of new technologies in the repository.
