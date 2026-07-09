# Aurum — FINORA Financial Intelligence System

FINORA is an auditable, probabilistic financial decision-support platform. It combines
chronological forecasting, evidence retrieval, risk and scenario analysis, textual
intelligence, contagion graphs, cost-aware backtesting, drift monitoring, and immutable
audit records.

The core model architecture is **FINORA-MoE**, a multimodal financial
mixture-of-experts system. **FINORA-KD-Q** remains the compact deployment student:
it is distilled from the governed MoE ensemble and separate evidence/reasoning
teachers, with quantization-aware training. See
[FINORA-MoE](docs/FINORA_MOE_ARCHITECTURE.md) and
[FINORA-KD-Q](docs/FINORA_KDQ.md).

It is **not investment advice**. Human review is mandatory before live capital
allocation or client-facing distribution.

## Current validation status

- Research validated: YES
- Real-execution validated: YES
- GitHub ready: YES, after Phase 7 local gates passed
- Staging-ready: NO
- Production-approved: NO

- 131 tests passed
- 26 skipped
- Ruff passed
- Ruff format check passed
- Mypy passed for 74 source files with a process-based 60 second timeout guard
- RTX 4070 benchmark generated
- Yahoo AAPL XGBoost expanding-window research run completed
- Qdrant and Neo4j reachable
- API health endpoint verified at runtime
- Windows pyarrow issue isolated with `pyarrow==16.1.0`; WSL/Linux remains the recommended validation environment if native Windows collection issues recur
- Live provider tests blocked by credentials

### Evidence links

- [FINORA_RESEARCH_VALIDATION_REPORT.md](FINORA_RESEARCH_VALIDATION_REPORT.md)
- [docs/PHASE7_GITHUB_RELEASE_READINESS.md](docs/PHASE7_GITHUB_RELEASE_READINESS.md)
- [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)
- [reports/providers/provider_status.md](reports/providers/provider_status.md)
- [reports/research/research_dataset_v1.md](reports/research/research_dataset_v1.md)
- [reports/benchmarks/rtx4070_real_models.md](reports/benchmarks/rtx4070_real_models.md)
- [reports/research/yahoo-aapl-xgboost-expanding.json](reports/research/yahoo-aapl-xgboost-expanding.json)
- [docs/PORTFOLIO_PRESENTATION.md](docs/PORTFOLIO_PRESENTATION.md)
- [docs/GITHUB_READY_HANDOFF.md](docs/GITHUB_READY_HANDOFF.md)

## What is implemented

| Layer | Production behavior |
|---|---|
| Data | Yahoo, Alpha Vantage, Tiingo, Stooq, Nasdaq Data Link, FRED, SEC, CoinGecko, Binance, FMP, Finnhub, World Bank, IMF, ECB, and OECD adapters with retry/cache/checkpoints |
| Data lake | Immutable content-addressed layers, lineage manifests and integrity verification |
| Retrieval | Qdrant dense+BM25 RRF, metadata/time filters, cross-encoder reranking, chunk hashes, and citations |
| Forecasting | Primary PatchTST/iTransformer experts; TFT/TiDE multi-horizon experts; Chronos foundation expert; LightGBM/XGBoost/CatBoost tabular experts |
| MoE intelligence | FinBERT text expert, graph-attention expert, cross-attention over eight modalities, sparse context router, multi-task prediction heads |
| Validation | Purged walk-forward, rolling and expanding windows, regime slices, conformal prediction, ECE, transaction-cost returns, Sharpe/Sortino/Calmar/max drawdown |
| Risk | Historical VaR/CVaR, drawdown, duration, volatility, skew, kurtosis, beta, liquidity and stress |
| Scenarios | Calibration-adjusted baseline/downside/upside priors with explicit basis |
| NLP | FinBERT production adapter, auditable offline fallback, rolling momentum, filing comparison |
| Graph | Neo4j entity/relationship persistence, transformer NER, evidence edges, and contagion paths |
| Backtesting | Lagged execution, spread/slippage, gross/net metrics, benchmarks, bootstrap significance and PBO proxy |
| Governance | Anti-lookahead checks, input hashes, reproducibility fields, regulatory flags |
| Storage | SQLite report/evidence store and hash-chained audit events |
| Operations | FastAPI, CLI, JWT/RBAC primitives, rate limiting, Prometheus/Grafana, OpenTelemetry, Docker and CI |

Optional packages in `pyproject.toml` provide integration points for heavier statistical,
ML, transformer, vector-database, graph-database, and MLOps deployments. The core never
claims an optional model is active unless it actually ran.

## Default execution path

The default API and CLI analysis workflow uses the lightweight, deterministic
`ForecastEngine` through `FinoraPipeline`. That path is intended for transparent local
research reports and API smoke validation. FINORA-MoE components, production
specialist adapters, RAG, and GPT-OSS reasoning are implemented as governed optional
layers, but they are not the default end-to-end production workflow unless explicitly
configured and wired into a run.

