| Runtime | Precision | Device | Batch | Median ms | P95 ms | Items/s | VRAM | MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| torchscript | int8 | cpu | 1 | 0.913 | 1.005 | 1095.53 | 0 | 0.0 |
| torchscript | int8 | cpu | 8 | 1.518 | 1.750 | 5270.96 | 0 | n/a |
| torchscript | int8 | cpu | 32 | 1.890 | 2.017 | 16926.74 | 0 | n/a |
