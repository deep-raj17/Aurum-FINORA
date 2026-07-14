# RP1 Publication 005: True Robustness Rerun

Status date: 2026-07-13

Run ID: `RP1_PUB005_TRUE_ROBUSTNESS_20260714T054241Z_7574f5fca030`

## Abstract

This publication executes fresh RP1 robustness reruns for the 20-day tree-model hypothesis. It evaluates LightGBM, XGBoost, and CatBoost across ETFs, forex, a narrowed stock subset, and exploratory mutual funds using chronological pre-holdout walk-forward splits. The final holdout beginning 2025-07-01 remains untouched.

The result is conservative. Some candidate groups remain worth continued research, but the evidence is not broad or stable enough for paper-observation qualification.

## Research Question

Do any 20-day tree-model candidates survive fresh robustness reruns across assets, regimes, time windows, costs, retraining schedules, hyperparameter neighborhoods, feature ablations, and statistical tests?

## Experimental Design

- Models: LightGBM, XGBoost, CatBoost.
- Horizon: 20 trading observations.
- Final holdout: rows on or after 2025-07-01 were excluded before target construction.
- Validation: purged chronological walk-forward with a 20-observation purge and 5-observation embargo.
- Universes: ETFs, forex, narrow stocks, exploratory mutual funds.
- Cost scenarios: low, realistic, stressed.
- Retraining schedules: weekly expanding, monthly expanding, quarterly expanding, monthly rolling.
- Hyperparameters: base, shallow regularized neighbor, deeper neighbor.
- Feature tests: full, family removals, noisy-feature stress.

## Data And Reproducibility

- Python: `3.11.9`
- NumPy: `1.26.4`
- Pandas: `2.3.3`
- scikit-learn: `1.9.0`
- Appendices directory: `research/experiments/rp1_publication_005_true_robustness/RP1_PUB005_TRUE_ROBUSTNESS_20260714T054241Z_7574f5fca030/appendices`
- Artifact directory: `research/experiments/rp1_publication_005_true_robustness/RP1_PUB005_TRUE_ROBUSTNESS_20260714T054241Z_7574f5fca030`

Dataset and feature hashes are recorded in `RP1_ASSET_APPENDIX.csv`.

## Primary Results

| asset_class | model | assets | mean_balanced_accuracy | median_sharpe | positive_realistic_cost_assets | robustness_candidates |
| --- | --- | --- | --- | --- | --- | --- |
| etfs | CatBoost | 9 | 0.4302048225280495 | 1.035578264553869 | 7 | 1 |
| etfs | LightGBM | 9 | 0.4959236326109391 | 3.3864541207547023 | 9 | 1 |
| etfs | XGBoost | 9 | 0.5202614379084968 | 3.4010732716623506 | 9 | 1 |
| forex | CatBoost | 6 | 0.49209962650822864 | 1.209553077836261 | 4 | 0 |
| forex | LightGBM | 6 | 0.44237166313779214 | 0.37518169902694787 | 3 | 0 |
| forex | XGBoost | 6 | 0.5088720056461992 | -1.286537999268917 | 2 | 0 |
| stocks | CatBoost | 5 | 0.49224716202270385 | -0.344639230412054 | 1 | 0 |
| stocks | LightGBM | 5 | 0.5 | 2.9723893314327654 | 3 | 0 |
| stocks | XGBoost | 5 | 0.5 | 2.9723893314327654 | 3 | 0 |

## Regime Results

Regime-conditioned results are recorded in `RP1_REGIME_APPENDIX.csv`. No candidate is promoted unless it survives more than one regime. The rerun shows that several assets have thin or uneven regime coverage, which blocks paper-observation qualification.

## Cost Sensitivity

Cost results are recorded in `RP1_COST_APPENDIX.csv`. A candidate that fails realistic costs is rejected or deferred. A candidate that survives realistic costs but fails stressed costs cannot enter paper observation.

## Feature Robustness

Feature robustness is recorded in `RP1_FEATURE_APPENDIX.csv`. SHAP analysis was not run because SHAP is not installed locally and adding a dependency would violate the frozen engineering posture. Native feature importance, permutation-style family ablation, and noisy-feature stress are recorded instead.

## Statistical Validation

Statistical evidence is recorded in `RP1_STATISTICAL_APPENDIX.csv`. The appendix includes block-bootstrap confidence intervals, permutation p-values, Benjamini-Hochberg q-values, and White Reality Check / SPA-style proxies. These are screening statistics, not final proof of alpha.

## Failure Analysis

Failure rows recorded: 60.

Common failure modes include weak directional evidence, confidence intervals crossing chance, sensitivity to cost assumptions, thin regime coverage, and insufficient evidence for the 2025-2026 untouched holdout period.

## Paper Observation Decision

No candidate is approved for paper observation. Human-reviewed qualification remains blocked.

## Limitations

- The final 2025-07-01 onward holdout was intentionally not evaluated.
- Monetary policy regimes are proxied through local price/volatility regimes; no point-in-time central-bank release calendar is available in the local dataset.
- SHAP was not run because the dependency is not installed.
- The stock universe remains survivorship-prone and narrow.
- Mutual fund evidence is exploratory and small-sample.
- The statistical tests are screening controls and should not be interpreted as proof of tradable alpha.

## Milestone 1 Decision

RP1 ROBUSTNESS INCONCLUSIVE -- additional evidence is required.
