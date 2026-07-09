# RTX 4070 research benchmarking

The local RTX 4070-class GPU is a development device, not a GPT-OSS 120B server.

```powershell
python scripts/benchmark_phase3.py artifacts/finora-kdq-smoke `
  --model artifacts/finora-kdq-smoke/finora-kdq-fp32.pt `
  --output reports/benchmarks/rtx4070 --device cuda --precision fp16
python scripts/benchmark_onnx_phase3.py artifacts/finora-kdq-smoke `
  --output reports/benchmarks/rtx4070-onnx
```

Reports capture model load time, median/P95 latency, throughput, batch size, precision,
peak allocated VRAM, hardware name, and total VRAM. Run FP32, FP16, BF16, CPU INT8,
ONNX CUDA and, when installed, TensorRT INT8. Reset peak CUDA memory before governed
runs and record driver, CUDA, runtime, model hash and dataset hash.

Smoke results validate runners only. Production evidence requires approved weights,
accuracy deltas, warm/cold tests, repeated runs, and target deployment hardware.

The 2026-07-01 FP16 smoke run is stored in `reports/benchmarks/rtx4070/`. Batch-one
median/P95 latency was 1.992/3.019 ms, throughput was 502 items/s, and model load time
was 119.418 ms. Batch 8 and 32 reports are included in the same governed JSON evidence.
