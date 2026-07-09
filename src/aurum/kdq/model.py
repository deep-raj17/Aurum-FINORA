"""Compact multimodal transformer with forecast, sentiment, risk and explanation heads."""

from __future__ import annotations

from typing import Any

try:
    import torch
    from torch import Tensor, nn
    from torch.ao.quantization import (
        FakeQuantize,
        MovingAverageMinMaxObserver,
        MovingAveragePerChannelMinMaxObserver,
    )
    from torch.nn import functional
except ImportError as exc:  # pragma: no cover - optional deep dependency
    raise RuntimeError("Install aurum-finora[kdq] to use FINORA-KD-Q") from exc

from .config import KDQConfig


class QATActivation(nn.Module):
    def __init__(self, enabled: bool) -> None:
        super().__init__()
        self.fake_quant = (
            FakeQuantize(
                observer=MovingAverageMinMaxObserver,
                quant_min=-128,
                quant_max=127,
                dtype=torch.qint8,
                qscheme=torch.per_tensor_symmetric,
            )
            if enabled
            else nn.Identity()
        )

    def forward(self, values: Tensor) -> Tensor:
        return self.fake_quant(values)


class QATLinear(nn.Linear):
    """Linear layer with per-channel symmetric fake-INT8 weight quantization."""

    def __init__(
        self, in_features: int, out_features: int, enabled: bool, bias: bool = True
    ) -> None:
        super().__init__(in_features, out_features, bias=bias)
        self.weight_fake_quant = (
            FakeQuantize(
                observer=MovingAveragePerChannelMinMaxObserver,
                quant_min=-127,
                quant_max=127,
                dtype=torch.qint8,
                qscheme=torch.per_channel_symmetric,
                ch_axis=0,
            )
            if enabled
            else nn.Identity()
        )

    def forward(self, values: Tensor) -> Tensor:
        return functional.linear(values, self.weight_fake_quant(self.weight), self.bias)


class TimeSeriesEncoder(nn.Module):
    def __init__(self, config: KDQConfig) -> None:
        super().__init__()
        self.patch = nn.Conv1d(
            config.time_features,
            config.hidden_size,
            kernel_size=config.patch_size,
            stride=config.patch_size,
        )
        layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_size,
            nhead=config.attention_heads,
            dim_feedforward=config.hidden_size * 4,
            dropout=config.dropout,
            batch_first=True,
            norm_first=False,
        )
        self.encoder = nn.TransformerEncoder(layer, config.encoder_layers)
        self.norm = nn.LayerNorm(config.hidden_size)
        self.quant = QATActivation(config.qat_enabled)

    def forward(self, values: Tensor) -> Tensor:
        mean = values.mean(dim=1, keepdim=True)
        std = values.std(dim=1, keepdim=True).clamp_min(1e-6)
        values = (values - mean) / std
        patches = self.patch(values.transpose(1, 2)).transpose(1, 2)
        return self.quant(self.norm(self.encoder(patches).mean(dim=1)))


class TextEncoder(nn.Module):
    position_ids: Tensor

    def __init__(self, config: KDQConfig) -> None:
        super().__init__()
        self.embedding = nn.Embedding(config.vocab_size, config.hidden_size, padding_idx=0)
        self.position = nn.Embedding(config.max_text_length, config.hidden_size)
        self.register_buffer(
            "position_ids",
            torch.arange(config.max_text_length).unsqueeze(0),
            persistent=False,
        )
        layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_size,
            nhead=config.attention_heads,
            dim_feedforward=config.hidden_size * 4,
            dropout=config.dropout,
            batch_first=True,
            norm_first=False,
        )
        self.encoder = nn.TransformerEncoder(layer, config.encoder_layers)
        self.norm = nn.LayerNorm(config.hidden_size)
        self.quant = QATActivation(config.qat_enabled)

    def forward(self, token_ids: Tensor, attention_mask: Tensor) -> Tensor:
        length = token_ids.shape[1]
        positions = self.position_ids[:, :length]
        encoded = self.encoder(
            self.embedding(token_ids) + self.position(positions),
            src_key_padding_mask=~attention_mask.bool(),
        )
        mask = attention_mask.unsqueeze(-1).float()
        pooled = (encoded * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)
        return self.quant(self.norm(pooled))


