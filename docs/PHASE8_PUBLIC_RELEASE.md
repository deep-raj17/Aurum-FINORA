# Phase 8 public GitHub release

Validation date: 2026-07-09

## Final classification

| Area | Status |
|---|---|
| GitHub portfolio-ready | yes |
| Research engineering platform | yes |
| Staging-ready | no |
| Production-approved | no |

FINORA is ready to publish as a public GitHub portfolio project. It must not be
described as investment advice, a production trading system, a staging-approved
service, or a proven alpha-generating strategy.

## Git commit hash

Phase 8 started from commit `b81dea1` (`Prepare Phase 7 GitHub release`). The Phase 8
public-release commit should be created after this report is staged; verify the final
public commit with:

```bash
git rev-parse --short HEAD
```

## Final test status

| Command | Result |
|---|---|
| `ruff check src tests scripts` | pass |
| `ruff format --check src tests scripts` | pass: 109 files already formatted |
| `pytest -q -ra` | pass: 131 passed, 26 skipped |
| timeout-safe `mypy src` | pass: `Success: no issues found in 74 source files` |
| `powershell -ExecutionPolicy Bypass -File scripts\demo_portfolio_run.ps1` | pass |
| `bash scripts/demo_portfolio_run.sh` | not executed in this Windows sandbox; host returned `Bash/Service/CreateInstance/E_ACCESSDENIED` |

The 26 skipped pytest tests are expected release-gated tests:

- 15 live-provider tests require `FINORA_RUN_LIVE_TESTS=1` and approved provider credentials.
- 11 real-model tests require `FINORA_RUN_MODEL_TESTS=1` and approved model/runtime configuration.

## Ignored files confirmed

Tracked forbidden-artifact scan returned no matches for:

```text
.env
.env.txt
.env.local
.env.production
.env.staging
model_cache/
artifacts/
outputs/
logs/
lightning_logs/
data/cache/
data/processed/
data/kdq/
*.parquet
*.sqlite3
*.db
*.pt
*.onnx
*.ckpt
*.safetensors
*.bin
*.gguf
.coverage
```

High-confidence secret scan returned no matches for common OpenAI, GitHub, AWS,
Google, Slack, or private-key patterns. Local private machine path scan returned no
matches in the public release docs, scripts, templates, configuration, source, and
tests after sanitizing the old security report artifact.

## Public release blockers

No blockers remain for a GitHub portfolio release.

The following are still blockers for staging or production:

1. Approved provider credentials and full live-provider validation.
2. Licensed multi-asset, multi-horizon, regime-specific calibration and bias datasets.
3. Approved model licenses, revisions, checksums, and weight provenance.
4. Governed FINORA-MoE/KD-Q ONNX, TensorRT, and INT8 accuracy-delta validation.
5. Hardened staging load, stress, soak, failover, backup/restore, and ingress security evidence.
6. Signed model-risk, security, data-owner, compliance, privacy, and engineering approvals.

## GitHub push instructions

```bash
git status --short
git add README.md docs .github scripts
git commit -m "Prepare Phase 8 public release"
git remote add origin https://github.com/<owner>/<repo>.git
git branch -M main
git push -u origin main
```

Before pushing, confirm that `git status --ignored --short` shows local private
artifacts as ignored, especially `.env`, `model_cache/`, `artifacts/`, `outputs/`,
`data/cache/`, and `data/processed/`.

## Recommended repository description

```text
Auditable financial intelligence research platform with forecasting, RAG, risk, graph reasoning, backtesting, FastAPI, and validation evidence.
```

## Recommended project tags

```text
finance
forecasting
rag
risk-management
backtesting
fastapi
pytorch
xgboost
lightgbm
qdrant
neo4j
mlops
model-risk
financial-ai
research-platform
```

## Release recommendation

Publish the repository as a portfolio-ready research engineering platform. Keep the
README disclaimer and limitation language visible. Do not add production badges,
performance claims, or trading claims until the staging and production blockers are
closed with independent evidence.
