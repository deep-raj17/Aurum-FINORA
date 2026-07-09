# FINORA portfolio presentation

## Project summary

FINORA is a research-focused financial intelligence platform that combines forecasting, evidence retrieval, graph reasoning, scenario analysis, and cost-aware backtesting. The project is intentionally structured as a validated research prototype rather than a production trading system.

## Architecture diagram text

```text
Market data and filings
  -> normalization and quality checks
  -> specialist experts (forecasting, text, graph, tabular)
  -> FINORA-MoE fusion and router
  -> calibration, risk, scenario, and backtesting layers
  -> evidence retrieval and graph persistence
  -> API, audit ledger, and research reports
```

## Model stack

- Forecasting specialists: PatchTST, iTransformer, TFT, TiDE, Chronos
- Tabular experts: LightGBM, XGBoost, CatBoost
- Text expert: FinBERT
- Graph expert: Graph Attention
- Reasoning layer: GPT OSS 120B via remote endpoint only

## Validation evidence

- Research validation report: [../FINORA_RESEARCH_VALIDATION_REPORT.md](../FINORA_RESEARCH_VALIDATION_REPORT.md)
- Provider status: [../reports/providers/provider_status.md](../reports/providers/provider_status.md)
- Research dataset summary: [../reports/research/research_dataset_v1.md](../reports/research/research_dataset_v1.md)
- RTX 4070 benchmark: [../reports/benchmarks/rtx4070_real_models.md](../reports/benchmarks/rtx4070_real_models.md)
- Research artifact: [../reports/research/yahoo-aapl-xgboost-expanding.json](../reports/research/yahoo-aapl-xgboost-expanding.json)

## Limitations

- Live provider tests are blocked by missing credentials.
- The Windows environment still shows a pyarrow-related collection crash during pytest startup.
- API health was not reachable in the current verification pass.
- The current evidence is research-grade, not production-approved.

## Interview talking points

- FINORA preserves the existing architecture and focuses on validation and reproducibility.
- The platform combines deterministic research outputs with local GPU-backed model execution.
- Evidence and audit layers are designed to support human review and future compliance workflows.
- The project is intentionally transparent about what is validated and what remains blocked.

## Future roadmap

- Add approved provider credentials and rerun the live-provider matrix.
- Expand beyond the current single-symbol Yahoo Finance walkthrough.
- Add broader backtesting and regime coverage.
- Resolve the pyarrow and API health blockers before broader deployment work.
