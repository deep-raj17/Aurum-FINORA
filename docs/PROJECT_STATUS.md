# FINORA project status

Status date: 2026-07-09

## Classification

| Area | Status |
|---|---|
| Research engineering platform | yes |
| Research-validated | yes |
| Real-execution validated | yes |
| GitHub portfolio-ready | yes, after Phase 7 local gates passed |
| Staging-ready | no |
| Production-approved | no |

FINORA is suitable for a GitHub portfolio release as a transparent research
engineering platform. It is not approved for autonomous trading, client-facing advice,
staging deployment, or production use.

## Phase 7 gate results

| Gate | Result |
|---|---|
| `pip install -e ".[dev,kdq,data]"` | pass |
| `ruff check src tests scripts` | pass |
| `ruff format --check src tests scripts` | pass |
| `pytest -q -ra` | pass: 131 passed, 26 skipped |
| `mypy src` | pass: 74 source files through process-based 60 second timeout guard |
| API health | pass: `GET /health` returned `status=ok`, `mode=decision-support`, `audit_chain_valid=True` |

Use this timeout-safe mypy command on Windows:

```powershell
$p = Start-Process -FilePath mypy -ArgumentList 'src' -PassThru -NoNewWindow
if (-not $p.WaitForExit(60000)) { $p.Kill(); throw 'mypy timed out after 60 seconds' }
if ($p.ExitCode -ne 0) { throw "mypy failed with exit code $($p.ExitCode)" }
```

## Default execution path

The default API workflow routes `POST /v1/forecast` through `FinoraService`,
`FinoraPipeline`, and the lightweight deterministic `ForecastEngine`. This path is
appropriate for local decision-support reports and release smoke validation.

FINORA-MoE is implemented as a governed architecture with fusion, routing, prediction
heads, specialist adapters, RAG, and GPT-OSS boundaries. It is not the default
end-to-end production workflow unless the operator explicitly wires specialist
embeddings, approved model weights, service endpoints, datasets, and validation gates
into a run.

## Research honesty note

The Yahoo/AAPL/XGBoost expanding-window run proves that the research pipeline executes
on real market data. It does not prove market alpha:

- Directional accuracy: 0.4286
- Interval coverage: 0.4286
- Net Sharpe: -4.0898
- Bootstrap p-value: 0.868

## Remaining blockers

1. Approved provider credentials and full live-provider matrix.
2. Licensed multi-asset, multi-horizon, regime-specific calibration/backtesting data.
3. Approved model licenses, revisions, checksums, and weight provenance.
4. Hardened staging deployment with sustained load, stress, soak, failover, backup,
   restore, and authenticated ingress tests.
5. Governed FINORA-MoE/KD-Q ONNX/TensorRT/INT8 accuracy delta validation.
6. Signed compliance, privacy, security, data-owner, engineering, and independent
   model-risk approvals.
