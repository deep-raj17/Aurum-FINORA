# RTX 4070 real-model benchmark

- GPU: NVIDIA GeForce RTX 4070 SUPER
- VRAM: 11.99 GiB
- Torch: 2.6.0+cu124
- CUDA runtime: 12.4
- Python/platform: 3.11.9 / Windows-10-10.0.26200-SP0
- Timed iterations per workload: 1
- Status: local execution evidence only; not a production performance approval.

| Model | Workload | Load ms | Mean ms | P50 ms | P95 ms | Peak VRAM MiB |
|---|---|---:|---:|---:|---:|---:|
| ProsusAI/finbert | batch=8 text classification | 6522.64 | 9.50 | 9.50 | 9.50 | 429.74 |
| amazon/chronos-t5-tiny | context=160 horizon=5 samples=50 | 1165.50 | 35.68 | 35.68 | 35.68 | 493.74 |

## Interpretation

These measurements prove that the checked model revisions execute on this RTX 4070 workstation. They are short local samples, not SLO, capacity, accuracy, stress, soak, or production approval evidence. GPT OSS 120B was not downloaded or benchmarked.
