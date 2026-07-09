# FINORA architecture

> Phase 2 production note: the dependency-light modules described below remain as
> backward-compatible offline baselines. Production deployments use
> `forecast_system.py` (Chronos-2, NeuralForecast, XGBoost/LightGBM and conformal
> calibration), `rag.py` (Qdrant hybrid retrieval plus cross-encoder reranking),
> `knowledge_graph.py` (Neo4j), and `llm.py` (evidence-constrained GPT-OSS). No
> optional adapter silently substitutes a baseline. See
> [the production guide](PHASE2_PRODUCTION.md).

FINORA separates immutable facts, deterministic analytics, optional model providers,
and presentation. Numerical conclusions do not depend on an LLM.

```text
CSV / FRED / SEC / market adapters
                 │
                 ▼
        normalized timestamped data ───────────────┐
                 │                                 │
                 ▼                                 ▼
      temporal/schema validation           evidence repository
                 │                                 │
                 ▼                                 ▼
 Tier 0 baselines → Tier 1 statistics → Tier 2 ML │
                 │                         hybrid retrieval
                 ▼                                 │
      purged walk-forward selection ◄──────────────┘
                 │
      ┌──────────┼───────────┬──────────────┐
      ▼          ▼           ▼              ▼
    risk      scenarios   macro/NLP      graph paths
      └──────────┴───────────┴──────────────┘
                 │
                 ▼
         governance enforcement
    (cutoff, hashes, limits, review flags)
                 │
                 ▼
      AnalysisReport + Markdown rendering
                 │
        ┌────────┴────────┐
        ▼                 ▼
  SQLite/audit chain   FastAPI / CLI
```

## Analytical discipline

`ForecastRequest` enforces unique chronological dates and rejects observations on or
after the forecast start. Each candidate is evaluated through expanding-window
walk-forward validation with a purge equal to the forecast horizon. Horizon forecasts
are recursive; models are never evaluated against randomly shuffled targets.

The model table retains every candidate’s error, directional accuracy, calibration,
tier, and feature importance where available. Selection is based on out-of-sample
RMSE. Random walk remains the explicit baseline.

Risk uses log returns and discloses historical VaR/CVaR, drawdown, higher moments,
liquidity penalty, and stress scaling. Backtests lag requested positions by one period
before applying returns, then charge turnover-sensitive spread and slippage.

## Retrieval and causality

Evidence is stored with source, publication timestamp, confidence, source type, and
entities. The local retriever combines IDF-weighted lexical relevance, deterministic
hashed-vector cosine similarity, and phrase overlap. It filters by publication cutoff
before scoring. `governance.verify_temporal_grounding` repeats the cutoff check at the
final report boundary, providing defense in depth.

Production dense embeddings, cross-encoders, and Qdrant can replace the local ranking
implementation while preserving the `Citation` contract.

## Persistence and audit

SQLite stores evidence and complete Pydantic report payloads. Audit events form a hash
chain:

```text
event_hash = SHA256(previous_hash | timestamp | event_type | run_id | canonical_details)
```

Each report also contains an input hash and deterministic run ID. `aurum audit` verifies
the full chain. This detects alteration; it does not replace signed remote attestation
or write-once retention in regulated production environments.

## Trust boundaries

- External payloads enter through typed Pydantic or normalized data contracts.
- Credentials come from environment variables and are never stored in reports.
- API-key authentication is an application-level local/development control; production
  identity, authorization, rate limits, and TLS belong at the service edge.
- Optional LLMs may explain a completed report but must not invent numerical results or
  citations.
- Human approval remains required for live capital or client distribution.

## Scaling path

SQLite can be replaced by Postgres/TimescaleDB, local retrieval by Qdrant plus a
cross-encoder, the in-memory graph by Neo4j, and local event logging by immutable object
storage. The service and data contracts intentionally remain stable across those
changes.

## Known limits

Offline intervals assume Gaussian innovations and square-root-time scaling. Scenario
probabilities are calibration-adjusted policy priors, not posterior probabilities.
Historical loss distributions omit unseen discontinuities. Lexical sentiment is a
transparent fallback, not FinBERT. Graph results are bounded by loaded relationships.
