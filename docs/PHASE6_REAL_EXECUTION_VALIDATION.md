# Phase 6 real execution validation

Validation date: 2026-07-02

Classification: **real-execution validated**

FINORA remains **not staging-ready** and **not production-approved**. Phase 6 proves
that selected real weights, specialist runtimes, CUDA execution, and local graph/vector
services operate on the development workstation. It does not supply licensed
production datasets, full provider coverage, production SLO evidence, independent
compliance review, or model-risk approval.

## Environment

| Component | Validated value |
|---|---|
| Host | Windows development workstation |
| GPU | NVIDIA GeForce RTX 4070 SUPER |
| VRAM | 11.99 GiB |
| Python | 3.11.9 |
| Torch | 2.6.0+cu124 |
| CUDA runtime | 12.4 |
| Model cache | `model_cache/`, 0.847 GiB, excluded from Git |
| GPT OSS 120B | Remote-only; not downloaded |

## Quality gates

| Gate | Result |
|---|---|
| `pytest` | Pass: 131 passed, 23 skipped |
| `ruff check src tests scripts` | Pass |
| `mypy src` | Pass: 74 source files |
| Native import warning | A recoverable Windows `pyarrow` access-violation trace appears during pytest collection; pytest completes successfully |

Phase 7 supersedes the local GitHub release gate results: `pytest -q -ra` now passes
with 131 passed and 26 skipped after adding `onnxscript` for KDQ ONNX export, `ruff`
and `ruff format --check` pass, and mypy passes for 74 source files when run through a
process-based 60 second timeout guard. Runtime API health is also verified.

Mypy initially found the legacy baseline package under both `models` and `src.models`.
The two inconsistent imports were normalized to the existing `models` package. No
public API or model behavior changed.

## Dependency activation

The following runtimes import successfully:

| Runtime | Version/status |
|---|---|
| Torch | 2.6.0+cu124; CUDA available |
| Transformers | 5.12.1 |
| NeuralForecast | 3.1.9 |
| Chronos | 2.3.0 |
| LightGBM | 4.6.0 |
| XGBoost | 3.2.0 |
| CatBoost | 1.2.10 |
| Sentence Transformers | 5.6.0 |
| Qdrant client | 1.18.0 |
| Neo4j driver | 6.2.0 |

## Real model execution

- FinBERT revision `4556d13015211d73dccd3fdd39d39232506f3e43` downloaded,
  loaded on CUDA, and returned a bounded three-class sentiment result.
- Chronos Tiny revision `29d808298f1a62493e7b9a5e08529d0d930fa189`
  downloaded, loaded on CUDA, and returned a finite three-step probabilistic forecast.
- PatchTST, iTransformer, TFT, and TiDE trained for a two-step activation smoke on
  CUDA and returned finite ordered quantile forecasts.
- iTransformer activation identified a required `n_series` runtime argument. The
  existing single-series adapter now supplies `n_series=1`; the model then passed.
- LightGBM, XGBoost, and CatBoost trained through FINORA's direct multi-horizon
  quantile adapter and returned ordered 10/50/90% forecasts.

Activation smokes prove runtime compatibility, not predictive accuracy. The short
seeded series and two training steps are not validation datasets.

## Local services

Docker Engine and Compose were installed inside the existing WSL2 Ubuntu environment
because Docker Desktop was unavailable on Windows. The existing `docker-compose.yml`
was used unchanged to start:

- Qdrant `qdrant/qdrant:v1.14.1` on ports 6333/6334;
- Neo4j `neo4j:5-community` on ports 7474/7687.

HTTP/Bolt connectivity passed. Qdrant completed a temporary vector
create/upsert/query/delete round trip. Neo4j initialized FINORA constraints and
upserted a validation entity through `Neo4jKnowledgeGraph`.

These are development services with development credentials. They are not hardened
staging services.

## Provider validation

`.env` already existed, was not overwritten, and is ignored by `.gitignore`. It was
opened locally for private editing; no values were printed or copied into reports.

No supported provider credential was populated at validation time. In accordance with
the Phase 6 rule, live-provider tests were not run. Historical provider evidence in the
repository is not treated as current Phase 6 evidence.

## RTX 4070 benchmark

The real-weight local benchmark is in
`reports/benchmarks/rtx4070_real_models.md`. FinBERT batch inference and Chronos Tiny
probabilistic inference ran on CUDA within 494 MiB peak allocated VRAM in the measured
process. This is short local latency evidence, not an SLO or capacity approval.

## Remaining staging blockers

1. Populate approved provider credentials and pass the full live-provider matrix.
2. Pin and approve model licenses, revisions, checksums, and weight provenance.
3. Run adequate multi-asset, multi-horizon, and regime-specific walk-forward
   calibration/backtesting on licensed real data.
4. Resolve the native Windows `pyarrow` collection trace.
5. Run sustained load, stress, soak, failover, backup/restore, and security tests in a
   hardened staging environment.
6. Validate ONNX/TensorRT/INT8 accuracy deltas for governed FINORA-MoE/KD-Q artifacts.
7. Obtain signed compliance, privacy, security, and independent model-risk approvals.

## Decision

- Engineering-ready: **yes**
- Real-execution validated: **yes, for the local components evidenced above**
- GitHub portfolio-ready: **yes, after Phase 7 local gates passed**
- Staging-ready: **no**
- Production-approved: **no**

## Phase 7 follow-up

Phase 7 isolates the Windows pyarrow issue with `pyarrow==16.1.0`. If native Windows
collection errors recur, use WSL/Linux as the recommended validation environment.
Phase 7 also verifies that the default API workflow uses the lightweight
`ForecastEngine`; FINORA-MoE remains an implemented optional architecture, not the
default production workflow.
