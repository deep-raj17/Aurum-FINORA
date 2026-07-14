# RP1 Publication 005 material-corrections report

Status date: 2026-07-14

Successor experiment: `RP1_PUB005B_CORRECTED_20260714T063122Z_7ea9e0c5c389`

Predecessor: `RP1_PUB005_TRUE_ROBUSTNESS_20260714T054241Z_7574f5fca030`

## Result

**RP1 REMAINS STATISTICALLY INCONCLUSIVE.**

No candidate qualifies for paper observation. No alpha, profitability, production,
or investment-advice claim is supported.

## Corrections matrix

| Issue | Severity | Corrective method | Evidence | Outcome | Unresolved limitation |
| --- | --- | --- | --- | --- |
| Short IID bootstrap | Material | Moving-block CIs with requested 20/25/40 blocks | `statistical_artifact.csv` | 20-row block generated | 25/40 blocks exceed 21-row folds and are invalid, not silently shortened. |
| IID permutation | Material | Circular-shift null with fixed seeds | `statistical_artifact.csv` | 20-row test generated | Longer-block tests unavailable on short folds; no final inference is made. |
| Baseline coverage | Material | Random, historical mean, random walk, buy-and-hold, momentum, moving average, logistic regression | `baseline_alignment.csv`, `per_seed_metrics.csv` | Coverage and fold alignment recorded | Baseline superiority is not established. |
| Missing split artifacts | Material | Explicit chronological split table | `splits.csv` | Generated | Fold test windows remain too short for 25/40 resampling. |
| Missing per-seed evidence | Material | Seeds 11, 17, 23, 42 | `per_seed_metrics.csv` | Generated | Dispersion/collapse remains high. |
| Missing probability/collapse evidence | Material | Probability and collapse fields per model/asset/seed/fold | `per_seed_metrics.csv` | Generated | Dedicated calibration-bin artifact remains absent. |
| Missing aggregate artifact | Material | Model/asset-class aggregate | `aggregate_metrics.csv` | Generated | Does not convert diagnostic evidence into significance. |
| Reproducibility package | Material | Snapshot, manifest, command, checksums | successor directory | Generated | Hardware/GPU/model-binary hashes are incomplete. |
| Overlapping economics | Material | Label annualized outputs diagnostic | `economic_diagnostic.csv` | Preserved as diagnostic only | A non-overlapping economic evaluation remains required. |

## Findings

The successor used the same hypothesis, assets, 20-day target, chronological
pre-holdout boundary, and tree-model families. It adds four fixed seeds and aligned
baselines. Candidate mean balanced accuracy is mixed and frequently centered on 0.5;
collapse flags are common for tree-model and constant baselines. The package therefore
does not satisfy predictive breadth, seed stability, collapse-free operation, or
dependence-aware significance gates.

The original Publication 005 record and its failed-run artifacts are preserved and
unchanged. The successor cannot be submitted for independent re-review until the
long-block design is repaired with sufficiently long out-of-sample windows and the
remaining reproducibility artifacts are complete.

## Next allowed action

Repair the corrected protocol's test-window design without accessing the protected
holdout, then regenerate a successor evidence package for independent re-review.
