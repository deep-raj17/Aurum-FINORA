from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.run_rp1_publication_005_robustness import (
    HORIZON,
    canonical_config_hash,
    load_frozen_config,
    make_folds,
    validate_prediction_frame,
)

CONFIG = Path("research/configs/robustness/rp1_publication_005_true_robustness.yaml")


def test_publication_005_config_is_valid_and_hash_is_deterministic() -> None:
    config, first_hash = load_frozen_config(CONFIG)
    assert config["horizon_days"] == HORIZON
    assert first_hash == canonical_config_hash(config)
    assert config["overwrite_policy"] == "forbid"


def test_publication_005_rejects_final_holdout_and_duplicate_predictions() -> None:
    rows = pd.DataFrame(
        {
            "asset": ["SPY", "SPY"],
            "model": ["LightGBM", "LightGBM"],
            "fold_id": ["fold", "fold"],
            "timestamp": ["2025-07-01", "2025-07-01"],
            "target_direction": [0, 0],
            "probability": [0.2, 1.1],
            "prediction": [0, 1],
            "target_return": [0.01, -0.01],
        }
    )

    failures = validate_prediction_frame(rows, final_holdout_start="2025-07-01")

    assert "final_test_boundary_violation" in failures
    assert "duplicate_prediction_rows" in failures
    assert "invalid_probability_range" in failures


def test_publication_005_folds_preserve_purge_and_embargo() -> None:
    frame = pd.DataFrame({"value": range(1_000)})
    folds = make_folds(frame, frequency="monthly_expanding")

    assert folds
    for fold in folds:
        assert fold.train_indices[-1] + HORIZON + 5 < fold.test_indices[0]


def test_publication_005_missing_config_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_frozen_config(tmp_path / "missing.yaml")
