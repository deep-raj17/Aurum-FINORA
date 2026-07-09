| Runtime | Precision | Device | Batch | Median ms | P95 ms | Items/s | VRAM | MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| torchscript | fp16 | cuda | 1 | 1.992 | 3.019 | 501.97 | 9809920 | 0.0 |
| torchscript | fp16 | cuda | 8 | 2.235 | 4.206 | 3579.26 | 9862144 | n/a |
| torchscript | fp16 | cuda | 32 | 2.211 | 3.478 | 14474.07 | 10044928 | n/a |
