# FINORA interview talking points

## Elevator pitch

FINORA is a portfolio-grade research engineering platform for financial intelligence.
It demonstrates how to build AI-assisted decision support without overclaiming:
forecasts, uncertainty, evidence retrieval, risk, backtesting, API delivery, and audit
records are all validated and bounded by explicit model-risk controls.

## What to emphasize

- The project is intentionally honest: GitHub-ready research platform, not
  production-approved trading software.
- The default workflow is deterministic and reproducible without secrets.
- Heavy model integrations are optional and fail closed when dependencies, weights, or
  endpoints are not configured.
- Validation gates distinguish local unit tests, live provider tests, real-model tests,
  staging tests, and production approval.
- Auditability is not an afterthought: reports carry input hashes, evidence hashes,
  model versions, human-review flags, and immutable event-chain checks.

## Architecture answer

Use this framing:

```text
Data connectors and quality checks feed a research pipeline. The default API path uses
FinoraPipeline and ForecastEngine for reproducible local reports. Optional governed
layers add specialist models, FINORA-MoE routing, RAG, graph reasoning, and GPT-OSS
report synthesis. Outputs pass through risk, scenarios, backtesting, and audit storage.
```

## Models used

- Baselines: random walk, drift, robust drift, Holt linear, AR(1), ridge autoregression.
- Time-series specialists: Chronos, PatchTST, iTransformer, TFT, TiDE.
- Tabular experts: LightGBM, XGBoost, CatBoost.
- Text: FinBERT plus lexical fallback.
- Retrieval and graph: Qdrant, BM25/RRF, cross-encoder reranking, Neo4j, graph
  attention.
- Reasoning boundary: GPT-OSS remote-only, restricted to grounded explanation and
  report synthesis.

## Engineering challenges

- Preventing lookahead leakage in financial validation.
- Keeping optional ML and provider integrations honest when credentials or model
  weights are absent.
- Avoiding false production claims from local GPU smoke tests.
- Making a demo that works publicly without secrets or private data.
- Maintaining Git hygiene around `.env`, model cache, large data, generated artifacts,
  and private reports.

## Validation answer

Phase 7 passed local gates:

- `pytest -q -ra`: 131 passed, 26 skipped
- Ruff and Ruff format: passed
- Timeout-safe mypy: passed for 74 source files
- Runtime API health: passed

Phase 6 proved selected real local model/runtime execution on an RTX 4070 workstation.
This is runtime compatibility evidence, not production performance approval.

## Research honesty answer

The Yahoo/AAPL/XGBoost walkthrough proves pipeline execution, not alpha. Directional
accuracy was 0.4286, interval coverage was 0.4286, net Sharpe was -4.0898, and the
bootstrap p-value was 0.868.

## Good limitations answer

The next real blockers are external and governance-heavy: approved provider
credentials, licensed multi-asset datasets, full MoE/KDQ deployment validation,
staging soak/failover/security tests, and signed model-risk/compliance approvals.

## Future-work answer

The next engineering step is not adding more models. It is taking the existing system
through broader validation: provider matrix, multi-asset walk-forward tests, governed
artifact export checks, hardened staging, and independent review.
