"""Benchmark the real FINORA ONNX Runtime artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from aurum.benchmarking import BenchmarkReport, benchmark_runtime, hardware_inventory
from aurum.kdq.config import KDQConfig


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmarks/onnx"))
    parser.add_argument("--batch-sizes", default="1,8,32")
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args()
    import onnxruntime as ort
    import torch

    if torch.cuda.is_available() and hasattr(ort, "preload_dlls"):
        ort.preload_dlls()

    manifest = json.loads((args.artifact / "manifest.json").read_text(encoding="utf-8"))
    config = KDQConfig.model_validate(manifest["model_config"])
    model = args.model or args.artifact / "finora-kdq.onnx"
    if not model.is_file():
        raise SystemExit(f"missing ONNX artifact: {model}")
    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if "CUDAExecutionProvider" in ort.get_available_providers()
        else ["CPUExecutionProvider"]
    )
    session = ort.InferenceSession(str(model), providers=providers)
    active_provider = session.get_providers()[0]
    blockers = []
    if providers[0] == "CUDAExecutionProvider" and active_provider != providers[0]:
        blockers.append(
            "CUDAExecutionProvider was installed but could not load; benchmark used CPU"
        )
    results = []
    for batch in [int(item) for item in args.batch_sizes.split(",")]:
        inputs = {
            "time_series": np.zeros(
                (batch, config.sequence_length, config.time_features), dtype=np.float32
            ),
            "text_ids": np.ones((batch, config.max_text_length), dtype=np.int64),
            "text_mask": np.ones((batch, config.max_text_length), dtype=bool),
            "tabular": np.zeros((batch, config.tabular_features), dtype=np.float32),
        }
        results.append(
            benchmark_runtime(
                "onnxruntime",
                "int8" if "int8" in model.name else "fp32",
                active_provider,
                batch,
                lambda local_inputs=inputs: session.run(["forecast_mean"], local_inputs)[0],
                iterations=args.iterations,
            )
        )
    BenchmarkReport(hardware=hardware_inventory(), results=results, blockers=blockers).write(
        args.output
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
