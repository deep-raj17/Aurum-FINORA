# Provider status

Validation date: 2026-07-02

This status report is based on the local environment and the existing FINORA provider connector code. No provider credentials were present in the local environment, so live connectivity and dataset retrieval were not executed.

| Provider | Connection status | Rate limit | Latency | Authentication | Dataset availability |
|---|---|---|---|---|---|
| Yahoo Finance | Not executed (no live credentials required for local package path, but no live request was run) | Unknown | Unknown | Not applicable | Not verified |
| Alpha Vantage | Not executed | Unknown | Unknown | Not configured | Not verified |
| Tiingo | Not executed | Unknown | Unknown | Not configured | Not verified |
| Finnhub | Not executed | Unknown | Unknown | Not configured | Not verified |
| FRED | Not executed | Unknown | Unknown | Not configured | Not verified |
| SEC EDGAR | Not executed | Unknown | Unknown | Not configured | Not verified |
| CoinGecko | Not executed | Unknown | Unknown | Not configured | Not verified |
| Binance | Not executed | Unknown | Unknown | Not configured | Not configured |
| World Bank | Not executed | Unknown | Unknown | Not configured | Not verified |
| IMF | Not executed | Unknown | Unknown | Not configured | Not verified |
| Nasdaq Data Link | Not executed | Unknown | Unknown | Not configured | Not verified |
| Financial Modeling Prep | Not executed | Unknown | Unknown | Not configured | Not verified |

## Notes

- The local environment contains a .env file, but none of the requested provider credentials were populated.
- Live-provider validation remains blocked until approved credentials are supplied locally.
- The repository still contains the connector implementations for these providers, but they were not exercised in the current run.
