# Public release checklist

Checklist date: 2026-07-09

## Required release checks

| Check | Status | Evidence / command |
|---|---|---|
| No tracked `.env` files | pass | `git ls-files` does not include `.env`, `.env.txt`, `.env.local`, `.env.production`, or `.env.staging` |
| No secrets or API keys committed | pass | Secret-pattern scan completed; only placeholders/docs/templates allowed |
| No model weights committed | pass | `*.pt`, `*.onnx`, `*.ckpt`, `*.safetensors`, `*.bin`, `*.gguf`, `model_cache/` ignored |
| No large generated datasets | pass | `data/processed/`, parquet files, outputs, checkpoints, artifacts, and local KDQ data ignored |
| No private reports | pass | `reports/private/`, private/secrets/credentials report patterns ignored |
| No cache files | pass | `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `data/cache/`, `__pycache__/` ignored |
| No local absolute paths exposing private machine details | pass with note | Release docs use repo-relative paths; historical validation evidence may mention generic Windows/WSL environment context |

## Ignore rules confirmed

Important local/private paths are ignored:

```text
.env
.env.*
.env.txt
secrets/
credentials/
tokens/
model_cache/
artifacts/
outputs/
logs/
lightning_logs/
data/cache/
data/processed/*
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

## Manual review notes

- `.env.example` is intentionally public and contains placeholders only.
- Small CSV evidence fixtures and public research artifacts are committed for
  reproducibility.
- Live-provider credentials must be supplied only through local `.env`, secret files,
  CI secrets, or a private deployment secret manager.
- Do not upload local model caches, downloaded weights, generated KDQ artifacts,
  private reports, or production datasets to the public repository.

## Final release decision

Public GitHub release is approved as a portfolio-ready research engineering platform.
It remains not staging-ready and not production-approved.
