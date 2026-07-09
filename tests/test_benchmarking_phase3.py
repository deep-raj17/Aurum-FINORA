import numpy as np
import pytest

from aurum.benchmarking import BenchmarkReport, benchmark_runtime, hardware_inventory


def test_phase3_benchmark_records_throughput_accuracy_and_reports(tmp_path) -> None:
    result = benchmark_runtime(
        "test",
        "fp32",
        "cpu",
        2,
        lambda: np.array([1.0, 2.0]),
        reference=np.array([1.0, 2.1]),
        warmup=1,
        iterations=3,
    )
    assert result.throughput_per_second > 0
    assert result.mean_absolute_error == pytest.approx(0.05)
    json_path, markdown_path = BenchmarkReport(
        hardware={"cuda_available": False}, results=[result]
    ).write(tmp_path)
    assert json_path.is_file()
    assert "Items/s" in markdown_path.read_text(encoding="utf-8")
    assert "cuda_available" in hardware_inventory()
    with pytest.raises(ValueError, match="dimensions"):
        benchmark_runtime("bad", "fp32", "cpu", 0, lambda: np.array([1]), iterations=1)
