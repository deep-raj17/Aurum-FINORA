# RP1 final archival report

Archive date: 2026-07-14

## Research question and hypothesis

RP1 asked whether medium-term 20-day tree-model signals demonstrate robust evidence
across assets, regimes, and realistic evaluation conditions. The hypothesis was that
the existing technical, momentum, volatility, volume, and lagged-return feature set
could support such evidence through LightGBM, XGBoost, or CatBoost.

## Experimental record

The record comprises the initial evidence review, asset-class review, stock
concentration review, ETF/forex review, Publication 005, its independent review,
material-correction successor, and long-window dependence correction. Publication
005C used 20 primary assets, four fixed seeds, seven aligned baselines, two
126-observation chronological pre-holdout test windows, a 20-row purge, five-row
embargo, and valid 20/25/40 moving-block sensitivity tests.

## Conclusions

The hypothesis is not supported to the standard required for promotion. Evidence is
mixed by asset, model, seed, and regime; collapse flags are common; baseline
superiority and broad stability are not established. The original result remains:

```text
RP1 remains statistically inconclusive.
Paper observation is not approved.
```

Economic figures are diagnostic only because 20-day forward targets overlap. They do
not support profitability, alpha, investment-advice, production-readiness, or trading
claims.

## Failure analysis and limitations

Stocks were concentrated or fragile. ETF and forex observations were mixed. The final
package records dependence-aware methods, aligned baselines, seeds, splits, collapse
diagnostics, and provenance; remaining limitations include survivorship-prone scope,
technical features only, overlapping-target economics, no final protected-holdout
evaluation, and no paper observation.

## Archive decision

Archive reason: **Evidence inconclusive but research objective completed.**

RP1 is closed, immutable, and read-only except for typographical corrections. It has
answered its defined question sufficiently: no candidate met the promotion standard.
Future work must not reinterpret RP1. Potential successors, each requiring a new
approved protocol, are RP2 Cross-Asset Generalization, RP3 Regime Detection, RP4
Feature Discovery, and RP5 Transaction Cost Analysis.
