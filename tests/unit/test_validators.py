import pytest
from lib import validators as V


def test_neutrality_pass():
    r = V.judge_neutrality(net_charge=0.0)
    assert r.tier == "pass"


def test_neutrality_warning_small_imbalance():
    r = V.judge_neutrality(net_charge=0.05)
    assert r.tier == "warning"
    assert r.suggested_mutation["target"] == "genion"


def test_neutrality_fatal_large_imbalance():
    r = V.judge_neutrality(net_charge=1.0)
    assert r.tier == "fatal"


def test_density_pass():
    r = V.judge_density(observed=1000.0, expected_range=(995, 1005))
    assert r.tier == "pass"


def test_density_warning_minor_deviation():
    r = V.judge_density(observed=985.0, expected_range=(995, 1005))
    assert r.tier == "warning"
    assert r.metric == "density"
    assert r.suggested_mutation["target"] == "npt.mdp"


def test_density_retryable_severe_deviation():
    r = V.judge_density(observed=500.0, expected_range=(995, 1005))
    assert r.tier == "retryable"


def test_judgment_carries_warning_id_when_warning():
    r = V.judge_density(observed=985.0, expected_range=(995, 1005))
    assert isinstance(r.warning_id, str) and len(r.warning_id) > 0


def test_temperature_pass():
    assert V.judge_temperature(observed=300.5, target=300.0).tier == "pass"


def test_temperature_warning():
    r = V.judge_temperature(observed=305.0, target=300.0)
    assert r.tier == "warning"
    assert r.cause == "temperature_coupling"


def test_temperature_retryable():
    assert V.judge_temperature(observed=350.0, target=300.0).tier == "retryable"


def test_energy_drift_pass():
    assert V.judge_energy_drift(slope_per_ns=-0.05).tier == "pass"


def test_energy_drift_warning():
    r = V.judge_energy_drift(slope_per_ns=0.6)
    assert r.tier == "warning"
    assert r.cause == "unstable_energy"


def test_rmsd_plateau_stable():
    rmsd_series = [0.20, 0.22, 0.21, 0.22, 0.21, 0.22]
    assert V.judge_rmsd_plateau(rmsd_series).tier == "pass"


def test_rmsd_plateau_not_converged():
    rmsd_series = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60]
    r = V.judge_rmsd_plateau(rmsd_series)
    assert r.tier == "warning"
    assert r.cause == "analysis_not_converged"
