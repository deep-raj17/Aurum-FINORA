"""Governed TorchScript and ONNX export for FINORA-KD-Q."""

from __future__ import annotations

import copy
import json
import subprocess
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import cast

try:
    import torch
    from torch import Tensor, nn
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Install aurum-finora[kdq] to export FINORA-KD-Q") from exc

from .config import KDQConfig
from .model import FINORAStudentModel, QATActivation, QATLinear


class ExportWrapper(nn.Module):
    def __init__(self, model: FINORAStudentModel) -> None:
        super().__init__()
        self.model = model

    def forward(
        self, time_series: Tensor, text_ids: Tensor, text_mask: Tensor, tabular: Tensor
    ) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        outputs = self.model(time_series, text_ids, text_mask, tabular)
        return (
            outputs["forecast_mean"],
            outputs["forecast_quantiles"],
            outputs["volatility"],
            outputs["sentiment_logits"],
            outputs["risk"],
            outputs["reasoning_embedding"],
            outputs["modality_importance"],
        )


def load_artifact(path: str | Path) -> FINORAStudentModel:
    directory = Path(path)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    config = KDQConfig.model_validate(manifest["model_config"])
    model = FINORAStudentModel(config)
    model.load_state_dict(
        torch.load(directory / "student-state.pt", map_location="cpu", weights_only=True)
    )
    model.eval()
    return model


def example_inputs(config: KDQConfig, batch_size: int = 1) -> tuple[Tensor, ...]:
    return (
        torch.zeros(batch_size, config.sequence_length, config.time_features),
        torch.ones(batch_size, config.max_text_length, dtype=torch.long),
        torch.ones(batch_size, config.max_text_length, dtype=torch.bool),
        torch.zeros(batch_size, config.tabular_features),
    )


def _without_fake_quant(model: FINORAStudentModel) -> FINORAStudentModel:
    prepared = copy.deepcopy(model).cpu().eval()
    for module in prepared.modules():
        if hasattr(module, "disable_observer"):
            cast(Callable[[], None], module.disable_observer)()
        if hasattr(module, "disable_fake_quant"):
            cast(Callable[[], None], module.disable_fake_quant)()
        if isinstance(module, QATActivation):
            module.fake_quant = nn.Identity()
    return prepared


def _replace_qat_linear(module: nn.Module) -> None:
    for name, child in list(module.named_children()):
        if isinstance(child, QATLinear):
            replacement = nn.Linear(
                child.in_features, child.out_features, bias=child.bias is not None
            )
            replacement.weight.data.copy_(child.weight.data)
            if child.bias is not None and replacement.bias is not None:
                replacement.bias.data.copy_(child.bias.data)
            setattr(module, name, replacement)
        else:
            _replace_qat_linear(child)


def export_torchscript(model: FINORAStudentModel, destination: str | Path) -> Path:
    prepared = _without_fake_quant(model)
    _replace_qat_linear(prepared)
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", torch.jit.TracerWarning)
        traced = torch.jit.trace(
            ExportWrapper(prepared), example_inputs(model.config), check_trace=False
        )
    torch.jit.save(traced, output)
    return output


def export_int8_torchscript(model: FINORAStudentModel, destination: str | Path) -> Path:
    """Convert linear layers to dynamic INT8 after QAT and export TorchScript."""
    prepared = _without_fake_quant(model)
    _replace_qat_linear(prepared)
    for name in (
        "forecast_head",
        "quantile_head",
        "volatility_head",
        "sentiment_head",
        "risk_head",
        "report_head",
        "explanation_gate",
    ):
        setattr(
            prepared,
            name,
            torch.ao.quantization.quantize_dynamic(
                getattr(prepared, name), {nn.Linear}, dtype=torch.qint8
            ),
        )
    prepared.tabular_encoder.network = torch.ao.quantization.quantize_dynamic(
        prepared.tabular_encoder.network, {nn.Linear}, dtype=torch.qint8
    )
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", torch.jit.TracerWarning)
        traced = torch.jit.trace(
            ExportWrapper(prepared), example_inputs(model.config), check_trace=False
        )
    torch.jit.save(traced, output)
    return output


def export_onnx(model: FINORAStudentModel, destination: str | Path, opset: int = 17) -> Path:
    prepared = _without_fake_quant(model)
    _replace_qat_linear(prepared)
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        ExportWrapper(prepared),
        example_inputs(model.config),
        output,
        input_names=["time_series", "text_ids", "text_mask", "tabular"],
        output_names=[
            "forecast_mean",
            "forecast_quantiles",
            "volatility",
            "sentiment_logits",
            "risk",
            "reasoning_embedding",
            "modality_importance",
        ],
        dynamic_axes={
            "time_series": {0: "batch"},
            "text_ids": {0: "batch"},
            "text_mask": {0: "batch"},
            "tabular": {0: "batch"},
        },
        opset_version=opset,
        do_constant_folding=True,
    )
    return output


def quantize_onnx_dynamic(source: str | Path, destination: str | Path) -> Path:
    """Apply ONNX Runtime dynamic INT8 weight quantization."""
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic
    except ImportError as exc:
        raise RuntimeError("Install onnxruntime to quantize ONNX artifacts") from exc
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    quantize_dynamic(str(source), str(output), weight_type=QuantType.QInt8)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("ONNX Runtime did not produce a dynamic INT8 artifact")
    return output


def quantize_onnx_static(
    source: str | Path,
    destination: str | Path,
    calibration_data_reader: object,
) -> Path:
    """Apply calibrated QDQ static INT8 quantization."""
    try:
        from onnxruntime.quantization import (
            QuantFormat,
            QuantType,
            quantize_static,
        )
    except ImportError as exc:
        raise RuntimeError("Install onnxruntime to quantize ONNX artifacts") from exc
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    quantize_static(
        str(source),
        str(output),
        calibration_data_reader,
        quant_format=QuantFormat.QDQ,
        activation_type=QuantType.QInt8,
        weight_type=QuantType.QInt8,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("ONNX Runtime did not produce a static INT8 artifact")
    return output


def compile_tensorrt(
    source: str | Path,
    destination: str | Path,
    *,
    precision: str = "fp16",
    workspace_mib: int = 2048,
    executable: str = "trtexec",
) -> Path:
    """Compile ONNX with NVIDIA's supported ``trtexec`` deployment tool."""
    if precision not in {"fp16", "int8", "bf16"}:
        raise ValueError("TensorRT precision must be fp16, bf16, or int8")
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        executable,
        f"--onnx={Path(source)}",
        f"--saveEngine={output}",
        f"--memPoolSize=workspace:{workspace_mib}",
        f"--{precision}",
        "--skipInference",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode or not output.is_file() or output.stat().st_size == 0:
        message = (result.stderr or result.stdout)[-2000:]
        raise RuntimeError(f"TensorRT compilation failed: {message}")
    return output
