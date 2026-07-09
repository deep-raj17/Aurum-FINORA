# FINORA Financial Intelligence System

FINORA is a research engineering platform for auditable financial decision support. It
combines time-series forecasting, evidence retrieval, risk and scenario analysis,
sentiment, graph reasoning, backtesting, API delivery, and immutable audit records.

FINORA is **not investment advice** and is not approved for autonomous trading,
client-facing recommendations, staging, or production use. Human review is mandatory.

## Validation Status

| Area | Status |
|---|---|
| Research engineering platform | yes |
| Research-validated | yes |
| Real-execution validated | yes |
| GitHub portfolio-ready | yes |
| Staging-ready | no |
| Production-approved | no |

Phase 7 local gates passed:

- `pytest -q -ra`: 131 passed, 26 skipped
- `ruff check src tests scripts`: passed
- `ruff format --check src tests scripts`: passed
- timeout-safe `mypy src`: passed for 74 source files
- Runtime API health: `status=ok`, `mode=decision-support`, `audit_chain_valid=True`

Skipped tests are intentionally gated behind live provider credentials or approved
real-model runtime configuration.

## Architecture

```text
Market data, filings, news, macro inputs
        |
        v
Ingestion connectors -> quality checks -> data lake / feature store
        |
        v
Forecasting, tabular, text, graph, risk, and retrieval specialists
        |
        v
FINORA-MoE architecture: fusion, sparse router, prediction heads
        |
        v
Calibration -> risk/scenarios -> backtesting -> evidence citations
        |
        v
FastAPI / CLI / reports -> hash-chained audit ledger
```

The default API and CLI workflow uses the lightweight deterministic `ForecastEngine`
through `FinoraPipeline`. FINORA-MoE, production specialist adapters, RAG, graph
services, and GPT-OSS reasoning are implemented as governed optional layers, but they
are not claimed as the default end-to-end production workflow unless explicitly wired,
configured, and validated.

## Implemented Capabilities

| Layer | Summary |
|---|---|
| Data | Yahoo, Alpha Vantage, Tiingo, Stooq, FRED, SEC, CoinGecko, Binance, World Bank, IMF, Nasdaq Data Link, FMP, Finnhub, ECB, OECD adapters |
| Forecasting | Deterministic baseline engine, Chronos adapter, NeuralForecast adapters, LightGBM/XGBoost/CatBoost quantile specialists |
| MoE | Cross-attention fusion, contextual sparse router, graph expert, multi-task prediction heads |
| Retrieval | Time-aware citations, Qdrant hybrid search, BM25/dense RRF, cross-encoder reranking |
| Risk/backtest | VaR/CVaR, drawdown, costs, slippage, net metrics, bootstrap/PBO-oriented evidence |
| Governance | Anti-lookahead checks, input hashes, audit metadata, human-review gates |
| Operations | FastAPI, CLI, Docker Compose, Kubernetes, Helm, Terraform, Prometheus/Grafana, CI |

## Reproduce Locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,api,kdq,data]"

ruff check src tests scripts
ruff format --check src tests scripts
pytest -q -ra

$p = Start-Process -FilePath mypy -ArgumentList 'src' -PassThru -NoNewWindow
if (-not $p.WaitForExit(60000)) { $p.Kill(); throw 'mypy timed out after 60 seconds' }
if ($p.ExitCode -ne 0) { throw "mypy failed with exit code $($p.ExitCode)" }
```

Run the API:

```powershell
python -m uvicorn aurum.api.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

Run the portfolio demo:

```powershell
scripts\demo_portfolio_run.ps1
```

On Linux/macOS/WSL:

```bash
bash scripts/demo_portfolio_run.sh
```

## Demo / Screenshots

The portfolio demo starts the API, checks health, runs one forecast request, runs one
sentiment example, and prints the audit-chain status. OpenAPI documentation is
available after startup at:

```text
http://127.0.0.1:8000/docs
```

Recommended screenshots for a portfolio page:

- `/docs` OpenAPI endpoint list
- `/health` response showing `audit_chain_valid=True`
- Example `/v1/forecast` response with forecast, intervals, risk, and audit block
- `reports/benchmarks/rtx4070_real_models.md`

## Evidence

- [Phase 8 public release report](docs/PHASE8_PUBLIC_RELEASE.md)
- [Phase 7 release readiness](docs/PHASE7_GITHUB_RELEASE_READINESS.md)
- [Project status](docs/PROJECT_STATUS.md)
- [Phase 6 real execution validation](docs/PHASE6_REAL_EXECUTION_VALIDATION.md)
- [RTX 4070 benchmark](reports/benchmarks/rtx4070_real_models.md)
- [Research validation report](FINORA_RESEARCH_VALIDATION_REPORT.md)
- [Yahoo/AAPL/XGBoost research artifact](reports/research/yahoo-aapl-xgboost-expanding.json)
- [GitHub handoff](docs/GITHUB_READY_HANDOFF.md)

## Research Honesty Note

The Yahoo/AAPL/XGBoost expanding-window run proves that the research pipeline executes
on real market data. It does **not** prove market alpha:

- Directional accuracy: 0.4286
- Interval coverage: 0.4286
- Net Sharpe: -4.0898
- Bootstrap p-value: 0.868

## Current Limitations

- Live-provider validation remains blocked until approved credentials are supplied.
- Full multi-asset, multi-horizon, regime-specific licensed datasets are not validated.
- GPT-OSS 120B is remote-only and not production-validated in this repository.
- FINORA-MoE and KDQ require governed end-to-end artifact validation before deployment claims.
- Staging load, soak, failover, ingress security, and signed model-risk/compliance approvals are not complete.
- Windows validation uses `pyarrow==16.1.0`; WSL/Linux is recommended if native Windows collection issues recur.

## Roadmap

1. Populate approved provider credentials and pass the live-provider matrix.
2. Expand research validation beyond the single Yahoo/AAPL walkthrough.
3. Add licensed calibration, regime, and bias datasets.
4. Validate governed FINORA-MoE/KD-Q ONNX, TensorRT, and INT8 accuracy deltas.
5. Run hardened staging load, stress, soak, backup/restore, failover, and security tests.
6. Complete model-risk, security, data-owner, compliance, privacy, and engineering approvals.

## Repository Description

Suggested GitHub description:

```text
Auditable financial intelligence research platform with forecasting, RAG, risk, graph reasoning, backtesting, FastAPI, and validation evidence.
```

Suggested topics:

```text
finance, forecasting, rag, risk-management, backtesting, fastapi, pytorch, xgboost, lightgbm, qdrant, neo4j, mlops, model-risk
```
