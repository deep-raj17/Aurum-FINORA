"""Benchmark a real self-hosted GPT-OSS endpoint without storing generated content."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np

from aurum.benchmarking import BenchmarkReport, benchmark_runtime, hardware_inventory
from aurum.llm import GPTOSSClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=os.getenv("GPT_OSS_ENDPOINT"))
    parser.add_argument("--model", default=os.getenv("GPT_OSS_MODEL", "openai/gpt-oss-120b"))
    parser.add_argument("--quantization", required=True, choices=["mxfp4", "awq", "gptq", "fp16"])
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmarks/gpt-oss"))
    args = parser.parse_args()
    if not args.endpoint:
        raise SystemExit("GPT_OSS_ENDPOINT is required")
    client = GPTOSSClient(
        args.endpoint,
        model=args.model,
        api_token=os.getenv("GPT_OSS_API_TOKEN"),
    )

    def invoke() -> np.ndarray:
        response = client.complete(
            "Return one sentence describing why cited evidence is required in financial reports."
        )
        return np.asarray([len(response)], dtype=float)

    result = benchmark_runtime(
        f"gpt-oss:{args.model}",
        args.quantization,
        "self-hosted-endpoint",
        1,
        invoke,
        warmup=2,
        iterations=args.iterations,
    )
    BenchmarkReport(hardware=hardware_inventory(), results=[result]).write(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
