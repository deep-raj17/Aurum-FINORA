# FINORA Phase 3A validation report

Generated: 2026-07-01  
Classification: **research-ready and GitHub-ready; not production-approved**

## Automated engineering gates

- Ruff: pass
- Mypy: pass (71 source files)
- Pytest: 121 passed, 23 safely skipped
- Coverage: 95.06%
- Docker core image: built
- API health: `ok`, decision-support mode, audit chain valid

## Real providers

Live pass: Yahoo Finance, CoinGecko, Binance, World Bank, and IMF.

Blocked/skipped: Alpha Vantage, Tiingo, Finnhub, Nasdaq Data Link, FMP, FRED, SEC
EDGAR, ECB, and OECD because their credential/configuration values were absent.

Failed: Stooq returned HTTP 404 without a browser user agent and an HTML denial page
with one; this is an external access-policy failure, not a passing provider result.

## Real models

- Downloaded/cached: `amazon/chronos-t5-tiny` (about 34 MB) and
  `ProsusAI/finbert` (about 876 MB).
- Locally executed: Chronos Tiny, FinBERT, PatchTST, TFT, N-HiTS, XGBoost, and
  LightGBM.
- Remote-only: GPT-OSS 20B/120B. No endpoint was configured, so the endpoint test
  skipped. Oversized local loading is blocked by policy on this 12 GB workstation.

## RTX 4070 SUPER smoke benchmark

FINORA-KD-Q smoke artifact, TorchScript FP16:

| Batch | Median ms | P95 ms | Items/s | Peak allocated VRAM |
|---:|---:|---:|---:|---:|
| 1 | 1.992 | 3.019 | 502 | 9,809,920 bytes |
| 8 | 2.235 | 4.206 | 3,579 | 9,862,144 bytes |
| 32 | 2.211 | 3.478 | 14,474 | 10,044,928 bytes |

Model load time was 119.418 ms. Hardware reported 12,878,086,144 bytes total VRAM.
This validates the smoke runner, not production model accuracy.

## Real-data research run

Yahoo/AAPL/XGBoost expanding-window validation generated 12 out-of-sample records:
MAE 13.9581, RMSE 17.0549, MAPE 4.85%, directional accuracy 41.67%, interval coverage
25%, and coverage ECE 55%. The cost-adjusted research calculation produced Sharpe
6.056, Sortino 13.950, Calmar 258.987, maximum drawdown -9.24%, turnover 7.0, and
annualized net return 2394%.

Those strategy figures are **not credible alpha evidence**: twelve observations are
far below an approval-quality sample and coverage/calibration are poor. The report
therefore records `alpha: false`.

## Remaining gates

- Populate the ignored `.env` locally for Alpha Vantage, Tiingo, and Finnhub.
- Resolve/replace Stooq access and rerun the provider matrix.
- Configure and validate a remote GPT-OSS endpoint.
- Expand real-data walk-forward validation across assets and every material regime.
- Complete governed calibration, bias, sustained load, DR, and production security
  evidence.
- Record signed model-risk, data-owner, security, and compliance approvals.

FINORA is not approved for real financial decisions.
