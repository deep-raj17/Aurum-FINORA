# Data-provider validation setup

Set `FINORA_RUN_LIVE_TESTS=1` only for an intentional research/staging validation.
For local research, copy `.env.example` to the ignored `.env`; CI and production
should use protected environment variables or mounted secret files:

| Provider | Configuration |
|---|---|
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` |
| Tiingo | `TIINGO_API_KEY` |
| Finnhub | `FINNHUB_API_KEY` |
| Nasdaq Data Link | `NASDAQ_DATA_LINK_API_KEY`, optional test dataset |
| FRED | `FRED_API_KEY` |
| SEC EDGAR | `SEC_USER_AGENT` containing a monitored contact email |
| Financial Modeling Prep | `FMP_API_KEY` |
| Yahoo, Stooq, CoinGecko, Binance, World Bank, IMF | network gate only |
| ECB | `ECB_TEST_DATASET`, `ECB_TEST_KEY`, optional geography |
| OECD | `OECD_TEST_DATASET`, `OECD_TEST_KEY`, optional geography |

## Phase 3A Research Validation

For Phase 3A research validation, the following providers are prioritized:

- **Alpha Vantage**: Historical OHLCV data, technical indicators, forex, crypto
- **Tiingo**: High-quality end-of-day data, news sentiment, fundamentals
- **Finnhub**: Real-time quotes, financial news, company fundamentals, earnings

These providers support the research validation pipeline with real historical data
for model training and backtesting.

## Safe Startup Validation

FINORA includes safe startup validation in `src/aurum/config.py`:

```python
from aurum.config import validate_api_keys

# Check which API keys are configured
status = validate_api_keys()
# Returns: {'ALPHA_VANTAGE': True, 'TIINGO': False, ...}
```

Missing API keys will log warnings but not block startup. Live provider tests
will automatically skip when credentials are absent.

Run (PowerShell):

```powershell
$env:FINORA_RUN_LIVE_TESTS="1"
pytest -m live tests/integration/test_live_providers.py -ra
```

Any skip in the staging report is an incomplete provider gate. Validate vendor
entitlements, quotas, symbol mapping, timestamps, adjustments, revision behavior and
historical depth separately from HTTP success.
