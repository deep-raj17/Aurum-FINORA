# Independent review: RP1 Publication 005

Review date: 2026-07-14

Reviewer role: independent quantitative research, statistical, reproducibility, and
research-governance reviewer.

## Scope and independence

This review examined Publication 005 and its stored evidence without accessing the
protected post-2025-07-01 holdout, retraining candidates, tuning models, beginning
paper observation, or modifying the Publication 005 verdict. The reviewer had no
role in selecting the candidate set or interpreting the original results.

Materials reviewed: Publications 001--005, the RP1 protocol, dataset/split and
baseline reports, frozen YAML, runner and focused tests, full and failed-run
directories, decision artifact, source inventory, predictions, metric appendices,
environment and Git metadata.

## Publication identity and provenance

| Item | Publication value | Independently verified value | Match | Notes |
| --- | --- | --- | --- | --- |
| Publication ID | RP1_PUBLICATION_005_TRUE_ROBUSTNESS_RERUN | same | Yes | frozen YAML and decision artifact agree. |
| Experiment ID | RP1_PUB005_TRUE_ROBUSTNESS_20260714T054241Z_7574f5fca030 | same | Yes | immutable full-run directory. |
| Config hash | 7574f5fca030... | 7574f5fca030b16f36e31c4d7e550cb305030e166fb03cf4789a37390d83c92f | Yes | recomputed with `canonical_config_hash`. |
| Git commit | bf80566ddaebd3c4926885d18e3ea32205286ee1 | same | Yes | dirty state was recorded. |
| Environment | Python 3.11.9, NumPy 1.26.4, pandas 2.3.3, sklearn 1.9.0 | same | Yes | stored `environment.json`. |

The preserved failed run `...20260714T053904Z_7574f5fca030` has the identical frozen
configuration hash. Its partial evidence files precede report assembly and it has no
decision artifact. The failure is consistent with the missing optional `tabulate`
formatter used only for report rendering; it did not alter candidates, assets, seed,
costs, scenarios, or computed model metrics in the successful rerun.

## Configuration, data, and temporal controls

The YAML is valid and explicitly freezes three models, 20-day direction target,
9 ETFs, 6 forex pairs, 5 narrowed stocks, seed 42, costs of 0/8/15/25 bps, and the
stated scenario classes. It does not freeze all analytical details: fold counts,
model parameters, purge/embargo, feature-selection policy, and decision aggregation
remain in code. That is a reproducibility concern.

All 20 inventory entries are readable and hashed. The stored range ends no later
than 2025-06-02; prepared prediction timestamps end at 2025-05-30. The runner filters
`date < 2025-07-01` before target construction, so a 20-day target cannot enter the
protected period. Train-fold medians are fit on training rows. No protected timestamp
appears in stored predictions, statistical inputs, or cost inputs.

| Final-test guard | Expected | Observed | Pass |
| --- | --- | --- | --- |
| Feature timestamp before cutoff | Yes | Source frame is filtered before preparation | Yes |
| Target-end timestamp before cutoff | Yes | Latest prediction date 2025-05-30 | Yes |
| Preprocessing excludes holdout | Yes | Fold medians use training rows | Yes |
| Statistical/economic inputs exclude holdout | Yes | Stored predictions end 2025-05-30 | Yes |

`make_folds` is chronological and uses `train_end = test_start - 20 - 5`. This gives
at least a 20-row purge plus 5-row embargo. The focused test verifies the index
inequality. Exact fold-boundary files are not stored, so the historical split cannot
be independently reconstructed from an artifact alone.

## Execution reconciliation and alignment

The full count is reconciled: `(15 ETF/forex assets * 3 models * 11 scenarios) +
(5 stocks * 3 models * 4 scenarios) = 555` asset-scenario rows. Four cost scenarios
produce `555 * 4 = 2,220` cost rows. The smoke count is
`(2 * 3 * 11) + (1 * 3 * 4) = 78`, with `78 * 4 = 312` cost rows. Regime rows are
conditional on partitions containing at least two observations, explaining 213 smoke
and 1,431 full rows.

Candidate and momentum-baseline predictions are generated in the same test-fold loop,
so they share asset, timestamp, target, and cost input. They are not stored as a
separate baseline-comparison artifact, and the protocol-required naive, random,
buy-hold, moving-average, linear, and nonlinear baselines are not all implemented in
Publication 005. This limitation prevents a baseline-superiority finding but does not
weaken the conservative non-promotion decision.

