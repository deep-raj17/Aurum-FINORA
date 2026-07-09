from datetime import UTC, datetime
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from aurum.kdq.config import KDQConfig, TrainingConfig  # noqa: E402
from aurum.kdq.data import (  # noqa: E402
    build_distilled_sample,
    read_jsonl,
    stable_tokenize,
    synthetic_teacher_inputs,
    write_jsonl,
)
from aurum.kdq.export import (  # noqa: E402
    export_int8_torchscript,
    export_onnx,
    export_torchscript,
)
from aurum.kdq.inference import KDQInferenceRequest, KDQPredictor  # noqa: E402
from aurum.kdq.losses import distillation_loss  # noqa: E402
from aurum.kdq.model import FINORAStudentModel  # noqa: E402
from aurum.kdq.teachers import (  # noqa: E402
    CallableTeacher,
    FinBERTTeacher,
    ForecastEnsembleTeacher,
    GPTOSSFeatureTeacher,
    TeacherEnsemble,
    TeacherInput,
    TrainedRiskTeacher,
)
from aurum.kdq.training import DistillationDataset, train_student  # noqa: E402


def small_config() -> KDQConfig:
    return KDQConfig(
        time_features=3,
        tabular_features=4,
        vocab_size=256,
        max_text_length=16,
        sequence_length=16,
        patch_size=4,
        hidden_size=32,
        reasoning_size=16,
        attention_heads=4,
        encoder_layers=1,
        qat_enabled=True,
    )


def samples(count: int = 12):
    config = small_config()
    ensemble = TeacherEnsemble(reasoning_size=config.reasoning_size, allow_offline_baselines=True)
    return [
        build_distilled_sample(
            raw,
            target_return=target,
            target_volatility=volatility,
            ensemble=ensemble,
            config=config,
        )
        for raw, target, volatility in synthetic_teacher_inputs(config, count=count)
    ]


def test_teacher_labels_and_tokenization_are_reproducible() -> None:
    first = samples(1)[0]
    assert sum(first.soft_labels.sentiment_probs) == pytest.approx(1)
    assert first.soft_labels.forecast_quantiles == sorted(first.soft_labels.forecast_quantiles)
    assert stable_tokenize("profit growth", 256, 8) == stable_tokenize("profit growth", 256, 8)
    assert first.soft_labels.teacher_versions["forecast"]


def test_production_teacher_ensemble_requires_explicit_models() -> None:
    with pytest.raises(ValueError, match="explicit teachers"):
        TeacherEnsemble()


def test_production_teacher_adapters_validate_outputs() -> None:
    class Analyzer:
        def analyse(self, text):
            from aurum.sentiment import SentimentResult

            return SentimentResult(
                label="Positive",
                probability=0.8,
                positive_hits=[],
                negative_hits=[],
                model="finbert",
            )

    class Risk:
        def predict(self, values):
            return [[0.1, 0.2, 1.4]]

    sample = TeacherInput(
        sample_id="sample",
        timestamp=datetime.now(UTC),
        time_series=[[1.0], [2.0]],
        text="growth",
        tabular=[1.0, 2.0],
    )
    assert FinBERTTeacher(Analyzer()).predict(sample) == pytest.approx([0.1, 0.1, 0.8])
    assert TrainedRiskTeacher(Risk(), "risk-v1").predict(sample) == [0.1, 0.2, 1.0]
    embedding = GPTOSSFeatureTeacher(lambda **kwargs: [3.0, 4.0], "gpt-oss").embed(sample, 2)
    assert embedding == pytest.approx([0.6, 0.8])


def test_distilled_jsonl_roundtrip_and_shape_guards(tmp_path) -> None:
    rows = samples(3)
    path = tmp_path / "dataset.jsonl"
    assert len(write_jsonl(rows, path)) == 64
    assert read_jsonl(path) == rows
    path.write_text(
        "\n".join(row.model_dump_json() for row in reversed(rows)) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="chronologically"):
        read_jsonl(path)
    config = small_config()
    ensemble = TeacherEnsemble(reasoning_size=config.reasoning_size, allow_offline_baselines=True)
    raw, target, volatility = synthetic_teacher_inputs(config, 1)[0]
    with pytest.raises(ValueError, match="length"):
        build_distilled_sample(
            raw.model_copy(update={"time_series": raw.time_series[:-1]}),
            target_return=target,
            target_volatility=volatility,
            ensemble=ensemble,
            config=config,
        )
    with pytest.raises(ValueError, match="tabular"):
        build_distilled_sample(
            raw.model_copy(update={"tabular": raw.tabular[:-1]}),
            target_return=target,
            target_volatility=volatility,
            ensemble=ensemble,
            config=config,
        )


