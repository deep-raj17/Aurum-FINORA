| Runtime | Precision | Device | Batch | Median ms | P95 ms | Items/s | VRAM | MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| torchscript | bf16 | cuda | 1 | 1.941 | 2.550 | 515.33 | 9809920 | 0.0 |
| torchscript | bf16 | cuda | 8 | 2.284 | 4.112 | 3502.63 | 9862144 | n/a |
| torchscript | bf16 | cuda | 32 | 4.475 | 5.551 | 7151.32 | 10044928 | n/a |
