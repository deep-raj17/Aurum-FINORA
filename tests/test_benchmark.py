import sys
import types

import numpy as np
import pytest

from aurum.kdq.benchmark import benchmark_predictor
from aurum.kdq.export import (
    compile_tensorrt,
    quantize_onnx_dynamic,
    quantize_onnx_static,
)


def test_benchmark_measures_latency_memory_and_accuracy() -> None:
    result = benchmark_predictor(
        "int8",
        lambda: np.array([1.0, 2.01]),
        reference=np.array([1.0, 2.0]),
        warmup=1,
        iterations=3,
    )
    assert result.p95_latency_ms >= result.median_latency_ms
    assert result.peak_memory_bytes > 0
    assert result.mean_absolute_error == pytest.approx(0.005)


def test_tensorrt_compiler_rejects_unsupported_precision(tmp_path) -> None:
    with pytest.raises(ValueError, match="precision"):
        compile_tensorrt(tmp_path / "model.onnx", tmp_path / "model.engine", precision="fp8")


def test_onnx_quantizers_validate_created_artifacts(tmp_path, monkeypatch) -> None:
    class QuantType:
        QInt8 = "int8"

    class QuantFormat:
        QDQ = "qdq"

    def write(source, destination, *args, **kwargs):
        from pathlib import Path

        Path(destination).write_bytes(b"quantized")

    module = types.SimpleNamespace(
        QuantType=QuantType,
        QuantFormat=QuantFormat,
        quantize_dynamic=write,
        quantize_static=write,
    )
    monkeypatch.setitem(sys.modules, "onnxruntime", types.ModuleType("onnxruntime"))
    monkeypatch.setitem(sys.modules, "onnxruntime.quantization", module)
    source = tmp_path / "source.onnx"
    source.write_bytes(b"onnx")
    assert quantize_onnx_dynamic(source, tmp_path / "dynamic.onnx").is_file()
    assert quantize_onnx_static(source, tmp_path / "static.onnx", object()).is_file()


def test_tensorrt_compiler_invokes_safe_argument_list(tmp_path, monkeypatch) -> None:
    output = tmp_path / "model.engine"

    def run(command, **kwargs):
        output.write_bytes(b"engine")
        assert "--fp16" in command
        return types.SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("aurum.kdq.export.subprocess.run", run)
    assert compile_tensorrt(tmp_path / "model.onnx", output, executable="trtexec") == output