To enable FINORA-MoE execution, install the relevant extras, provide approved model
weights and service endpoints, construct the specialist embeddings required by
`aurum.moe.FINORAMoE`, and validate the full routed path with licensed datasets and
model-risk review. Do not treat MoE architecture evidence as production workflow
evidence until that end-to-end route has passed validation.

## FINORA-MoE architecture

```text
Data Lake → Feature Store → Specialist Experts → Cross-Attention Fusion
          → MoE Router → Prediction Heads → Calibration → Backtesting
          → Audit Ledger → API/UI
```

The router conditions on asset class, volatility regime, modality availability,
market regime, forecast horizon, liquidity, sentiment strength, and macro shocks.
It masks unavailable experts and selects a sparse top-k mixture. LSTM, GRU, vanilla
RNN, and simple Transformer models are retained only as benchmark/fallback baselines;
they are not primary routed experts.

Prediction heads cover returns, direction, volatility, risk, VaR/CVaR, drawdown,
regime, scenario probabilities, and evidence-linked explanations. GPT-OSS is confined
to grounded reasoning, RAG, and report-teacher roles; it is not a raw price forecaster.

### GPT OSS 120B reasoning layer

```text
Data + Forecast Experts + Risk Experts + Graph Experts + RAG Evidence
                              ↓
                    Evidence Pack Builder
                              ↓
                 GPT OSS 120B (remote only)
                              ↓
              Grounded Financial Reasoning Report
                              ↓
                Audit Ledger + Human Review Gate
```

GPT OSS 120B is FINORA's elite reasoning, synthesis, scenario, explanation, audit,
compliance, report, coordination, and knowledge-distillation teacher layer. It
receives computed specialist outputs; it does not predict prices, compute indicators,
execute backtests, calculate VaR/CVaR, optimize portfolios, or clean/engineer data.

An RTX 4070 12GB cannot host this model. FINORA rejects local GPT OSS 120B loading and
supports it through remote OpenAI-compatible endpoints such as hosted vLLM/SGLang or
cloud GPU services. A smaller 8B–14B local model is development-only and is never
treated as equivalent validation evidence. See
[GPT OSS integration](docs/GPT_OSS_INTEGRATION.md),
[reasoning policy](docs/LLM_REASONING_POLICY.md), and
[RAG safety](docs/RAG_SAFETY.md).

## Phase 3A research workflow

Phase 3A adds secure `.env` provider configuration, workstation-aware Chronos/FinBERT/
GPT-OSS policies, real-provider walk-forward research reports, optional Backtrader
event simulation, expanded Neo4j contagion relationships, and an append-only
PostgreSQL-compatible audit ledger. It remains research decision support—not autonomous
trading or production approval.

```powershell
Copy-Item .env.example .env
# Populate secrets locally, then explicitly authorize live tests:
$env:FINORA_RUN_LIVE_TESTS="1"
pytest -m live tests/integration/test_live_providers.py -ra

python scripts/run_research_validation.py `
  --provider yahoo --symbol AAPL --model xgboost `
  --window expanding --output reports/research
```

See [research validation](docs/PHASE3_RESEARCH_VALIDATION.md),
[model downloads](docs/MODEL_DOWNLOADS.md), [API key setup](docs/API_KEYS_SETUP.md),
[GPU benchmarking](docs/GPU_BENCHMARKING.md), [backtesting](docs/BACKTESTING.md), and
the [portfolio roadmap](docs/PROJECT_PORTFOLIO_ROADMAP.md).

## Quickstart

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,api]"

# Explicit development smoke (simulated; never a validation dataset)
aurum demo --allow-synthetic
```

## How to reproduce

```powershell
# 1) Setup venv
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -e ".[dev,api]"

# 3) Run tests
pytest -q -ra

# 4) Run lint
ruff check src tests scripts

# 5) Run mypy with a Windows-safe timeout guard
$p = Start-Process -FilePath mypy -ArgumentList 'src' -PassThru -NoNewWindow
if (-not $p.WaitForExit(60000)) { $p.Kill(); throw 'mypy timed out after 60 seconds' }
if ($p.ExitCode -ne 0) { throw "mypy failed with exit code $($p.ExitCode)" }

# 6) Run benchmark
python scripts/benchmark_phase6_real_models.py --iterations 1

# 7) Run research validation
python scripts/run_research_validation.py --provider yahoo --symbol AAPL --model xgboost --days 180 --horizon 3 --lags 30 --window expanding --output reports/research

# 8) Run API health
python -m uvicorn aurum.api.main:app --host 127.0.0.1 --port 8000
# Then visit http://127.0.0.1:8000/health
```

Open `http://localhost:8000` for the landing page or `/docs` for OpenAPI.
The optional Streamlit console runs at `http://localhost:8501` with
`docker compose --profile ui up --build`.

## Portfolio section

FINORA is positioned as a validated research platform and GitHub portfolio project. The core evidence trail lives in [FINORA_RESEARCH_VALIDATION_REPORT.md](FINORA_RESEARCH_VALIDATION_REPORT.md) and [docs/PORTFOLIO_PRESENTATION.md](docs/PORTFOLIO_PRESENTATION.md).

