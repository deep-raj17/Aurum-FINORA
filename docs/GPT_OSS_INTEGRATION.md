# GPT OSS 120B integration

GPT OSS 120B is FINORA-MoE's elite grounded reasoning and teacher layer. It is not a
mathematical forecasting engine.

```text
Data + Forecast Experts + Risk Experts + Graph Experts + RAG Evidence
                              ↓
                    Evidence Pack Builder
                              ↓
                 GPT OSS 120B (remote only)
                              ↓
              Grounded Financial Reasoning Report
                              ↓
                Audit Ledger + Human Review Gate
```

## Permitted roles

GPT OSS 120B may act as chief financial reasoning engine, RAG synthesis engine,
filing/news/macro analyst, scenario generator, risk explainer, audit-block generator,
compliance explanation assistant, knowledge-distillation teacher, final report
generator, and coordinator of macro/sentiment/risk/graph/forecast outputs.

It must not directly predict prices, forecast raw time series, compute technical
indicators, execute backtests, calculate VaR/CVaR, run portfolio optimization, clean
data, or engineer features. Those remain deterministic or specialist-model duties.

## Typed runtime path

`EvidencePackBuilder` sanitizes retrieved text and creates `ReasoningEvidencePack`.
The pack carries:

- retrieved evidence with evidence ID, source, excerpt, and timestamp;
- PatchTST/iTransformer/TFT/TiDE/Chronos outputs;
- XGBoost/LightGBM/CatBoost risk and alpha outputs;
- FinBERT sentiment and graph-attention risk outputs;
- uncertainty intervals and cost-aware backtest metrics;
- data-quality flags and governed audit metadata.

`GPTOSSClient.reason_from_pack()` accepts only that computed pack and a permitted
reasoning task. It validates a structured `GroundedFinancialReport` containing an
executive summary, cited reasoning, scenarios, risk and disagreement analysis,
uncertainty explanation, limitations, audit block, and review recommendation.

Unknown citations, mismatched evidence-pack hashes/run IDs, invalid schemas, or any
attempt to waive human review fail closed. An empty evidence set is admissible only
when the output explicitly flags insufficient evidence and recommends review.

## Remote deployment

RTX 4070 12GB is not sufficient for GPT OSS 120B. Local loading is disabled in code.
Use a remote endpoint, cloud GPU server, hosted vLLM/SGLang service, or compatible
chat-completions server.

```dotenv
FINORA_LLM_PROVIDER=gpt_oss
FINORA_LLM_MODEL_ID=gpt-oss-120b
FINORA_LLM_ENDPOINT=https://your-private-inference.example
FINORA_LLM_API_KEY=
FINORA_LLM_MODE=remote
FINORA_LLM_MAX_CONTEXT=131072
FINORA_LLM_MAX_TOKENS=4096
FINORA_LLM_TEMPERATURE=0.1
```

The endpoint must provide TLS, authentication, bounded retries/timeouts, tenant
isolation, regional/data-residency controls where required, and a retention policy
appropriate to the documents. Supply the key via environment or mounted secret file.

## Development fallback

`TransformersGPTOSSClient` permits an explicitly configured smaller local instruct
model, but rejects GPT OSS 20B/120B identifiers. Local fallback output is
development-only and cannot satisfy real-weight, benchmark, compliance, or model-risk
release gates.
