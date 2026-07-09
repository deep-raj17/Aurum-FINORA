# MoE router

`MoERouter` learns sparse top-k trust weights over the specialist set. Its input is
the fused multimodal embedding plus this explicit, auditable context:

1. asset class;
2. volatility regime;
3. data availability;
4. market regime;
5. forecast horizon;
6. liquidity condition;
7. sentiment strength;
8. macro shock state.

`RoutingFeatures.vector()` defines the stable eight-value encoding used at the model
boundary. The categorical encoding is intentionally versioned with the model; a
production training pipeline may replace it with learned embeddings while preserving
the external fields.

## Routing behavior

- Unavailable experts receive zero weight before top-k selection.
- At least one expert must be available for every sample.
- Only the configured top-k experts receive non-zero weights.
- A load-balancing loss is returned for the trainer to discourage expert collapse.
- Router weights, top-k identities, context, availability masks, and versions must be
  written to the audit event for each decision.

The default router contains PatchTST, iTransformer, TFT, TiDE, Chronos, LightGBM,
XGBoost, CatBoost, FinBERT, and graph attention. LSTM/GRU/RNN/simple Transformer
baselines are excluded unless an explicitly governed fallback policy selects them.

## Training controls

Train with chronological splits and expert dropout so the router learns degraded-data
behavior. Monitor expert utilization, entropy, turnover, asset/regime concentration,
performance contribution, and routing drift. A good average score cannot hide a
failed regime slice.

Routing is not an approval decision. Compliance gates, data-quality checks, calibration
thresholds, and human review execute after routing and may block the result.
