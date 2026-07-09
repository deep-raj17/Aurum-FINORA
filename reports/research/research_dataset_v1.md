# Research dataset v1

Validation date: 2026-07-02

## Scope

The dataset build was executed through the existing research validation script using Yahoo Finance data for AAPL with an expanding-window walk-forward run.

## Source snapshot

- Provider: Yahoo Finance
- Symbol: AAPL
- Date range: approximately 180 calendar days ending 2026-07-01
- Rows retained after quality validation: 123
- Validation output: [reports/research/yahoo-aapl-xgboost-expanding.json](reports/research/yahoo-aapl-xgboost-expanding.json)

## Metrics captured

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

## Notes

- This is a research-only artifact and not a production dataset approval.
- The run used a single-symbol, single-provider validation path and should not be interpreted as broad multi-asset research coverage.
