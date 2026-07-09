# Baseline models

The following are baseline-only in FINORA-MoE:

| Model | Permitted use |
|---|---|
| LSTM | Historical benchmark, ablation, emergency governed fallback |
| GRU | Historical benchmark, ablation, emergency governed fallback |
| Vanilla RNN | Sanity check and complexity baseline |
| Simple Transformer | Capacity/latency benchmark |

They are not primary experts and are absent from the default MoE router. Existing
training scripts and artifacts are retained for reproducibility and API compatibility.
No file is removed merely because its model has been downgraded.

Random walk, drift, historical mean, AR(1), Holt, robust drift, and ridge
autoregression remain essential statistical baselines. N-HiTS remains a compatible
optional adapter but is not part of the default FINORA-MoE hierarchy.

A specialist is promoted only if it beats relevant baselines out of sample after
costs, remains calibrated, and passes regime, risk, compliance, and model-risk gates.
Baseline underperformance is evidence against deployment, not a reason to hide or
remove the baseline.
