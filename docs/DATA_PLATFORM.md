# FINORA data platform

Phase 2 connectors cover Yahoo Finance, Alpha Vantage, Tiingo, Stooq, Nasdaq Data Link,
FRED, SEC EDGAR, CoinGecko, Binance, Financial Modeling Prep, Finnhub, World Bank, IMF,
ECB, and OECD. All network adapters normalize into typed contracts and use resilient
transport; `DataSynchronizer` owns compression, quality acceptance, lineage, parallel
downloads, and checkpoint recovery.

The local data platform implements immutable content-addressed storage and a resilient
connector transport. It is the foundation for the directive:

```text
raw → validated → normalized → cleaned → feature store → training dataset
    → model input → inference cache → analytics store
```

## Guarantees

- Raw bytes are never overwritten.
- Dataset versions are SHA-256 content addresses.
- Derived manifests record parent hashes, transformation names and versions, exact
  configuration hashes, source metadata, timestamps, and quality metrics.
- Writes use `fsync` followed by atomic replacement.
- Reads verify content integrity.
- Unsafe dataset identifiers are rejected before path construction.

## Connector behavior

`ResilientJSONClient` provides thread-safe token-bucket rate limiting, bounded timeout,
exponential backoff with jitter, response schema validation, deterministic test
injection, and atomic disk caching. Connectors fail closed after retry exhaustion.

Currently normalized first-party adapters are implemented for CSV, synthetic fixtures,
FRED, and SEC submissions. The resilient transport is ready for additional source
adapters, but a provider is not advertised as supported until its schema normalizer,
rate-limit policy, quality metrics, contract tests, and licensing review are complete.
This intentionally avoids “checkbox connectors” that silently return malformed data.

## Quality contract

Every lake object records row count, missing values, duplicate rows, schema validity,
chronological ordering when relevant, and a normalized quality score. Source-specific
adapters may add freshness, revision, corporate-action, timezone, and unit checks.

## Production scaling

The `LocalDataLake` contract can be implemented over object storage with write-once
retention and a catalog database. Atomic local writes become multipart uploads followed
by catalog transactions; content and lineage hashes remain unchanged.
