# Phase 7 GitHub release readiness

Validation date: 2026-07-09

## Classification

| Area | Decision |
|---|---|
| Research engineering platform | yes |
| GitHub portfolio-ready | yes, because all local Phase 7 gates passed |
| Staging-ready | no |
| Production-approved | no |

## Fixed issues

- Added `onnxscript` to the `kdq` and `dev` extras so KDQ ONNX export works with the
  installed PyTorch ONNX exporter.
- Reinstalled the editable package with `pip install -e ".[dev,kdq,data]"`.
- Applied Ruff formatting to five previously unformatted files.
- Isolated the Windows pyarrow issue with `pyarrow==16.1.0` in the data/dev extras.
- Verified runtime API health with the documented Uvicorn command.
- Reinitialized the unusable empty Git repository during Phase 7.
- Tightened `.gitignore` for secrets, model cache, local outputs, logs, checkpoints,
  local databases, and private report artifacts.

## Commands run

```powershell
pip install -e ".[dev,kdq]"
pip install "pyarrow==16.1.0"
pip install -e ".[dev,kdq,data]"
ruff format src\aurum\llm.py src\aurum\moe.py src\evaluation\evaluate_model.py src\training\train_lstm_transformer_weighted.py tests\test_llm.py
ruff check src tests scripts
ruff format --check src tests scripts
pytest -q -ra
$p = Start-Process -FilePath mypy -ArgumentList 'src' -PassThru -NoNewWindow
if (-not $p.WaitForExit(60000)) { $p.Kill(); throw 'mypy timed out after 60 seconds' }
if ($p.ExitCode -ne 0) { throw "mypy failed with exit code $($p.ExitCode)" }
python -m uvicorn aurum.api.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

## Test, lint, and type results

| Gate | Result |
|---|---|
| `ruff check src tests scripts` | pass |
| `ruff format --check src tests scripts` | pass |
| `pytest -q -ra` | pass: 131 passed, 26 skipped |
| timeout-safe mypy | pass: `Success: no issues found in 74 source files` |

The 26 skipped tests are credential/model-gated integration tests:

- 15 live-provider tests require `FINORA_RUN_LIVE_TESTS=1` and approved provider credentials.
- 11 real-model tests require `FINORA_RUN_MODEL_TESTS=1` and approved model/runtime configuration.

## API health result

Runtime command:

```powershell
python -m uvicorn aurum.api.main:app --host 127.0.0.1 --port 8000
```

Health check result:

```text
status=ok
mode=decision-support
audit_chain_valid=True
```

## Git status

The pre-existing `.git` directory was empty and unusable. Phase 7 reinitialized Git
only after local tests passed. Initial release commit message: `Prepare Phase 7 GitHub
release`. Final Git status after the commit was clean. The commit includes source,
tests, docs, configuration, and public evidence artifacts while excluding `.env`,
secrets, `model_cache`, checkpoints, local databases, logs, outputs, local KDQ
artifacts, and private report material.

## Research honesty note

The Yahoo/AAPL/XGBoost expanding-window run proves that the research validation
pipeline executes on real market data. It does not prove market alpha:

- Directional accuracy: 0.4286
- Interval coverage: 0.4286
- Net Sharpe: -4.0898
- Bootstrap p-value: 0.868

## Unresolved blockers

1. Full live-provider matrix remains blocked by missing approved credentials.
2. Licensed multi-asset, multi-horizon, regime-specific datasets are not validated.
3. Production model licenses, checksums, revisions, and weight provenance are not
   approved.
4. FINORA-MoE and KDQ artifacts still need governed ONNX/TensorRT/INT8 accuracy delta
   validation.
5. Hardened staging load, stress, soak, failover, backup/restore, and ingress security
   evidence is not present.
6. Compliance, privacy, security, engineering, data-owner, and independent model-risk
   approvals are not signed.

## Release recommendation

Release to GitHub as a portfolio-ready research engineering platform. Do not describe
the repository as staging-ready, production-approved, investment advice, or a proven
alpha-generating trading system.
