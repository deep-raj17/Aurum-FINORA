# API key setup

1. Copy `.env.example` to `.env`.
2. Populate only the providers you are authorized to use:

```dotenv
ALPHA_VANTAGE_API_KEY=
TIINGO_API_KEY=
FINNHUB_API_KEY=
```

`.env` and `.env.*` are ignored except `.env.example`. Never paste key values into
source, tests, logs, issues, reports, shell history, or commits. Mounted `*_FILE`
secrets remain the production preference.

FINORA loads `.env` without overriding process-level variables. Normal tests skip all
live calls. To authorize credentialed calls explicitly:

```powershell
$env:FINORA_RUN_LIVE_TESTS="1"
pytest -m live tests/integration/test_live_providers.py -ra
```

Missing provider keys cause only that provider test to skip. In a release pipeline any
skip is a blocked validation gate, not a passing provider result.
