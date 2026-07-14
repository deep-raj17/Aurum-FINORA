# Research Change Control Policy

Status date: 2026-07-09

## Principle

FINORA is now a quantitative financial research laboratory. The platform build is
complete enough for current research needs.

No code change should be made unless it is motivated by evidence from the research
process.

## Rule

Every future code change must answer:

```text
Which research result showed that this change is necessary?
```

If there is no evidence-based answer, do not make the change.

Every future commit must answer a research question. If a commit cannot be connected
to a research question, experiment result, reproducibility issue, or documented
validation need, it should not be made.

FINORA v1 is the frozen engineering baseline. Future versions should represent
research milestones, not feature accumulation.

The required decision flow is:

```text
Research -> Evidence -> Decision -> Engineering only if necessary
```

Every accepted hypothesis must include a documented failure condition:

- What evidence would invalidate it.
- What market changes would cause the signal to be retired.
- Which metrics would trigger re-evaluation.

## Allowed Changes

Allowed changes include:

- Fixing correctness bugs found during research.
- Improving reproducibility when an experiment cannot be repeated.
- Improving data quality when research identifies a concrete data defect.
- Adding a feature only when a research program shows the current feature set cannot
  answer an important hypothesis.
- Improving transaction-cost assumptions when paper-trading or robustness analysis
  shows current assumptions are unrealistic.
- Adding statistical tests when existing validation is insufficient for a candidate
  signal.
- Improving documentation when research conclusions need clearer lineage.
- Maintenance required to preserve reproducibility, security, or dependency health.

## Discouraged Changes

Do not add:

- New LLMs because they are new.
- New forecasting models because they are popular.
- New databases because they are fashionable.
- New dashboards unless paper-trading review proves the current journal/templates are
  insufficient.
- New APIs unless a research workflow requires them.
- Broker integrations before paper trading has demonstrated sustained usefulness.
- Autonomous trading logic.
- Research lineage tooling before the current knowledge base becomes insufficient.

## Required Justification

Every meaningful future change should document:

- Research program or experiment ID.
- Problem observed.
- Evidence that the current system cannot answer the research question.
- Proposed change.
- Expected research benefit.
- Risks or ways the change could increase overfitting.
- Validation plan.
- Failure condition for any accepted hypothesis or promoted signal.

## Examples

Acceptable:

```text
Research Program 1 shows that macro variables consistently improve 20-day forecasts
for ETFs, but current campaign features cannot ingest the required rate and inflation
series. Add a macro feature ingestion step and rerun the same campaign.
```

Acceptable:

```text
Paper-trading review shows transaction costs erase apparent edge. Improve cost and
slippage modeling before running another campaign.
```

Not acceptable:

```text
Add a new transformer model because it may perform better.
```

Not acceptable:

```text
Add another dashboard before any paper-trading review has created a dashboard-shaped
problem.
```

## Current Standing

FINORA should now be measured by research quality:

- Hypotheses tested.
- Experiments completed.
- Signals rejected.
- Robustness analyses performed.
- Paper-trading decisions reviewed.
- Lessons captured in the research journal.

The project should not be measured by lines of code, number of models, or number of
technologies.
