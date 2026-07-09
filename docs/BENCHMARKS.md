# FINORA production benchmarks

Status: **BLOCKED — governed production-weight and target-runtime reports are required**

```bash
python scripts/benchmark_phase3.py artifacts/finora-kdq --device cuda --precision fp16
python scripts/benchmark_phase3.py artifacts/finora-kdq --device cuda --precision bf16
python scripts/benchmark_phase3.py artifacts/finora-kdq --device cpu --precision int8
python scripts/benchmark_onnx_phase3.py artifacts/finora-kdq
python scripts/benchmark_gpt_oss_phase3.py --quantization mxfp4
```

Reports include median/P95 latency, items/second, batch size, peak VRAM when available,
and numerical error relative to a governed reference. Production approval requires
repeatable results on the target GPU/driver/runtime, warm and cold starts, batch sizes
1/8/32, and accuracy tolerances approved by model risk.

## Local GPU smoke benchmark — not production evidence

On 2026-07-01, the explicitly marked `FINORA-KD-Q-SMOKE` artifact ran on an NVIDIA
GeForce RTX 4070 SUPER. The table reports batch-1 results; batch 8/32 evidence is in
the linked JSON/Markdown report directories.

| Runtime | Precision | Device | Median ms | P95 ms | Items/s |
|---|---:|---|---:|---:|---:|
| TorchScript | FP32 | CUDA | 1.283 | 1.476 | 779 |
| TorchScript | FP16 | CUDA | 1.931 | 2.889 | 518 |
| TorchScript | BF16 | CUDA | 1.941 | 2.551 | 515 |
| TorchScript | INT8 | CPU | 0.913 | 1.005 | 1,096 |
| ONNX Runtime | FP32 | CUDA | 1.185 | 1.319 | 844 |

Evidence: `docs/benchmarks/smoke-fp32`, `smoke-fp16`, `smoke-bf16`, `smoke-int8`,
and `smoke-onnx`. These measurements validate the runners and deployment formats only.
They do not validate production accuracy, a real teacher-distilled checkpoint,
TensorRT INT8, or the quantized GPT-OSS endpoint.

## Local API smoke load — not a staging benchmark

On 2026-07-01, a 10-second, five-user Locust run against the local Docker API completed
61 requests with zero failures. The 23 forecast requests averaged 80 ms with an
approximate P95 of 140 ms. Health and forecast CSV evidence is stored alongside this
document as `load-local_*`. This short local result does not satisfy sustained load,
stress, soak, multi-replica, GPU, or staging SLO gates.
