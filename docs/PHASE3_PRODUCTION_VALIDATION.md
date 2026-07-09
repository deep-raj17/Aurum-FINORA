# Phase 3 production-readiness validation

## Current classification

**Engineering-ready; not staging-ready or production-approved.**

Code and local infrastructure may be validated without external credentials. The
following release gates are intentionally fail-closed:

| Gate | Local state | Pass evidence required |
|---|---|---|
| Unit/static/coverage | Available | CI artifacts and coverage threshold |
| Live providers | Blocked | Credentialed `pytest -m live` report for every provider |
| Real model weights | Blocked | `pytest -m model` on approved weights/endpoints |
| GPU/quantization | Blocked | Smoke runners pass; governed production-weight target-hardware and accuracy-delta reports are required |
| Calibration/backtesting | Blocked | Versioned calibration datasets and all regime reports |
| Bias | Blocked | Adequately sized approved slices within thresholds |
| Load/reliability | Blocked | Staging SLO, stress, recovery and DR evidence |
| Security | Partially available | Clean dependency, secret, JWT/RBAC, abuse and image scans |
| Model risk | Blocked | Signed model-risk and data-owner approvals |
| Compliance | Blocked | Signed compliance and security approvals |

## Provider and model validation

```bash
FINORA_RUN_LIVE_TESTS=1 pytest -m live tests/integration/test_live_providers.py
FINORA_RUN_MODEL_TESTS=1 pytest -m model tests/integration/test_real_models.py
```

Tests skip without the explicit network/model gate. Credentialed tests additionally
skip only the provider whose credential/configuration is absent. In staging, any skip
is a failed release gate even though it is safe behavior in ordinary CI.

## Calibration and backtesting

`production_validation.py` supports expanding and rolling walk-forward origins,
bull/bear/sideways/high-volatility/crisis classification, conformal intervals,
directional accuracy, coverage ECE, and cost-adjusted strategy metrics. Calibration
records are timestamped, versioned, and content hashed.

Required evidence must cover every supported asset class and material market regime.
No random train/test split is acceptable for time series.

## Benchmark runner validation

The explicitly marked smoke artifact has completed TorchScript FP32/FP16/BF16 CUDA,
TorchScript INT8 CPU, and ONNX Runtime CUDA runs on a GeForce RTX 4070 SUPER. Results
are recorded in `docs/benchmarks/`. This validates the runners and portable execution
paths, not the final model: the production gate remains blocked until approved weights,
calibration data, accuracy tolerances, target runtime, and GPT-OSS quantized endpoint
results are available.

## Security

The security job runs dependency, secret, and container scans. Tests cover prompt
injection, evidence poisoning, JWT/RBAC, rate abuse and authenticated encryption.
Staging must additionally run authenticated ingress tests and network-policy tests.

## Reliability and disaster recovery

Locust exercises health and forecast endpoints. Circuit breakers make optional vector
and graph dependencies explicitly degraded; required analytical/storage failures remain
errors. Snapshot drills use SQLite online backup, file hashes, integrity verification,
and non-destructive restore destinations.

Required staging evidence:

- sustained load at the approved concurrency and latency SLO;
- burst/stress behavior with 429 rather than process exhaustion;
- concurrent CPU/GPU inference;
- Qdrant, Neo4j and connector outage/recovery;
- database write failure and restore;
- recovery point objective and recovery time objective measurements.

## Approval rule

`ProductionApprovalPacket.status()` cannot pass unless every automated gate passes and
model-risk, compliance, security, and data-owner reviewers approve the same
reproducibility hash. Checked-in documentation is never itself an approval.
