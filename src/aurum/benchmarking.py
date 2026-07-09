"""Hardware-aware latency, throughput, memory, and agreement benchmarks."""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field


class RuntimeBenchmark(BaseModel):
    runtime: str
    precision: str
    device: str
    batch_size: int
    iterations: int
    median_latency_ms: float
    p95_latency_ms: float
    throughput_per_second: float
    peak_vram_bytes: int | None = None
    peak_host_memory_bytes: int | None = None
    mean_absolute_error: float | None = None
    maximum_absolute_error: float | None = None
    model_load_time_ms: float | None = None


class BenchmarkReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    hardware: dict[str, str | int | bool]
    results: list[RuntimeBenchmark]
    blockers: list[str] = Field(default_factory=list)

    def write(self, directory: str | Path) -> tuple[Path, Path]:
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        json_path = destination / "latest.json"
        markdown_path = destination / "latest.md"
        json_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        rows = [
            "| Runtime | Precision | Device | Batch | Median ms | P95 ms | Items/s | VRAM | MAE |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for result in self.results:
            rows.append(
                f"| {result.runtime} | {result.precision} | {result.device} | "
                f"{result.batch_size} | {result.median_latency_ms:.3f} | "
                f"{result.p95_latency_ms:.3f} | {result.throughput_per_second:.2f} | "
                f"{result.peak_vram_bytes or 0} | "
                f"{result.mean_absolute_error if result.mean_absolute_error is not None else 'n/a'} |"
            )
        if self.blockers:
            rows.extend(["", "## Blockers", *[f"- {item}" for item in self.blockers]])
        markdown_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return json_path, markdown_path


def hardware_inventory() -> dict[str, str | int | bool]:
    import platform

    inventory: dict[str, str | int | bool] = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cuda_available": False,
        "gpu_count": 0,
    }
    try:
        import torch
    except ImportError:
        return inventory
    inventory["cuda_available"] = torch.cuda.is_available()
    inventory["gpu_count"] = torch.cuda.device_count() if torch.cuda.is_available() else 0
    for index in range(int(inventory["gpu_count"])):
        inventory[f"gpu_{index}"] = torch.cuda.get_device_name(index)
        inventory[f"gpu_{index}_vram_bytes"] = torch.cuda.get_device_properties(index).total_memory
    return inventory


def benchmark_runtime(
    runtime: str,
    precision: str,
    device: str,
    batch_size: int,
    function: Callable[[], np.ndarray],
    *,
    synchronize: Callable[[], None] | None = None,
    vram: Callable[[], int] | None = None,
    reference: np.ndarray | None = None,
    warmup: int = 10,
    iterations: int = 100,
    model_load_time_ms: float | None = None,
) -> RuntimeBenchmark:
    if batch_size < 1 or warmup < 0 or iterations < 2:
        raise ValueError("invalid benchmark dimensions")
    for _ in range(warmup):
        function()
    if synchronize:
        synchronize()
    latencies = []
    output = None
    peak_vram = 0
    for _ in range(iterations):
        started = time.perf_counter_ns()
        output = np.asarray(function(), dtype=float)
        if synchronize:
            synchronize()
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        latencies.append(elapsed)
        if vram:
            peak_vram = max(peak_vram, int(vram()))
    if output is None or not np.all(np.isfinite(output)):
        raise RuntimeError("runtime returned non-finite output")
    errors = None if reference is None else np.abs(output - np.asarray(reference))
    ordered = sorted(latencies)
    p95 = ordered[min(len(ordered) - 1, int(np.ceil(0.95 * len(ordered))) - 1)]
    median = statistics.median(latencies)
    return RuntimeBenchmark(
        runtime=runtime,
        precision=precision,
        device=device,
        batch_size=batch_size,
        iterations=iterations,
        median_latency_ms=median,
        p95_latency_ms=p95,
        throughput_per_second=batch_size / (median / 1000),
        peak_vram_bytes=peak_vram or None,
        mean_absolute_error=float(errors.mean()) if errors is not None else None,
        maximum_absolute_error=float(errors.max()) if errors is not None else None,
        model_load_time_ms=model_load_time_ms,
    )
