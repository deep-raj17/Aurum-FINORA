| Runtime | Precision | Device | Batch | Median ms | P95 ms | Items/s | VRAM | MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| torchscript | fp32 | cuda | 1 | 1.283 | 1.476 | 779.18 | 9806848 | 1.1920928955078125e-07 |
| torchscript | fp32 | cuda | 8 | 1.423 | 2.938 | 5622.12 | 9894400 | n/a |
| torchscript | fp32 | cuda | 32 | 1.322 | 1.531 | 24213.99 | 10196992 | n/a |
