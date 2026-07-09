# FINORA-KD-Q

Production teacher construction is fail-closed: forecast, FinBERT, trained risk, and
GPT-OSS feature teachers must be supplied explicitly. The statistical/lexical/hash
teachers exist only for CI smoke artifacts and require `--allow-offline-baselines`.
Such artifacts remain marked `REQUIRES_HUMAN_VALIDATION`.

**Financial Intelligence Distilled Quantized Model**

FINORA-KD-Q is a compact multi-teacher student. It does not collapse every financial
capability into one opaque teacher. Each teacher remains independently replaceable,
versioned, evaluated, and auditable.

## Architecture

```text
Chronos + PatchTST + TFT ─┐
FinBERT ──────────────────┤
LightGBM + XGBoost ───────┼─ versioned soft labels ─┐
Finance Qwen/Llama ───────┤                         │
BGE-M3 + reranker ────────┘                         ▼
                                      ┌─────────────────────────┐
market windows ─ PatchTST-lite ──────►│ cross-modal transformer │
text/evidence ─ compact text encoder ─►│ fusion + modality gates │
factors ─────── MLP/BN/dropout ──────►│                         │
                                      └────────────┬────────────┘
                                                   │
                     ┌────────────┬────────────┬────┴─────┬─────────────┐
                     ▼            ▼            ▼          ▼             ▼
                  forecast     quantiles    sentiment    risk      reasoning
                  + vol        p10/50/90    3 classes  VaR/DD/crash embedding
```

## Three-stage workflow

### 1. Run teachers independently

Production teacher adapters should wrap pinned inference functions using
`CallableTeacher`. Each output records the exact teacher version. The offline
surrogates are deterministic and intended for CI, schema validation, and pipeline
testing—not live investment use.

### 2. Generate immutable soft-label datasets

```bash
aurum kdq-generate --settings config/kdq.yaml \
  --output data/kdq/training.jsonl --count 10000
```

Every row carries the timestamp, teacher probabilities, quantiles, risk targets,
reasoning embedding, teacher versions, and evidence identifiers. JSONL output is
chronologically sorted and SHA-256 hashed.

### 3. Train with KD and QAT

```bash
aurum kdq-train data/kdq/training.jsonl --settings config/kdq.yaml
aurum kdq-export artifacts/finora-kdq --format int8
python scripts/deploy_kdq_artifact.py artifacts/finora-kdq
docker compose --profile kdq up -d finora-kdq
```

The objective is:

```text
1.0 × supervised forecast MSE
+ 0.7 × teacher forecast MSE
+ 0.3 × teacher quantile MSE
+ 0.5 × temperature-scaled sentiment KL
+ 0.5 × risk-target MSE
+ 0.3 × quantile pinball loss
+ 0.2 × volatility MSE
+ 0.2 × interval calibration loss
+ 0.1 × reasoning-embedding cosine loss
```

Weights are explicit in `config/kdq.yaml`. Data splits are chronological. Training
uses AdamW, gradient clipping, optional CUDA mixed precision, early stopping, and
activation fake quantization with moving-average INT8 observers.

## Artifacts

Each training run writes:

- `student-state.pt` — QAT-trained weights;
- `manifest.json` — configurations, teachers, dataset/checkpoint hashes, metrics;
- `MODEL_CARD.md` — intended use, limitations, and required review;
- `finora-kdq.pt` — optional hybrid INT8 TorchScript deployment artifact;
- `finora-kdq.onnx` — optional ONNX graph for ONNX Runtime/TensorRT quantization.

The local INT8 exporter quantizes MLP and output linear layers while retaining
transformer attention in floating point for PyTorch compatibility. Full static INT8
transformer conversion should be performed from ONNX using representative calibration
data on the target ONNX Runtime or TensorRT version.

Docker uses a named artifact volume rather than a host bind mount. This works when the
workspace is on a Windows drive that is not shared into Docker Desktop's WSL VM. The
deployment script verifies the artifact layout and copies it through Docker's API.

## Production teacher mapping

| Capability | Production teacher | Offline pipeline teacher |
|---|---|---|
| Forecast | Chronos, PatchTST, TFT ensemble | statistical ensemble surrogate |
| Sentiment | FinBERT | auditable finance lexicon |
| Risk | LightGBM and XGBoost | historical risk surrogate |
| Reasoning/report | finance-tuned Qwen or Llama | grounded hashed embedding |
| Retrieval | BGE-M3 plus cross-encoder | hybrid lexical/hashed-dense retriever |

Teacher adapters must enforce the forecast cutoff before inference. Reasoning traces
should not be stored; distil outputs, grounded summaries, or embeddings instead.

## Validation gates

An artifact remains `REQUIRES_HUMAN_VALIDATION` until it passes:

1. Purged walk-forward evaluation against random walk and specialist teachers.
2. Regime tables for bull, bear, sideways, high-volatility, and crisis windows.
3. Interval coverage, ECE, Brier score, and reliability plots.
4. VaR exception tests and stress-loss review.
5. Net-of-cost backtests with PBO/multiple-testing controls.
6. Teacher/student disagreement and out-of-distribution thresholds.
7. INT8 accuracy delta and latency/throughput benchmarks on target hardware.
8. Evidence faithfulness, language/market bias, and compliance review.

No generated artifact is automatically approved for trading.
