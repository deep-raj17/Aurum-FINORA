# Stage 1 verification report

Status date: 2026-07-13

## Purpose

Stage 1 verification confirms that the frozen FINORA engineering baseline is locally
healthy before publishing additional RP1 evidence.

This is a verification record, not an engineering expansion.

## Verification commands

```text
ruff check src tests scripts
ruff format --check src tests scripts
pytest -q -ra
mypy src
```

The mypy command was executed with a Windows-safe `Start-Process -Wait` wrapper.

## Results

| Gate | Result |
|---|---|
| Ruff lint | Pass: all checks passed |
| Ruff format check | Pass: 119 files already formatted |
| Pytest | Pass |
| Mypy | Pass: no issues found in 74 source files |

## Pytest details

Observed result:

```text
147 passed, 26 skipped
```

Skipped tests are the expected gated integration tests:

- 15 live-provider tests skipped until `FINORA_RUN_LIVE_TESTS=1`
- 11 real-model tests skipped until `FINORA_RUN_MODEL_TESTS=1`

Warnings were limited to existing PyTorch / ONNX / quantization deprecation and export
warnings in KDQ tests. No verification failure was observed.

## Decision

Stage 1 verification passed.

FINORA is clear to continue RP1 evidence publication from the current frozen
engineering baseline.

## Next action

Publish RP1 evidence without adding engineering features, models, APIs, dashboards, or
commercial documentation.
