from datetime import UTC, datetime

import pytest

torch = pytest.importorskip("torch")

from aurum.kdq.teachers import FINORAMoETeacher, TeacherInput  # noqa: E402
from aurum.moe import (  # noqa: E402
    BASELINE_EXPERTS,
    MODALITIES,
    SPECIALIST_EXPERTS,
    AssetClass,
    FINORAMoE,
    FINORAMoEConfig,
    GraphAttentionExpert,
    MarketState,
    RoutingFeatures,
    VolatilityRegime,
)


def config() -> FINORAMoEConfig:
    return FINORAMoEConfig(
        modality_dims=dict.fromkeys(MODALITIES, 4),
        hidden_size=16,
        attention_heads=4,
        forecast_horizon=3,
        explanation_size=8,
        evidence_slots=5,
        router_top_k=2,
        dropout=0,
    )


def test_moe_fuses_modalities_routes_available_experts_and_runs_all_heads() -> None:
    model = FINORAMoE(config()).eval()
    batch = 2
    modalities = {name: torch.randn(batch, 4) for name in MODALITIES}
    modality_availability = torch.ones(batch, len(MODALITIES), dtype=torch.bool)
    modality_availability[0, 4] = False
    experts = torch.randn(batch, len(SPECIALIST_EXPERTS), 16)
    expert_availability = torch.ones(batch, len(SPECIALIST_EXPERTS), dtype=torch.bool)
    expert_availability[0, -1] = False
    context = torch.tensor(
        [
            RoutingFeatures(
                asset_class=AssetClass.EQUITY,
                volatility_regime=VolatilityRegime.HIGH,
                data_availability=0.8,
                market_regime=MarketState.BEAR,
                forecast_horizon=20,
                liquidity_condition=0.7,
                sentiment_strength=0.9,
                macro_shock_state=True,
            ).vector()
        ]
        * batch
    )

    output = model(
        modalities,
        modality_availability,
        experts,
        expert_availability,
        context,
    )

    assert output["return_forecast"].shape == (batch, 3)
    assert output["direction_logits"].shape == (batch, 3, 3)
    assert output["explanation_embedding"].shape == (batch, 8)
    assert output["evidence_logits"].shape == (batch, 5)
    assert torch.all(output["cvar"] >= output["var"])
    assert torch.allclose(output["expert_weights"].sum(dim=-1), torch.ones(batch))
    assert torch.count_nonzero(output["expert_weights"][0]) <= 2
    assert output["expert_weights"][0, -1] == 0
    assert output["modality_attention"][0, 4] == 0


def test_router_and_fusion_fail_closed_when_no_inputs_are_available() -> None:
    model = FINORAMoE(config()).eval()
    batch = 1
    modalities = {name: torch.randn(batch, 4) for name in MODALITIES}
    experts = torch.randn(batch, len(SPECIALIST_EXPERTS), 16)
    context = torch.zeros(batch, 8)
    with pytest.raises(ValueError, match="modality"):
        model(
            modalities,
            torch.zeros(batch, len(MODALITIES), dtype=torch.bool),
            experts,
            torch.ones(batch, len(SPECIALIST_EXPERTS), dtype=torch.bool),
            context,
        )
    with pytest.raises(ValueError, match="expert"):
        model(
            modalities,
            torch.ones(batch, len(MODALITIES), dtype=torch.bool),
            experts,
            torch.zeros(batch, len(SPECIALIST_EXPERTS), dtype=torch.bool),
            context,
        )


def test_graph_attention_and_architecture_manifest() -> None:
    graph = GraphAttentionExpert(5, 16)
    nodes = torch.randn(2, 4, 5)
    adjacency = torch.eye(4).repeat(2, 1, 1)
    assert graph(nodes, adjacency).shape == (2, 16)
    manifest = FINORAMoE(config()).architecture_manifest()
    assert manifest["experts"][0:2] == ["patchtst", "itransformer"]
    assert manifest["baselines"] == [expert.name for expert in BASELINE_EXPERTS]


def test_finora_moe_is_a_valid_kdq_teacher() -> None:
    sample = TeacherInput(
        sample_id="sample",
        timestamp=datetime.now(UTC),
        time_series=[[1.0], [1.1]],
        text="evidence",
        tabular=[0.2],
    )
    teacher = FINORAMoETeacher(
        lambda _: {"mean": 0.02, "quantiles": [-0.01, 0.02, 0.04], "volatility": 0.03},
        "finora-moe-v1",
    )
    assert teacher.predict(sample)["quantiles"] == [-0.01, 0.02, 0.04]
