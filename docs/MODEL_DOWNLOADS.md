# Model downloads and cache policy

Weights are never committed. Set `FINORA_MODEL_CACHE_DIR=model_cache`; `.gitignore`
excludes that directory and common model formats.

## Workstation-safe models

```powershell
pip install -e ".[deep,nlp,stats]"
$env:FINORA_CHRONOS_MODEL_ID="amazon/chronos-t5-tiny"
$env:FINORA_FINBERT_MODEL_ID="ProsusAI/finbert"
$env:FINORA_RUN_MODEL_TESTS="1"
pytest -m model tests/integration/test_real_models.py -ra
```

Chronos and FinBERT load lazily and use the configured cache. FinBERT supports batch
inference and automatic CUDA/CPU selection. XGBoost and LightGBM train only when their
adapter or training script is invoked; `scripts/train_tabular_model.py` performs an
80/20 chronological split, GPU-with-CPU-fallback training, native model persistence,
dataset hashing, metrics, and feature-importance export.

Do not load GPT-OSS 120B or 20B locally on a 12GB workstation. Configure a vLLM/SGLang
OpenAI-compatible endpoint with `FINORA_LLM_PROVIDER=remote`, or use a reviewed
4/8-bit small local instruct model such as a 3B-class model. Local oversized GPT-OSS
IDs are rejected by code.

Model license, checksum, source, revision, data restrictions, and approval status must
be recorded before a weight becomes a governed production artifact.
