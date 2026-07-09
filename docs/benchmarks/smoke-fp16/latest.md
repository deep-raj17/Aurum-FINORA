| Runtime | Precision | Device | Batch | Median ms | P95 ms | Items/s | VRAM | MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| torchscript | fp16 | cuda | 1 | 1.931 | 2.889 | 517.87 | 9809920 | 0.0 |
| torchscript | fp16 | cuda | 8 | 2.640 | 4.867 | 3030.36 | 9862144 | n/a |
| torchscript | fp16 | cuda | 32 | 2.867 | 4.937 | 11160.52 | 10044928 | n/a |
