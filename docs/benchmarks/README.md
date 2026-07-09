# FINORA benchmark reports

No production GPU benchmark is claimed in source control. Run:

```bash
python scripts/benchmark_phase3.py artifacts/finora-kdq \
  --device cuda --precision fp16 --batch-sizes 1,8,32
```

The runner writes machine-readable `latest.json` and a Markdown table to this
directory. A release gate remains blocked until the target GPU has reports for FP16,
BF16, INT8, ONNX Runtime/TensorRT, batch throughput, peak VRAM, and the self-hosted
GPT-OSS endpoint, with accuracy deltas compared to the governed FP32 artifact.
