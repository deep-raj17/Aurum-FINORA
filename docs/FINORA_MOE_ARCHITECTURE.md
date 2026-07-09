# FINORA-MoE architecture

FINORA-MoE is the model architecture for FINORA's audited financial
decision-support workflow. It is an engineering implementation, not a production
approval or an autonomous trading system.

```text
Data Lake → Feature Store → Specialist Experts → Cross-Attention Fusion
          → MoE Router → Prediction Heads → Calibration → Backtesting
          → Audit Ledger → API/UI
```

## Component boundaries

1. The data lake preserves immutable source payloads, timestamps, hashes, and lineage.
2. The feature store produces point-in-time-correct OHLCV, technical, macro,
   sentiment, filing/news, graph, risk, and regime features.
3. Specialist adapters run real model code or fail explicitly. Missing models are
   marked unavailable; no statistical surrogate silently impersonates an expert.
4. Cross-attention maps the eight modalities into a shared decision embedding.
5. The sparse MoE router combines available specialist embeddings using audited
   context. Baselines do not enter the default router.
6. Heads emit return, direction, volatility, risk, VaR/CVaR, drawdown, regime,
   scenario, and explanation/evidence outputs.
7. Conformal calibration and chronological backtesting execute before release gates.
8. Existing governance, security, model-risk, audit-ledger, API, UI, observability,
   Docker, Kubernetes, Helm, and Terraform layers remain unchanged.

`src/aurum/moe.py` contains the expert registry, graph-attention encoder,
cross-attention fusion, contextual sparse router, and prediction heads.
`src/aurum/forecast_system.py` remains the runtime boundary for forecasting
specialists and now includes iTransformer, TiDE, and CatBoost.

## Prediction contract

The MoE core returns the following tensors together with routing diagnostics:

| Output | Constraint |
|---|---|
| Return forecast | One value per configured horizon |
| Direction logits | Down/flat/up logits per horizon |
| Volatility and risk | Non-negative |
| VaR/CVaR | Non-negative; CVaR is constrained to be at least VaR |
| Drawdown probability | In `[0,1]` |
| Regime/scenario logits | Calibrated downstream before use as probabilities |
| Explanation embedding | Passed to grounded report generation |
| Evidence logits | Rank only evidence admitted by the retrieval/audit cutoff |
| Expert/modality weights | Persisted for monitoring and audit |

## Failure and governance rules

- A sample with no available modality or no available expert fails closed.
- Router weights do not waive data quality, compliance, or human-review gates.
- GPT-OSS may consume approved evidence for reasoning/RAG/report teaching. It cannot
  supply a raw forecasting expert output.
- Development or synthetic data cannot satisfy release validation.
- Real data, governed weights, target-hardware benchmarks, security/compliance
  review, and independent model-risk approval are still required.

## Compatibility

Existing forecast, report, risk, scenario, RAG, graph, audit, KD-Q, and API contracts
remain valid. FINORA-MoE is additive: callers may adopt its internals without changing
the current public API payloads. Model/version metadata should record whether the
legacy selector or FINORA-MoE produced a forecast.
