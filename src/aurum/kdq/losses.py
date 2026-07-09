"""Multi-task knowledge-distillation and calibration objectives."""

from __future__ import annotations

try:
    import torch
    import torch.nn.functional as functional
    from torch import Tensor
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Install aurum-finora[kdq] to train FINORA-KD-Q") from exc

from .config import LossWeights


def pinball_loss(predictions: Tensor, targets: Tensor, quantiles: Tensor) -> Tensor:
    errors = targets.unsqueeze(-1) - predictions
    return torch.maximum((quantiles - 1) * errors, quantiles * errors).mean()


def calibration_loss(predictions: Tensor, targets: Tensor) -> Tensor:
    lower, upper = predictions[:, 0], predictions[:, -1]
    below = torch.sigmoid(20 * (lower - targets)).mean()
    above = torch.sigmoid(20 * (targets - upper)).mean()
    desired_tail = 0.1
    return (below - desired_tail).square() + (above - desired_tail).square()


def distillation_loss(
    outputs: dict[str, Tensor],
    batch: dict[str, Tensor],
    *,
    quantiles: list[float],
    temperature: float,
    weights: LossWeights,
) -> tuple[Tensor, dict[str, Tensor]]:
    target = batch["target_return"]
    teacher_forecast = batch["teacher_forecast"]
    forecast = functional.mse_loss(outputs["forecast_mean"], target)
    forecast_kd = functional.mse_loss(outputs["forecast_mean"], teacher_forecast)
    quantile_kd = functional.mse_loss(outputs["forecast_quantiles"], batch["teacher_quantiles"])
    sentiment_kd = (
        functional.kl_div(
            functional.log_softmax(outputs["sentiment_logits"] / temperature, dim=-1),
            batch["teacher_sentiment"],
            reduction="batchmean",
        )
        * temperature**2
    )
    risk_kd = functional.mse_loss(outputs["risk"], batch["teacher_risk"])
    uncertainty = pinball_loss(
        outputs["forecast_quantiles"],
        target,
        torch.tensor(quantiles, device=target.device),
    )
    volatility = functional.mse_loss(outputs["volatility"], batch["target_volatility"])
    calibration = calibration_loss(outputs["forecast_quantiles"], target)
    reasoning = (
        1
        - functional.cosine_similarity(
            outputs["reasoning_embedding"], batch["teacher_reasoning"], dim=-1
        ).mean()
    )
    components = {
        "forecast": forecast,
        "forecast_kd": forecast_kd,
        "quantile_kd": quantile_kd,
        "sentiment_kd": sentiment_kd,
        "risk_kd": risk_kd,
        "uncertainty": uncertainty,
        "volatility": volatility,
        "calibration": calibration,
        "reasoning": reasoning,
    }
    total = (
        weights.forecast * forecast
        + weights.forecast_distillation * forecast_kd
        + weights.quantile_distillation * quantile_kd
        + weights.sentiment_distillation * sentiment_kd
        + weights.risk_distillation * risk_kd
        + weights.uncertainty * uncertainty
        + weights.volatility * volatility
        + weights.calibration * calibration
        + weights.reasoning * reasoning
    )
    return total, components
