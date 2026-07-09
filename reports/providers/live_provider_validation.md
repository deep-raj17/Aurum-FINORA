# Phase 6 live-provider validation

Validation date: 2026-07-02  
Current status: **not executed — credential safety gate applied**

`.env` exists locally and is excluded by `.gitignore`. FINORA checked only whether
supported credential names had non-empty values; it did not print or store any values.

At the Phase 6 validation cutoff, none of these were configured:

- `ALPHA_VANTAGE_API_KEY`
- `TIINGO_API_KEY`
- `NASDAQ_DATA_LINK_API_KEY`
- `FMP_API_KEY`
- `FINNHUB_API_KEY`
- `FRED_API_KEY`
- `SEC_USER_AGENT`

The instruction was to run live tests only when `.env` credentials exist. Therefore:

| Item | Result |
|---|---|
| Credentialed live tests | Not run |
| Credentialless network live tests | Not run as part of this credential-gated invocation |
| Secrets printed or copied to report | No |
| Historical provider report reused as current evidence | No |

After populating approved credentials locally, run:

```powershell
$env:FINORA_RUN_LIVE_TESTS="1"
pytest -m live tests/integration/test_live_providers.py -ra
```

Do not commit `.env`. A successful future run must replace this report with provider,
dataset, cutoff, quality, retry, and failure evidence. Until then, the live-provider
gate blocks staging readiness.
