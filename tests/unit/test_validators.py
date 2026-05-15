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
