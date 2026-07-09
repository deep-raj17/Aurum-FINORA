| Runtime | Precision | Device | Batch | Median ms | P95 ms | Items/s | VRAM | MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| onnxruntime | fp32 | CUDAExecutionProvider | 1 | 1.185 | 1.319 | 843.78 | 0 | n/a |
| onnxruntime | fp32 | CUDAExecutionProvider | 8 | 1.296 | 1.623 | 6174.75 | 0 | n/a |
| onnxruntime | fp32 | CUDAExecutionProvider | 32 | 1.286 | 1.690 | 24888.20 | 0 | n/a |
