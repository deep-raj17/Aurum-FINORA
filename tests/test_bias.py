import pytest

from aurum.bias import BiasObservation, evaluate_bias


def test_bias_evaluation_compares_adequately_sized_slices() -> None:
    rows = [
        BiasObservation(
            slice_name="asset_class",
            slice_value=group,
            actual=float(index),
            prediction=float(index) + error,
            lower=float(index) - 1,
            upper=float(index) + 1,
        )
        for group, error in (("equity", 0.1), ("forex", 0.2))
        for index in range(25)
    ]
    report = evaluate_bias(rows)
    assert report.passed
    assert set(report.slices) == {"asset_class=equity", "asset_class=forex"}


def test_bias_evaluation_fails_when_slices_are_underpowered() -> None:
    row = BiasObservation(
        slice_name="region",
        slice_value="small",
        actual=1,
        prediction=1,
        lower=0,
        upper=2,
    )
    report = evaluate_bias([row])
    assert not report.passed and report.warnings
    with pytest.raises(ValueError, match="requires"):
        evaluate_bias([])