The Yahoo/AAPL/XGBoost expanding-window run proves the research pipeline executes on
real market data; it does not prove market alpha. Its headline metrics were
directional accuracy 0.4286, interval coverage 0.4286, net Sharpe -4.0898, and
bootstrap p-value 0.868.

## CLI

```text
aurum demo [--days 180] [--horizon 5]
aurum forecast prices.csv --target SPY --horizon 5 --output markdown
aurum ingest filing.txt --origin SEC:10-K --published-at 2025-02-15T12:00:00Z
aurum audit
aurum kdq-generate --output data/kdq/training.jsonl
aurum kdq-train data/kdq/training.jsonl
aurum kdq-export artifacts/finora-kdq --format int8
```

CSV input is normalized as:

```csv
timestamp,value,entity,unit,release_timestamp
2025-01-02T00:00:00Z,100.25,SPY,USD,2025-01-02T21:00:00Z
```

## API

Main endpoints:

- `POST /v1/forecast`
- `POST /v1/evidence`
- `GET /v1/reports`
- `GET /v1/reports/{run_id}`
- `GET /v1/reports/{run_id}/markdown`
- `POST /v1/backtest`
- `POST /v1/drift`
- `POST /v1/sentiment`
- `POST /v1/filing-compare`
- `POST /v1/macro-regime`
- `POST /v1/contagion`
- `POST /v1/kdq/predict`
- `GET /health`
- `GET /metrics`

Set `AURUM_API_KEY` or `AURUM_API_KEY_FILE` outside local development; clients then
send `X-API-Key`. OIDC/JWT verification and role permissions are available in
`aurum.security` for gateway integration.

## Project layout

```text
src/aurum/
  api/             FastAPI application
  data/            ingestion adapters and normalized data contracts
  forecast_system.py production specialist adapters, selection, and calibration
  moe.py           FINORA-MoE registry, fusion, router, graph expert, and heads
  validation.py    purged walk-forward evaluation
  rag.py           production hybrid retrieval and reranking
  risk.py          market and liquidity risk
  scenarios.py     calibrated scenario construction
  sentiment.py     textual intelligence
  graph.py         contagion graph
  backtest.py      cost-aware strategy evaluation
  monitoring.py    data/model drift indicators
  governance.py    cutoff enforcement and audit metadata
  storage.py       reports, evidence, hash-chained events
  service.py       application orchestration
  reporting.py     deterministic Markdown output
  cli.py           operational CLI
```

See [FINORA-MoE architecture](docs/FINORA_MOE_ARCHITECTURE.md),
[model stack](docs/MODEL_STACK.md), [router](docs/MOE_ROUTER.md),
[fusion](docs/FUSION_LAYER.md), [baselines](docs/BASELINE_MODELS.md),
[MoE distillation](docs/DISTILLATION_MOE.md), [system charter](prompts/system_prompt.md),
[data platform](docs/DATA_PLATFORM.md), and [security policy](SECURITY.md).

## Deployment

```bash
docker compose up --build
docker compose --profile observability up --build
```

For hardened settings, layer `compose.production.yml`, supply the required secret files,
terminate TLS at an authenticated ingress, and run credentialed integration tests:

```bash
docker compose -f docker-compose.yml -f compose.production.yml up -d
```

See [Phase 2 production guide](docs/PHASE2_PRODUCTION.md) for data sync, model serving,
training, observability, benchmarking, and troubleshooting.

## Phase 3 production validation

Phase 3 adds credential-gated live-provider tests, real-weight model tests, GPU/ONNX/
GPT-OSS benchmark runners, regime-aware calibration datasets, bias analysis, load and
failure-recovery tests, approval packets, Kubernetes/Helm, and Terraform.

The repository is **engineering-ready**. It is not production-approved: the checked-in
release gates deliberately remain blocked until live data, real weights, target GPU
benchmarks, full calibration/backtests, security scans, and signed human model-risk and
compliance approvals all pass. See [Phase 3 validation](docs/PHASE3_PRODUCTION_VALIDATION.md).

## Phase 6 real execution activation

The local RTX 4070 workstation has executed real FinBERT and Chronos Tiny weights,
PatchTST/iTransformer/TFT/TiDE CUDA training smokes, all three tabular expert
runtimes, and local Qdrant/Neo4j round trips. The current classification is
**real-execution validated**, not staging-ready and not production-approved.

See [Phase 6 validation](docs/PHASE6_REAL_EXECUTION_VALIDATION.md),
[real model evidence](reports/models/real_model_validation.md),
[provider gate](reports/providers/live_provider_validation.md), and
[RTX 4070 benchmark](reports/benchmarks/rtx4070_real_models.md).

## Epistemic limits

- Offline intervals assume locally stable Gaussian innovations with square-root-time
  variance scaling; fat tails and discontinuities can invalidate them.
- Scenario probabilities are calibration-adjusted policy priors, not posteriors.
- Historical risk is not a bound on future loss.
- Development smoke data and offline baseline teachers require explicit opt-in and
  artifacts remain marked `REQUIRES_HUMAN_VALIDATION`.
- Optional model integrations fail closed when their weights/runtime are unavailable.
- Network paths are only as complete as the loaded relationship data.