class TabularEncoder(nn.Module):
    def __init__(self, config: KDQConfig) -> None:
        super().__init__()
        self.network = nn.Sequential(
            QATLinear(
                config.tabular_features,
                config.hidden_size * 2,
                config.qat_enabled,
            ),
            nn.BatchNorm1d(config.hidden_size * 2),
            nn.GELU(),
            nn.Dropout(config.dropout),
            QATLinear(
                config.hidden_size * 2,
                config.hidden_size,
                config.qat_enabled,
            ),
            nn.LayerNorm(config.hidden_size),
            QATActivation(config.qat_enabled),
        )

    def forward(self, values: Tensor) -> Tensor:
        return self.network(values)


class FINORAStudentModel(nn.Module):
    """FINORA-KD-Q student. Inputs are already normalized/tokenized and auditable."""

    def __init__(self, config: KDQConfig) -> None:
        super().__init__()
        self.config = config
        self.time_encoder = TimeSeriesEncoder(config)
        self.text_encoder = TextEncoder(config)
        self.tabular_encoder = TabularEncoder(config)
        fusion_layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_size,
            nhead=config.attention_heads,
            dim_feedforward=config.hidden_size * 4,
            dropout=config.dropout,
            batch_first=True,
            norm_first=False,
        )
        self.fusion = nn.TransformerEncoder(fusion_layer, config.encoder_layers)
        self.fusion_norm = nn.LayerNorm(config.hidden_size)
        self.forecast_head = QATLinear(config.hidden_size, 1, config.qat_enabled)
        self.quantile_head = QATLinear(
            config.hidden_size, len(config.quantiles), config.qat_enabled
        )
        self.volatility_head = QATLinear(config.hidden_size, 1, config.qat_enabled)
        self.sentiment_head = QATLinear(
            config.hidden_size, config.sentiment_classes, config.qat_enabled
        )
        self.risk_head = QATLinear(config.hidden_size, 3, config.qat_enabled)
        self.report_head = QATLinear(config.hidden_size, config.reasoning_size, config.qat_enabled)
        self.explanation_gate = QATLinear(config.hidden_size, 3, config.qat_enabled)
        self.softplus = nn.Softplus()

    def forward(
        self,
        time_series: Tensor,
        text_ids: Tensor,
        text_mask: Tensor,
        tabular: Tensor,
    ) -> dict[str, Tensor]:
        modalities = torch.stack(
            (
                self.time_encoder(time_series),
                self.text_encoder(text_ids, text_mask),
                self.tabular_encoder(tabular),
            ),
            dim=1,
        )
        fused_tokens = self.fusion(modalities)
        gates = torch.softmax(self.explanation_gate(fused_tokens.mean(dim=1)), dim=-1)
        fused = self.fusion_norm((fused_tokens * gates.unsqueeze(-1)).sum(dim=1))
        quantiles = torch.sort(self.quantile_head(fused), dim=-1).values
        risk_raw = self.risk_head(fused)
        return {
            "forecast_mean": self.forecast_head(fused).squeeze(-1),
            "forecast_quantiles": quantiles,
            "volatility": self.softplus(self.volatility_head(fused)).squeeze(-1),
            "sentiment_logits": self.sentiment_head(fused),
            "risk": torch.stack(
                (
                    self.softplus(risk_raw[:, 0]),
                    self.softplus(risk_raw[:, 1]),
                    torch.sigmoid(risk_raw[:, 2]),
                ),
                dim=-1,
            ),
            "reasoning_embedding": self.report_head(fused),
            "modality_importance": gates,
        }

    def parameter_summary(self) -> dict[str, Any]:
        total = sum(parameter.numel() for parameter in self.parameters())
        trainable = sum(
            parameter.numel() for parameter in self.parameters() if parameter.requires_grad
        )
        return {
            "model": self.config.model_name,
            "parameters": total,
            "trainable_parameters": trainable,
            "qat_enabled": self.config.qat_enabled,
        }
