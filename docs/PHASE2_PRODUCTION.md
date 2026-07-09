# FINORA Phase 2 production guide

## Runtime architecture

```text
Provider APIs -> resilient connectors -> quality gate -> immutable lake
                                                  |
                                                  v
                                      point-in-time feature store
                                                  |
            +----------------+--------------------+------------------+
            v                v                    v                  v
       Chronos-2       NeuralForecast       XGBoost/LightGBM    risk models
            +----------------+--------------------+
                             v
                walk-forward selection + conformal calibration

Evidence -> semantic chunks -> Qdrant dense + BM25 -> RRF -> cross-encoder
                                                           |
                                                           v
                                                    cited evidence
                                                           |
                                              GPT-OSS synthesis only

Entities -> transformer NER -> Neo4j evidence relationships -> graph paths
```

## Analysis sequence

```text
Client -> API: authenticated request
API -> data/feature services: cutoff-safe inputs
API -> forecast ensemble: probabilistic forecast
API -> risk engine: deterministic risk metrics
API -> RAG: time-aware evidence
RAG -> GPT-OSS: evidence + computed metrics
GPT-OSS -> API: structured cited explanation
API -> audit store: report hash + chained event
API -> Client: report requiring human review
```

GPT-OSS is never used for forecasts, indicators, or risk calculations. Evidence is
untrusted input, structured output is validated, and unknown citation IDs are rejected.

## Data synchronization

Configure provider credentials using environment variables or mounted `*_FILE` secrets.
`DataSynchronizer` resumes from SQLite checkpoints, validates canonical `MarketBar`
records, writes deterministic gzip content to the content-addressed lake, and advances
the checkpoint only after the quality report accepts the batch.

Run source-specific credentialed integration tests before enabling a connector. Vendor
entitlements, symbol conventions, exchange calendars, and rate limits differ.

## Forecast deployment

Install `.[stats,deep]`. Configure only specialists whose model weights are available.
`ProductionForecastEngine` evaluates specialists on chronological rolling origins,
selects by out-of-sample RMSE, records regime and directional/coverage diagnostics, and
widens intervals using held-out absolute conformal residuals.

Chronos-2 is zero-shot. PatchTST, TFT, and N-HiTS train through NeuralForecast with
validation and quantile loss. XGBoost and LightGBM use direct multi-horizon quantile
models. No adapter silently falls back to a different model.

## Distillation and quantization

Production `TeacherEnsemble` requires explicit forecast, FinBERT, trained risk, and
GPT-OSS feature teachers. Offline baselines require the
`--allow-offline-baselines` flag and are unsuitable for model validation.

Train with `aurum kdq-train`, export QAT-derived TorchScript or ONNX, then use ONNX
Runtime dynamic/static INT8 or TensorRT FP16/BF16/INT8 compilation. Record latency,
peak memory, and numerical error with `aurum.kdq.benchmark.benchmark_predictor`.
Artifacts stay `REQUIRES_HUMAN_VALIDATION` until asset/regime walk-forward results,
calibration, stress tests, bias review, and model-risk approval are attached.

## Security and operations

- Use `compose.production.yml` and mounted secrets.
- Terminate TLS/OAuth at the ingress or integrate `JWTAuthenticator`.
- Map JWT roles through `require_permission`.
- Encrypt sensitive fields with AES-256-GCM and rotate keys outside the database.
- Apply `RAGContentGuard` before indexing and verify source hashes.
- Run dependency audit in CI and image scanning in the registry.
- Scrape `/metrics`; start Prometheus/Grafana with the `observability` profile.
- Configure OTLP with `configure_opentelemetry` and an authenticated collector.

## Verification

```bash
ruff check src tests scripts
ruff format --check src tests scripts
mypy src
pytest --cov=aurum --cov-report=term-missing --cov-fail-under=95
docker compose config
docker compose --profile observability config
```

Credentialed provider, GPU accuracy/latency, OAuth/JWKS, Qdrant, Neo4j, and failure-
recovery tests must run in the target environment. Unit tests do not establish market
fitness, regulatory approval, or safe autonomous trading.

## Troubleshooting

- `artifact is not deployed`: seed the external `aurum_kdq_artifacts` volume.
- model import error: install the matching optional extra and verify compatible CUDA.
- empty provider batch: check symbol/entitlement/time interval; empty data is not
  converted into synthetic data.
- quality rejection: inspect issue codes and repair upstream data; checkpoints remain
  at the last accepted record.
- calibration drift: suspend the model, rerun rolling evaluation by regime, and require
  model-risk sign-off before redeployment.