## Statistical, predictive, and economic review

The primary screening set contains 60 asset-model rows. Balanced accuracy is commonly
at or below chance; group means range from 0.4302 to 0.5203. The stored result is
therefore consistent with the statement that most primary balanced accuracies are near
or below chance. The two local screening candidates do not establish cross-asset,
cross-regime, or multi-seed evidence.

The statistical controls are not sufficient for a final financial inference. The
runner uses a block length of 5 while labels overlap for 20 trading observations, and
its label permutation is IID rather than block-permuted. It also uses 200 resamples,
not the protocol's final-run default of at least 1,000, and labels White/SPA entries
as proxies rather than implementing the required tests. Benjamini-Hochberg is a
screening correction and was not treated as definitive support.

Economic outputs correctly lag positions and apply the configured costs. They remain
research-only: 20-day forward returns overlap when evaluated at daily frequency, so
annualized Sharpe/return values cannot be used as tradable-performance evidence. The
publication's warning that positive ETF economic outputs with weak direction evidence
are not proof of a signal is proportionate. JPY remains weak; stock conclusions remain
narrow and fragile; no broad asset-class robustness is demonstrated.

Probability values are within [0, 1], but the run lacks a dedicated collapse,
positive-rate, entropy, log-loss, calibration-slope, and calibration-intercept
appendix. One seed is inherited from the campaign and no evidence supports a
seed-stability claim.

## Decision and governance review

| Criterion | Required state | Observed state | Contribution |
| --- | --- | --- | --- |
| Protected holdout | No access | Passed | Supports validity. |
| Predictive evidence | Stable above-chance, broad | Not shown | Blocks promotion. |
| Baseline superiority | Full aligned inventory | Incomplete | Blocks promotion. |
| Dependence-aware statistics | Protocol-compliant | Incomplete | Blocks promotion. |
| Multiple assets/regimes/seeds | Required | One seed; mixed evidence | Blocks promotion. |
| Costs and economic rationale | Survive and be interpretable | Exploratory only | Blocks promotion. |

The runner's aggregate decision branch is too simple to independently establish pass,
fail, invalid, and inconclusive outcomes. Nevertheless, the observed evidence is
mixed, incomplete, and not promotable. `RP1 remains statistically inconclusive` is
supported and is more appropriate than a pass. `Paper observation: not approved` is
the required governance outcome.

## Reproducibility checklist

| Required artifact | Present | Review result |
| --- | --- | --- |
| Config snapshot/hash, environment, Git state, source inventory | Yes | Valid. |
| Eligibility and immutable output directory | Yes | Valid, 20/20 sources recorded. |
| Predictions, per-asset/regime/cost/statistical files | Yes | Traceable. |
| Exact split boundaries, aggregate metrics, baseline-comparison file | No | Material gap. |
| Per-seed, collapse, and reproducibility-checklist artifacts | No | Material gap. |
| Execution logs | No | Nonmaterial operational gap. |

## Claims review

Publication 005 and the decision JSON consistently prohibit alpha, profitability,
production readiness, investment advice, autonomous trading, commercial signal sales,
and institutional-readiness claims. Repository-wide language such as “alpha discovery”
in historical phase names is contextual, but should not be reused as a claim about
Publication 005.

## Material issues and required corrections

1. Replace or explicitly quarantine the 5-row bootstrap and IID permutation for
overlapping 20-day labels; use preregistered dependence-aware tests.
2. Produce immutable split-boundary, baseline-alignment, probability/collapse,
per-seed, aggregate-metric, and reproducibility-checklist artifacts.
3. Encode and test the full pass/fail/invalid/inconclusive decision matrix rather than
inferring the aggregate decision from the presence of local screening candidates.
4. Do not interpret overlapping-forward-return economic annualization as performance
evidence; document it as a diagnostic until a valid non-overlapping evaluation exists.

Nonmaterial corrections: correct the publication date, remove the mutual-fund scope
reference (the frozen config excludes it), and name the exact config hash in the
publication.

## Independent verdict and record decision

**Verdict: Conditionally accepted pending material corrections.**

**Research-record decision: Not approved until material corrections are completed.**

This is a validity decision about the publication record, not a positive signal
assessment. The RP1 inconclusive decision and paper-observation prohibition remain in
force. The only next permitted action is to document these corrections and conduct an
independent human review; no paper observation, productization, retraining, or
protected-holdout evaluation is authorized.
