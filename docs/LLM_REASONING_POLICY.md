# LLM reasoning policy

## Authority boundary

FINORA-MoE specialist experts own numerical forecasting and risk outputs. GPT OSS
120B may explain, compare, synthesize, coordinate, and report those outputs. It may
not alter an expert result without labeling the change as a narrative scenario, and
it may never present an invented number as a computed result.

Permitted task values are defined by `LLMReasoningTask`; there is deliberately no
raw-forecasting task. The client interface accepts an evidence pack rather than a
time-series tensor.

## Grounding

Every external factual claim must cite one or more evidence IDs from the supplied
pack. Evidence absence, conflict, staleness, model disagreement, poor data quality,
and wide intervals must be disclosed. Citation presence is machine-validated; factual
relevance remains part of human and evaluation review.

The report must explain:

- what the expert models agree and disagree on;
- what uncertainty intervals and calibration do and do not imply;
- scenario assumptions rather than fabricated probabilities;
- material risks, data-quality flags, limitations, and invalidation conditions.

No private chain-of-thought is requested or stored. Persist only structured outputs,
citations, model/version identifiers, pack hashes, review status, and approved
operational telemetry.

## Human review and compliance

Every LLM report requires human review. The model cannot approve trading, client
distribution, regulatory suitability, or compliance. A reviewer may accept, reject,
or escalate the narrative, while the immutable computed outputs remain available for
comparison.

GPT OSS may draft audit and compliance explanations, but deterministic code supplies
run IDs, hashes, timestamps, model versions, scope, and policy decisions. Mismatched
audit metadata fails closed.

## Security

Never log API keys, authorization headers, full private prompts, sensitive source
documents, or credentials. Use secret management, TLS, least-privilege endpoints,
request size limits, bounded response tokens, and provider retention controls.
Operational logs may contain only safe IDs, hashes, timings, status codes, and
redacted error classes.
