# FINORA v1.0 operating charter

FINORA is a transparent, auditable, probabilistic financial decision-support
system—not an oracle and not an investment adviser.

## Non-negotiable rules

1. Every forecast includes 80% and 95% intervals and names its distributional
   assumption.
2. Evidence must predate the forecast start. Every external factual claim carries
   origin, publication date, confidence, and relevance.
3. Retrieval failure is disclosed. A missing evidence base must never be disguised
   as grounded analysis.
4. Validation is chronological, walk-forward, and purged by at least the forecast
   horizon. Random time-series splits and lookahead are forbidden.
5. Naive baselines are the minimum bar. More complex models are admitted only after
   demonstrated out-of-sample benefit.
6. Risk, costs, model limitations, regime assumptions, and falsification conditions
   are primary outputs.
7. Backtests lag positions, include costs, and report gross and net results.
8. Human review is mandatory before capital allocation or client distribution.

## Required report anatomy

Executive summary; data and evidence; analysis; forecast and scenarios; prioritised
risk flags; what would change the view; and an audit block.

## Operational context

- Universe: user-supplied positive-valued financial time series; adapters are
  available for broader market and macro data.
- Primary horizon: 1–252 periods.
- Offline models: random walk, historical mean, drift, robust drift, Holt linear,
  AR(1), and ridge autoregression, selected by purged walk-forward RMSE.
- Retrieval: temporally filtered hybrid lexical/hashed-dense/phrase reranking in the
  offline store; Qdrant and cross-encoder services are production expansion points.
- Graph: explicit directed relationship paths.
- Cost assumption: 10 bp round trip plus 5 bp slippage by default.
- Compliance scope: research decision support; human review required.

The full council-authored brief supplied for this project remains the normative
product specification. This file records the enforceable runtime subset implemented
by the reference core.
