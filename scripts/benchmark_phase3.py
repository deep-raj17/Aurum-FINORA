"""Benchmark a governed FINORA TorchScript artifact on CPU or CUDA."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from aurum.benchmarking import (
    BenchmarkReport,
    benchmark_runtime,
    hardware_inventory,
)
from aurum.kdq.config import KDQConfig
from aurum.kdq.export import example_inputs


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("artifact", type=Path)
    value.add_argument("--model", type=Path)
    value.add_argument("--output", type=Path, default=Path("docs/benchmarks"))
    value.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    value.add_argument("--precision", choices=["fp32", "fp16", "bf16", "int8"], default="fp16")
    value.add_argument("--batch-sizes", default="1,8,32")
    value.add_argument("--iterations", type=int, default=100)
    return value


def main() -> int:
    args = parser().parse_args()
    import torch

    if args.device == "cuda" and not torch.cuda.is_available():
        report = BenchmarkReport(
            hardware=hardware_inventory(),
            results=[],
            blockers=["CUDA device is not available"],
        )
        report.write(args.output)
        return 2
    if args.device == "cpu" and args.precision in {"fp16", "bf16"}:
        report = BenchmarkReport(
            hardware=hardware_inventory(),
            results=[],
            blockers=[f"{args.precision} mixed-precision benchmarking requires CUDA"],
        )
        report.write(args.output)
        return 2
    manifest = json.loads((args.artifact / "manifest.json").read_text(encoding="utf-8"))
    config = KDQConfig.model_validate(manifest["model_config"])
    model_path = args.model or args.artifact / "finora-kdq.pt"
    if not model_path.exists():
        raise SystemExit(f"missing exported runtime: {model_path}")
    load_started = time.perf_counter_ns()
    model = torch.jit.load(str(model_path), map_location=args.device).eval()
    load_time_ms = (time.perf_counter_ns() - load_started) / 1_000_000
    dtype = {
        "fp32": torch.float32,
        "fp16": torch.float16,
        "bf16": torch.bfloat16,
        "int8": torch.float32,
    }[args.precision]
    autocast_enabled = args.device == "cuda" and args.precision in {"fp16", "bf16"}
    results = []
    reference = None
    for batch in [int(item) for item in args.batch_sizes.split(",")]:
        inputs = list(example_inputs(config, batch))
        inputs[0] = inputs[0].to(args.device)
        inputs[1] = inputs[1].to(args.device)
        inputs[2] = inputs[2].to(args.device)
        inputs[3] = inputs[3].to(args.device)

        def invoke(local_inputs=inputs) -> np.ndarray:
            with (
                torch.inference_mode(),
                torch.autocast(
                    device_type=args.device,
                    dtype=dtype,
                    enabled=autocast_enabled,
                ),
            ):
                output = model(*local_inputs)[0]
            return output.detach().float().cpu().numpy()

        if reference is None:
            reference = invoke()
        results.append(
            benchmark_runtime(
                "torchscript",
                args.precision,
                args.device,
                batch,
                invoke,
                synchronize=torch.cuda.synchronize if args.device == "cuda" else None,
                vram=(lambda: torch.cuda.max_memory_allocated() if args.device == "cuda" else 0),
                reference=reference if reference.shape == (batch,) else None,
                iterations=args.iterations,
                model_load_time_ms=load_time_ms,
            )
        )
    BenchmarkReport(hardware=hardware_inventory(), results=results).write(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