def test_forecast_and_callable_teacher_adapters() -> None:
    class Engine:
        def forecast(self, levels, dates, horizon):
            from types import SimpleNamespace

            from aurum.forecast_system import ForecastDistribution

            distribution = ForecastDistribution(
                model="ensemble",
                mean=torch.tensor([0.2]).numpy(),
                quantiles={
                    0.1: torch.tensor([0.1]).numpy(),
                    0.5: torch.tensor([0.2]).numpy(),
                    0.9: torch.tensor([0.3]).numpy(),
                },
                metadata={},
            )
            return distribution, [SimpleNamespace(rmse=0.05)]

    sample = TeacherInput(
        sample_id="sample",
        timestamp=datetime.now(UTC),
        time_series=[[1.0], [1.1], [1.2]],
        text="growth",
        tabular=[1],
    )
    output = ForecastEnsembleTeacher(Engine(), "forecast-v1").predict(sample)
    assert output == {
        "mean": pytest.approx(0.2),
        "quantiles": pytest.approx([0.1, 0.2, 0.3]),
        "volatility": pytest.approx(0.05),
    }
    callable_teacher = CallableTeacher(lambda value: [0.6, 0.8], "callable")
    assert callable_teacher.embed(sample, 2) == [0.6, 0.8]
    with pytest.raises(ValueError, match="dimensions"):
        callable_teacher.embed(sample, 3)


def test_student_multitask_loss_backpropagates() -> None:
    config = small_config()
    model = FINORAStudentModel(config)
    raw = DistillationDataset(samples(2))
    batch = {key: torch.stack([raw[0][key], raw[1][key]]) for key in raw[0]}
    outputs = model(
        batch["time_series"],
        batch["text_ids"],
        batch["text_mask"],
        batch["tabular"],
    )
    loss, components = distillation_loss(
        outputs,
        batch,
        quantiles=config.quantiles,
        temperature=2,
        weights=TrainingConfig().weights,
    )
    loss.backward()
    assert torch.isfinite(loss)
    assert set(components) == {
        "forecast",
        "forecast_kd",
        "quantile_kd",
        "sentiment_kd",
        "risk_kd",
        "uncertainty",
        "volatility",
        "calibration",
        "reasoning",
    }
    assert outputs["forecast_quantiles"].shape == (2, 3)
    assert torch.allclose(outputs["modality_importance"].sum(dim=-1), torch.ones(2))


def test_fp32_torchscript_export(tmp_path) -> None:
    output = export_torchscript(
        FINORAStudentModel(small_config()).eval(), tmp_path / "model-fp32.pt"
    )
    assert output.stat().st_size > 0


def test_training_artifact_inference_and_int8_export(tmp_path: Path) -> None:
    config = small_config()
    result = train_student(
        samples(),
        config,
        TrainingConfig(
            epochs=1,
            batch_size=4,
            mixed_precision=False,
            output_dir=str(tmp_path / "artifact"),
        ),
    )
    assert (result.artifact_dir / "manifest.json").exists()
    predictor = KDQPredictor(result.artifact_dir)
    sample = samples(1)[0]
    prediction = predictor.predict(
        KDQInferenceRequest(
            time_series=sample.time_series,
            text="strong profit growth",
            tabular=sample.tabular,
        )
    )
    assert sum(prediction.sentiment_probabilities) == pytest.approx(1)
    assert sum(prediction.modality_importance.values()) == pytest.approx(1)
    exported = export_int8_torchscript(result.model, tmp_path / "finora-kdq-int8.pt")
    assert exported.stat().st_size > 0
    onnx = pytest.importorskip("onnx")
    onnx_path = export_onnx(result.model, tmp_path / "finora-kdq.onnx")
    onnx.checker.check_model(onnx.load(onnx_path))
