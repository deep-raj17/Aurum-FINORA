"""Benchmark cached real FinBERT and Chronos weights on the local CUDA device."""

from __future__ import annotations

import argparse
import platform
import statistics
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from aurum.forecast_system import Chronos2Specialist
from aurum.sentiment import FinBERTSentimentAnalyzer


def _timings(function: Callable[[], Any], iterations: int) -> tuple[float, float, float]:
    import torch

    function()
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    values = []
    for _ in range(iterations):
        started = time.perf_counter()
        function()
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        values.append((time.perf_counter() - started) * 1000)
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, int(np.ceil(len(ordered) * 0.95)) - 1)
    return statistics.mean(values), statistics.median(values), ordered[p95_index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/benchmarks/rtx4070_real_models.md"),
    )
    parser.add_argument("--cache-dir", default="model_cache")
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()

    import torch

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required for the Phase 6 RTX benchmark")
    torch.set_float32_matmul_precision("high")
    device = torch.cuda.get_device_properties(0)
    results: list[dict[str, Any]] = []

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    finbert = FinBERTSentimentAnalyzer(
        "ProsusAI/finbert",
        cache_dir=args.cache_dir,
        device="cuda",
        batch_size=8,
    )
    finbert.analyse("Revenue and earnings exceeded expectations.")
    torch.cuda.synchronize()
    load_ms = (time.perf_counter() - started) * 1000
    texts = [
        "Revenue and earnings exceeded expectations.",
        "Management reduced full-year guidance.",
        "Operating cash flow remained stable.",
        "Credit spreads widened during the quarter.",
        "Demand improved in the core segment.",
        "Margins declined because of input costs.",
        "The filing disclosed no material change.",
        "Liquidity remained above the internal threshold.",
    ]
    mean, p50, p95 = _timings(lambda: finbert.analyse_batch(texts), args.iterations)
    results.append(
        {
            "model": "ProsusAI/finbert",
            "workload": "batch=8 text classification",
            "load_ms": load_ms,
            "mean_ms": mean,
            "p50_ms": p50,
            "p95_ms": p95,
            "peak_vram_mb": torch.cuda.max_memory_allocated() / 1024**2,
        }
    )

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    values = 100 * np.exp(np.cumsum(np.random.default_rng(17).normal(0, 0.01, 160)))
    dates = [date(2025, 1, 1) + timedelta(days=index) for index in range(len(values))]
    chronos = Chronos2Specialist(
        "amazon/chronos-t5-tiny",
        device_map="cuda",
        cache_dir=args.cache_dir,
    )
    started = time.perf_counter()
    chronos.forecast(values, dates, 5)
    torch.cuda.synchronize()
    load_ms = (time.perf_counter() - started) * 1000
    mean, p50, p95 = _timings(
        lambda: chronos.forecast(values, dates, 5),
        args.iterations,
    )
    results.append(
        {
            "model": "amazon/chronos-t5-tiny",
            "workload": "context=160 horizon=5 samples=50",
            "load_ms": load_ms,
            "mean_ms": mean,
            "p50_ms": p50,
            "p95_ms": p95,
            "peak_vram_mb": torch.cuda.max_memory_allocated() / 1024**2,
        }
    )

    lines = [
        "# RTX 4070 real-model benchmark",
        "",
        f"- GPU: {device.name}",
        f"- VRAM: {device.total_memory / 1024**3:.2f} GiB",
        f"- Torch: {torch.__version__}",
        f"- CUDA runtime: {torch.version.cuda}",
        f"- Python/platform: {platform.python_version()} / {platform.platform()}",
        f"- Timed iterations per workload: {args.iterations}",
        "- Status: local execution evidence only; not a production performance approval.",
        "",
        "| Model | Workload | Load ms | Mean ms | P50 ms | P95 ms | Peak VRAM MiB |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            f"| {row['model']} | {row['workload']} | {row['load_ms']:.2f} | "
            f"{row['mean_ms']:.2f} | {row['p50_ms']:.2f} | {row['p95_ms']:.2f} | "
            f"{row['peak_vram_mb']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "These measurements prove that the checked model revisions execute on this RTX 4070 "
            "workstation. They are short local samples, not SLO, capacity, accuracy, stress, soak, "
            "or production approval evidence. GPT OSS 120B was not downloaded or benchmarked.",
            "",
        ]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
