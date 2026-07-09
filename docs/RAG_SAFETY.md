# RAG safety for GPT OSS

All retrieved documents are untrusted input, including SEC filings, news, analyst
notes, macro publications, transcripts, and internal documents.

## Before inference

`EvidencePackBuilder`:

1. neutralizes common prompt-injection instruction patterns;
2. preserves evidence IDs, source metadata, and timestamps;
3. rejects duplicate evidence IDs;
4. keeps evidence distinct from system policy and computed outputs;
5. produces a deterministic evidence-pack hash for the audit block.

Sanitization is defense in depth, not a proof of safety. Retrieval must also enforce
the forecast cutoff, source allowlists, metadata filters, size limits, malware/content
controls where applicable, and access authorization before retrieval.

## During inference

The system policy labels excerpts as untrusted data and forbids following embedded
instructions. The response must match a bounded JSON schema. Low temperature, maximum
context, and maximum output tokens are configuration controls, not grounding proof.

## After inference

FINORA validates that:

- every claim cites supplied evidence IDs;
- no citation ID was invented;
- the audit run ID and evidence-pack hash match;
- insufficient evidence is explicitly flagged;
- the human-review gate remains enabled.

A citation does not prove that its claim follows from the source. Evaluation and human
review must test entailment, quotation accuracy, temporal relevance, source quality,
and omitted contradictory evidence.

Never write full private prompts or sensitive excerpts to application logs. The audit
ledger stores hashes, safe metadata, citations, structured reports, and review events
under the applicable retention/access policy.
