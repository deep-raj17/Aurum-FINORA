# Distilling FINORA-MoE into FINORA-KD-Q

FINORA-KD-Q remains the compact multimodal student and quantized deployment path.
`FINORAMoETeacher` adapts a governed MoE predictor to the existing soft-label contract:
forecast mean, ordered quantiles, and volatility. Existing teacher slots continue to
provide FinBERT sentiment, trained risk targets, grounded reasoning embeddings, and
retrieval embeddings.

```text
FINORA-MoE forecast/risk ensemble ─┐
FinBERT teacher ───────────────────┤
Grounded RAG/report teacher ───────┼→ chronological KD dataset
Retrieved evidence embeddings ────┘        ↓
                                  FINORA-KD-Q + QAT
                                  ↓
                         FP32 / INT8 / ONNX / TensorRT
```

GPT-OSS is permitted only in the grounded reasoning/RAG/report-teacher branch. It must
not generate raw forecast targets.

GPT OSS 120B teaches four distinct language tasks: compact report generation,
financial reasoning, audit summarization, and scenario analysis. Training examples
must be produced from governed evidence packs and retain citations, pack hashes,
teacher version, task, cutoff, and review outcome.

The target language student is an 8B–14B model fine-tuned with QLoRA. Candidate
artifacts may use 4-bit weight-only or INT8 deployment so local inference is possible
on smaller hardware. Quantization does not relax grounding, calibration, leakage,
security, or human-review tests. The existing multimodal FINORA-KD-Q student remains
the compact numerical/sentiment/risk path; the language student is a separate
grounded-report component.

## Training and release rules

- Build labels at chronological cutoffs and persist teacher/expert/weight versions.
- Split chronologically; never shuffle future observations into training.
- Train on forecast, quantile, uncertainty, volatility, sentiment, risk, calibration,
  and explanation objectives already implemented by KD-Q.
- Compare the student with both its MoE teacher and simple baselines by asset, horizon,
  regime, and data-availability pattern.
- Re-run conformal calibration after quantization/export.
- Benchmark FP32, INT8, ONNX, and TensorRT separately on target hardware.
- Preserve existing artifact hashes, model cards, human-validation status, audit
  events, and rollback paths.

The current KD-Q public request/response contracts are unchanged. Additional MoE
routing diagnostics may be stored as training provenance in a future schema version;
they must not be added as a breaking required field.

An offline/synthetic teacher can exercise the pipeline but cannot support live capital,
staging promotion, or production approval.
