"""Repeatable latency, memory, and numerical-agreement benchmarks."""

from __future__ import annotations

import statistics
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    iterations: int
    median_latency_ms: float
    p95_latency_ms: float
    peak_memory_bytes: int
    mean_absolute_error: float | None
    maximum_absolute_error: float | None


def benchmark_predictor(
    name: str,
    predictor: Callable[[], np.ndarray],
    *,
    reference: np.ndarray | None = None,
    warmup: int = 5,
    iterations: int = 50,
) -> BenchmarkResult:
    if warmup < 0 or iterations < 2:
        raise ValueError("benchmark requires non-negative warmup and at least two iterations")
    for _ in range(warmup):
        predictor()
    latencies = []
    output: np.ndarray | None = None
    tracemalloc.start()
    for _ in range(iterations):
        started = time.perf_counter_ns()
        output = np.asarray(predictor(), dtype=float)
        latencies.append((time.perf_counter_ns() - started) / 1_000_000)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if output is None or not np.all(np.isfinite(output)):
        raise RuntimeError("benchmark predictor returned non-finite output")
    mae = maximum = None
    if reference is not None:
        expected = np.asarray(reference, dtype=float)
        if expected.shape != output.shape:
            raise ValueError("reference and predictor output shapes differ")
        errors = np.abs(expected - output)
        mae = float(errors.mean())
        maximum = float(errors.max())
    ordered = sorted(latencies)
    p95_index = min(len(ordered) - 1, int(np.ceil(0.95 * len(ordered))) - 1)
    return BenchmarkResult(
        name=name,
        iterations=iterations,
        median_latency_ms=float(statistics.median(latencies)),
        p95_latency_ms=float(ordered[p95_index]),
        peak_memory_bytes=peak,
        mean_absolute_error=mae,
        maximum_absolute_error=maximum,
    )
