from lib import validators as v


def test_neutral_charge_passes():
    assert v.judge_neutrality(0.0).tier == "pass"


def test_small_residual_charge_warns():          # |q| <= 0.1
    assert v.judge_neutrality(0.05).tier == "warning"


def test_moderate_charge_retryable():            # 0.1 < |q| <= 0.5
    assert v.judge_neutrality(0.3).tier == "retryable"


def test_large_charge_fatal():                   # |q| > 0.5
    assert v.judge_neutrality(1.0).tier == "fatal"


def test_temperature_within_tolerance_passes():  # |dT| <= 3 K
    assert v.judge_temperature(300.5, target=300.0).tier == "pass"


def test_temperature_far_off_retryable():        # |dT| > 10 K
    assert v.judge_temperature(315.0, target=300.0).tier == "retryable"


def test_energy_drift_small_passes():            # < 0.5 kJ/mol/ns
    assert v.judge_energy_drift(0.1).tier == "pass"


def test_rmsd_plateau_flat_passes():             # tail-half range <= 0.05 nm
    assert v.judge_rmsd_plateau([0.10, 0.19, 0.20, 0.20, 0.21, 0.20]).tier == "pass"


def test_rmsd_still_climbing_not_pass():
    assert v.judge_rmsd_plateau([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]).tier != "pass"


def test_density_within_range_passes():
    assert v.judge_density(1000.0, (990.0, 1010.0)).tier == "pass"


def test_assert_unique_attempt_raises_on_duplicate():
    history = [{"command": "genion", "parameters": {"-conc": "0.15"}}]
    import pytest
    with pytest.raises(v.RetryContractError):
        v.assert_unique_attempt(history, "genion", {"-conc": "0.15"})
