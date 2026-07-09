"""FINORA-MoE multimodal fusion, contextual routing, and prediction heads.

Specialist runtimes produce same-width embeddings before entering this module.
Keeping execution adapters outside the trainable fusion core lets unavailable
optional models fail closed and keeps the router independently exportable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import log1p
from typing import Any

from pydantic import BaseModel, Field

try:
    import torch
    from torch import Tensor, nn
except ImportError as exc:  # pragma: no cover - optional deep dependency
    raise RuntimeError("Install aurum-finora[deep] to use FINORA-MoE") from exc


class ExpertRole(StrEnum):
    PRIMARY = "primary-forecasting"
    MULTI_HORIZON = "multi-horizon"
    FOUNDATION = "foundation"
    TABULAR = "tabular-alpha-risk"
    TEXT = "textual-intelligence"
    GRAPH = "graph-intelligence"
    BASELINE = "baseline-only"


@dataclass(frozen=True)
class ExpertSpec:
    name: str
    role: ExpertRole
    implementation: str
    default_router_member: bool = True


SPECIALIST_EXPERTS = (
    ExpertSpec("patchtst", ExpertRole.PRIMARY, "NeuralForecast PatchTST"),
    ExpertSpec("itransformer", ExpertRole.PRIMARY, "NeuralForecast iTransformer"),
    ExpertSpec("tft", ExpertRole.MULTI_HORIZON, "NeuralForecast TFT"),
    ExpertSpec("tide", ExpertRole.MULTI_HORIZON, "NeuralForecast TiDE"),
    ExpertSpec("chronos", ExpertRole.FOUNDATION, "Amazon Chronos"),
    ExpertSpec("lightgbm", ExpertRole.TABULAR, "LightGBM"),
    ExpertSpec("xgboost", ExpertRole.TABULAR, "XGBoost"),
    ExpertSpec("catboost", ExpertRole.TABULAR, "CatBoost"),
    ExpertSpec("finbert", ExpertRole.TEXT, "FinBERT"),
    ExpertSpec("graph_attention", ExpertRole.GRAPH, "Graph Attention Network"),
)

BASELINE_EXPERTS = (
    ExpertSpec("lstm", ExpertRole.BASELINE, "LSTM", False),
    ExpertSpec("gru", ExpertRole.BASELINE, "GRU", False),
    ExpertSpec("vanilla_rnn", ExpertRole.BASELINE, "Vanilla RNN", False),
    ExpertSpec("simple_transformer", ExpertRole.BASELINE, "Simple Transformer", False),
)

MODALITIES = (
    "ohlcv",
    "technical",
    "macro",
    "sentiment",
    "filing_news",
    "graph",
    "risk",
    "regime",
)


class AssetClass(StrEnum):
    EQUITY = "equity"
    FIXED_INCOME = "fixed-income"
    FX = "fx"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    MULTI_ASSET = "multi-asset"


class VolatilityRegime(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRISIS = "crisis"


class MarketState(StrEnum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    STRESS = "stress"


class RoutingFeatures(BaseModel):
    """Auditable router context converted to a stable eight-feature vector."""

    asset_class: AssetClass
    volatility_regime: VolatilityRegime
    data_availability: float = Field(ge=0, le=1)
    market_regime: MarketState
    forecast_horizon: int = Field(ge=1, le=252)
    liquidity_condition: float = Field(ge=0, le=1)
    sentiment_strength: float = Field(ge=0, le=1)
    macro_shock_state: bool = False

    def vector(self) -> list[float]:
        asset = list(AssetClass).index(self.asset_class) / (len(AssetClass) - 1)
        volatility = list(VolatilityRegime).index(self.volatility_regime) / (
            len(VolatilityRegime) - 1
        )
        market = list(MarketState).index(self.market_regime) / (len(MarketState) - 1)
        return [
            asset,
            volatility,
            self.data_availability,
            market,
            log1p(self.forecast_horizon) / log1p(252),
            self.liquidity_condition,
            self.sentiment_strength,
            float(self.macro_shock_state),
        ]


@dataclass(frozen=True)
class FINORAMoEConfig:
    modality_dims: dict[str, int]
    hidden_size: int = 128
    attention_heads: int = 4
    forecast_horizon: int = 1
    direction_classes: int = 3
    regime_classes: int = 5
    scenario_classes: int = 3
    explanation_size: int = 64
    evidence_slots: int = 16
    router_top_k: int = 3
    dropout: float = 0.1
    expert_names: tuple[str, ...] = field(
        default_factory=lambda: tuple(expert.name for expert in SPECIALIST_EXPERTS)
    )

    def __post_init__(self) -> None:
        missing = set(MODALITIES) - set(self.modality_dims)
        if missing:
            raise ValueError(f"missing modality dimensions: {sorted(missing)}")
        if self.hidden_size % self.attention_heads:
            raise ValueError("hidden_size must be divisible by attention_heads")
        if not 1 <= self.router_top_k <= len(self.expert_names):
            raise ValueError("router_top_k must be between one and the expert count")
        if self.forecast_horizon < 1:
            raise ValueError("forecast_horizon must be positive")


class CrossAttentionFusion(nn.Module):
    """Cross-attend a learned decision query over the eight modality tokens."""

    def __init__(self, config: FINORAMoEConfig) -> None:
        super().__init__()
        self.config = config
        self.projections = nn.ModuleDict(
            {name: nn.Linear(config.modality_dims[name], config.hidden_size) for name in MODALITIES}
        )
        self.modality_embedding = nn.Parameter(torch.empty(len(MODALITIES), config.hidden_size))
        self.query = nn.Parameter(torch.empty(1, 1, config.hidden_size))
        self.attention = nn.MultiheadAttention(
            config.hidden_size,
            config.attention_heads,
            dropout=config.dropout,
            batch_first=True,
        )
        self.norm = nn.LayerNorm(config.hidden_size)
        nn.init.normal_(self.modality_embedding, std=0.02)
        nn.init.normal_(self.query, std=0.02)

    def forward(self, modalities: dict[str, Tensor], availability: Tensor) -> tuple[Tensor, Tensor]:
        if availability.ndim != 2 or availability.shape[1] != len(MODALITIES):
            raise ValueError(f"availability must have shape [batch, {len(MODALITIES)}]")
        if torch.any(~availability.bool().any(dim=1)):
            raise ValueError("each sample requires at least one available modality")
        tokens = []
        for index, name in enumerate(MODALITIES):
            if name not in modalities:
                raise ValueError(f"missing modality tensor: {name}")
            value = modalities[name]
            if value.ndim == 3:
                value = value.mean(dim=1)
            if value.ndim != 2:
                raise ValueError(
                    f"{name} must have shape [batch, features] or [batch, time, features]"
                )
            tokens.append(self.projections[name](value) + self.modality_embedding[index])
        encoded = torch.stack(tokens, dim=1)
        query = self.query.expand(encoded.shape[0], -1, -1)
        fused, weights = self.attention(
            query,
            encoded,
            encoded,
            key_padding_mask=~availability.bool(),
            need_weights=True,
        )
        return self.norm(fused.squeeze(1)), weights.squeeze(1)


class MoERouter(nn.Module):
    """Sparse contextual router with hard availability masking."""

    def __init__(self, config: FINORAMoEConfig) -> None:
        super().__init__()
        self.top_k = config.router_top_k
        self.network = nn.Sequential(
            nn.Linear(config.hidden_size + 8, config.hidden_size),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_size, len(config.expert_names)),
        )

    def forward(
        self, fused: Tensor, context: Tensor, expert_availability: Tensor
    ) -> tuple[Tensor, Tensor]:
        if context.ndim != 2 or context.shape[1] != 8:
            raise ValueError("router context must have shape [batch, 8]")
        available = expert_availability.bool()
        if available.shape[0] != fused.shape[0] or torch.any(~available.any(dim=1)):
            raise ValueError("each sample requires at least one available expert")
        logits = self.network(torch.cat((fused, context), dim=-1))
        logits = logits.masked_fill(~available, torch.finfo(logits.dtype).min)
        k = min(self.top_k, logits.shape[-1])
        top_values, top_indices = torch.topk(logits, k=k, dim=-1)
        sparse_logits = torch.full_like(logits, torch.finfo(logits.dtype).min)
        sparse_logits.scatter_(1, top_indices, top_values)
        weights = torch.softmax(sparse_logits, dim=-1)
        importance = weights.mean(dim=0)
        usage = (weights > 0).float().mean(dim=0)
        balance_loss = weights.shape[1] * torch.sum(importance * usage)
        return weights, balance_loss


class GraphAttentionExpert(nn.Module):
    """Dependency-light graph attention encoder for entity/contagion embeddings."""

    def __init__(self, input_size: int, hidden_size: int) -> None:
        super().__init__()
        self.node = nn.Linear(input_size, hidden_size, bias=False)
        self.source = nn.Linear(hidden_size, 1, bias=False)
        self.target = nn.Linear(hidden_size, 1, bias=False)
        self.activation = nn.LeakyReLU(0.2)

    def forward(self, nodes: Tensor, adjacency: Tensor) -> Tensor:
        if nodes.ndim != 3 or adjacency.shape != nodes.shape[:2] + (nodes.shape[1],):
            raise ValueError(
                "nodes must be [batch,nodes,features] and adjacency [batch,nodes,nodes]"
            )
        encoded = self.node(nodes)
        scores = self.activation(self.source(encoded) + self.target(encoded).transpose(1, 2))
        identity = torch.eye(nodes.shape[1], device=nodes.device, dtype=torch.bool).unsqueeze(0)
        mask = adjacency.bool() | identity
        attention = torch.softmax(scores.masked_fill(~mask, torch.finfo(scores.dtype).min), dim=-1)
        return torch.bmm(attention, encoded).mean(dim=1)


class PredictionHeads(nn.Module):
    def __init__(self, config: FINORAMoEConfig) -> None:
        super().__init__()
        hidden = config.hidden_size
        horizon = config.forecast_horizon
        self.horizon = horizon
        self.direction_classes = config.direction_classes
        self.return_head = nn.Linear(hidden, horizon)
        self.direction_head = nn.Linear(hidden, horizon * config.direction_classes)
        self.volatility_head = nn.Linear(hidden, horizon)
        self.risk_head = nn.Linear(hidden, 1)
        self.tail_head = nn.Linear(hidden, 2)
        self.drawdown_head = nn.Linear(hidden, 1)
        self.regime_head = nn.Linear(hidden, config.regime_classes)
        self.scenario_head = nn.Linear(hidden, config.scenario_classes)
        self.explanation_head = nn.Linear(hidden, config.explanation_size)
        self.evidence_head = nn.Linear(hidden, config.evidence_slots)
        self.softplus = nn.Softplus()

    def forward(self, hidden: Tensor) -> dict[str, Tensor]:
        tail = self.softplus(self.tail_head(hidden))
        var = tail[:, :1]
        cvar = var + tail[:, 1:2]
        return {
            "return_forecast": self.return_head(hidden),
            "direction_logits": self.direction_head(hidden).view(
                -1, self.horizon, self.direction_classes
            ),
            "volatility_forecast": self.softplus(self.volatility_head(hidden)),
            "risk_forecast": self.softplus(self.risk_head(hidden)),
            "var": var,
            "cvar": cvar,
            "drawdown_probability": torch.sigmoid(self.drawdown_head(hidden)),
            "regime_logits": self.regime_head(hidden),
            "scenario_logits": self.scenario_head(hidden),
            "explanation_embedding": self.explanation_head(hidden),
            "evidence_logits": self.evidence_head(hidden),
        }


class FINORAMoE(nn.Module):
    """Trainable fusion/router core; specialist inference remains pluggable."""

    def __init__(self, config: FINORAMoEConfig) -> None:
        super().__init__()
        self.config = config
        self.fusion = CrossAttentionFusion(config)
        self.router = MoERouter(config)
        self.decision = nn.Sequential(
            nn.Linear(config.hidden_size * 2, config.hidden_size),
            nn.GELU(),
            nn.LayerNorm(config.hidden_size),
        )
        self.heads = PredictionHeads(config)

    def forward(
        self,
        modalities: dict[str, Tensor],
        modality_availability: Tensor,
        expert_embeddings: Tensor,
        expert_availability: Tensor,
        routing_context: Tensor,
    ) -> dict[str, Tensor]:
        expected = (len(self.config.expert_names), self.config.hidden_size)
        if expert_embeddings.ndim != 3 or expert_embeddings.shape[1:] != expected:
            raise ValueError(
                f"expert_embeddings must have shape [batch, {expected[0]}, {expected[1]}]"
            )
        fused, modality_weights = self.fusion(modalities, modality_availability)
        expert_weights, balance_loss = self.router(fused, routing_context, expert_availability)
        mixture = torch.sum(expert_embeddings * expert_weights.unsqueeze(-1), dim=1)
        hidden = self.decision(torch.cat((fused, mixture), dim=-1))
        return {
            **self.heads(hidden),
            "expert_weights": expert_weights,
            "modality_attention": modality_weights,
            "router_balance_loss": balance_loss,
            "decision_embedding": hidden,
        }

    def architecture_manifest(self) -> dict[str, Any]:
        return {
            "model": "FINORA-MoE",
            "modalities": list(MODALITIES),
            "experts": list(self.config.expert_names),
            "baselines": [expert.name for expert in BASELINE_EXPERTS],
            "router_top_k": self.config.router_top_k,
            "forecast_horizon": self.config.forecast_horizon,
        }
