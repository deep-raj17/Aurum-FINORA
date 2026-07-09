# FINORA portfolio presentation

## One-minute summary

FINORA is an auditable financial intelligence research platform. It turns market data,
filings, news, macro signals, graph relationships, and model outputs into governed
decision-support reports with forecasts, uncertainty intervals, risk metrics,
citations, and hash-chained audit evidence.

The project is built to demonstrate engineering judgment around financial AI:
validation, leakage control, human review, reproducibility, observability, and honest
model-risk boundaries.

## What FINORA does

- Normalizes financial and macro data through provider connectors.
- Produces transparent baseline forecasts through the default `ForecastEngine`.
- Provides optional specialist adapters for Chronos, NeuralForecast, LightGBM,
  XGBoost, CatBoost, FinBERT, graph reasoning, Qdrant retrieval, and GPT-OSS-style
  report synthesis boundaries.
- Calculates risk, scenarios, costs, slippage, backtest metrics, and calibration
  evidence.
- Persists reports, citations, and audit events for reproducibility.
- Exposes the workflow through FastAPI, CLI, Docker, Kubernetes, Helm, Terraform, and
  monitoring assets.

## Architecture

```text
Provider data / filings / news / macro
        |
        v
Connectors -> quality checks -> data lake -> feature store
        |
        v
Default path: FinoraPipeline -> ForecastEngine -> risk/scenarios/audit/report
        |
        +--> Optional governed path:
             specialists -> FINORA-MoE fusion/router -> calibration/backtesting
             RAG/graph evidence -> GPT-OSS reasoning boundary -> audit
```

The default portfolio demo uses the deterministic pipeline. FINORA-MoE is implemented
as a governed architecture, but it is not claimed as the default production workflow
until the full routed path has its own end-to-end validation evidence.

## Models and techniques

| Area | Models / methods |
|---|---|
| Default forecasting | random walk, drift, robust drift, Holt linear, AR(1), ridge autoregression |
| Specialist forecasting | Chronos, PatchTST, iTransformer, TFT, TiDE |
| Tabular experts | LightGBM, XGBoost, CatBoost quantile specialists |
| Text | FinBERT adapter plus auditable lexical fallback |
| Graph | Neo4j persistence and graph attention expert |
| Retrieval | Qdrant dense + BM25 hybrid retrieval, RRF, cross-encoder reranking |
| Reasoning boundary | GPT-OSS remote-only grounded report path with citation validation |
| Governance | anti-lookahead validation, hash-chained audit, model-risk release gates |

## Engineering challenges solved

- Kept optional heavy ML dependencies fail-closed instead of silently substituting
  fake model behavior.
- Added explicit live-provider and real-model gates so skipped external validation is
  visible rather than treated as success.
- Separated research-grade local evidence from staging and production approval.
- Built deterministic default demos that work without secrets or private data.
- Added Windows-safe validation notes for `pyarrow` and mypy timeout behavior.
- Repaired Git hygiene and excluded secrets, model weights, local caches, and large
  artifacts from the public release.

## Validation evidence

- Phase 8 public release: [PHASE8_PUBLIC_RELEASE.md](PHASE8_PUBLIC_RELEASE.md)
- Phase 7 gates: [PHASE7_GITHUB_RELEASE_READINESS.md](PHASE7_GITHUB_RELEASE_READINESS.md)
- Phase 6 real execution: [PHASE6_REAL_EXECUTION_VALIDATION.md](PHASE6_REAL_EXECUTION_VALIDATION.md)
- RTX 4070 benchmark: [../reports/benchmarks/rtx4070_real_models.md](../reports/benchmarks/rtx4070_real_models.md)
- Research artifact: [../reports/research/yahoo-aapl-xgboost-expanding.json](../reports/research/yahoo-aapl-xgboost-expanding.json)

Phase 7 local gates passed: Ruff, Ruff format check, pytest, timeout-safe mypy, and
runtime API health.

## Research honesty

The Yahoo/AAPL/XGBoost expanding-window run proves pipeline execution on real market
data. It does not prove alpha:

- Directional accuracy: 0.4286
- Interval coverage: 0.4286
- Net Sharpe: -4.0898
- Bootstrap p-value: 0.868

## Limitations

- No live-provider matrix without approved credentials.
- No production-approved calibration, regime, or bias datasets.
- No staging SLO, soak, failover, ingress-security, or signed approval package.
- GPT-OSS 120B remains remote-only and not production-validated here.
- FINORA-MoE/KD-Q deployment artifacts need governed ONNX/TensorRT/INT8 accuracy
  validation before deployment claims.

## Future work

1. Add approved provider credentials and run the full live-provider matrix.
2. Expand research validation across assets, horizons, regimes, and market stress.
3. Validate licensed calibration and bias datasets.
4. Wire and validate the full FINORA-MoE path end to end.
5. Run hardened staging performance, reliability, recovery, and security tests.
6. Complete independent model-risk, security, compliance, data-owner, and engineering
   sign-offs.
