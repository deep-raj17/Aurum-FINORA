# FINORA research validation report

Validation date: 2026-07-02

## Architecture status

- Architecture remained unchanged. The FINORA-MoE stack was used as-is.
- The validation effort focused on evidence, reproducibility, and research readiness rather than redesign.

## Dataset status

- A real Yahoo Finance walk-forward research validation was executed for AAPL.
- The resulting research artifact is stored in [reports/research/yahoo-aapl-xgboost-expanding.json](reports/research/yahoo-aapl-xgboost-expanding.json).
- A summary dataset note is available in [reports/research/research_dataset_v1.md](reports/research/research_dataset_v1.md).
- Provider-backed datasets beyond Yahoo Finance remain blocked until approved credentials are available.

## Model status

- FinBERT and Chronos were executed locally on CUDA and benchmarked successfully.
- The model cache directory is present and used by the validation scripts.
- GPT OSS 120B was not downloaded locally; remote integration remains unvalidated in this run.

## GPU benchmark

- Benchmark output: [reports/benchmarks/rtx4070_real_models.md](reports/benchmarks/rtx4070_real_models.md)
- Verified local execution on an RTX 4070 SUPER.

## Provider benchmark

- Provider status report: [reports/providers/provider_status.md](reports/providers/provider_status.md)
- Live provider connectivity remains blocked by missing credentials.

## Research metrics

- MAE: 9.5186
- RMSE: 11.8383
- MAPE: 0.0328
- Directional accuracy: 0.4286
- Interval coverage: 0.4286
- Calibration ECE: 0.3714
- Sharpe (net): -4.0898
- Sortino (net): -5.8462
- Max drawdown: -0.1799
- Calmar (net): -4.6821

## Backtesting metrics

- The existing backtesting utilities were not executed as a full portfolio exercise in this run.
- The research validation output includes a net strategy result with negative performance and a bootstrap p-value indicating no evidence of alpha in this single run.

## Limitations

- No real provider credentials were available for Alpha Vantage, Tiingo, Finnhub, FRED, SEC EDGAR, CoinGecko, Binance, World Bank, IMF, Nasdaq Data Link, or Financial Modeling Prep.
- The Windows environment still shows a pyarrow-related collection crash during pytest startup, even though pytest completes and reports the expected skips.
- The API health endpoint was not reachable from the current environment during the verification pass.

## Future work

- Add approved provider credentials and rerun the live-provider matrix.
- Expand the research dataset beyond the single AAPL Yahoo Finance sample.
- Re-run the full backtest suite with cost, spread, slippage, turnover, and significance analysis.
- Resolve the Windows pyarrow and API health issues before treating the project as fully production-ready.

## GitHub readiness

- The project has validated local research artifacts, benchmark output, and reproducible scripts.
- The repository is suitable for portfolio presentation as a validated research prototype, not as a production-approved system.

## Portfolio readiness

- Research evidence is now present and documented.
- The project is portfolio-ready as a research validation demo, with the caveat that live-provider and production-stage claims remain explicitly blocked.

## Production blockers

- Missing provider credentials
- Missing multi-asset research datasets
- Missing full backtest and compliance evidence
- Windows environment issue around pyarrow collection
- API health reachability issue
