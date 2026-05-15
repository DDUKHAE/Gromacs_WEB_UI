import pytest
from lib import validators as V


def test_block_identical_command_reuse():
    history = [{"step": 7, "phase": "npt", "tier": "retryable",
                "cause": "pressure_coupling",
                "command": "gmx mdrun -deffnm npt",
                "parameters": {"tau_p": 2.0}}]
    with pytest.raises(V.RetryContractError):
        V.assert_unique_attempt(history, command="gmx mdrun -deffnm npt",
                                parameters={"tau_p": 2.0})


def test_allow_mutated_attempt():
    history = [{"step": 7, "phase": "npt", "tier": "retryable",
                "cause": "pressure_coupling",
                "command": "gmx mdrun -deffnm npt",
                "parameters": {"tau_p": 2.0}}]
    V.assert_unique_attempt(history, command="gmx mdrun -deffnm npt",
                            parameters={"tau_p": 5.0})


def test_retryable_budget_exhausted():
    history = [
        {"step": 7, "phase": "npt", "tier": "retryable", "cause": "pressure_coupling",
         "command": "x", "parameters": {"a": 1}},
        {"step": 7, "phase": "npt", "tier": "retryable", "cause": "pressure_coupling",
         "command": "x", "parameters": {"a": 2}},
        {"step": 7, "phase": "npt", "tier": "retryable", "cause": "pressure_coupling",
         "command": "x", "parameters": {"a": 3}},
    ]
    assert V.retryable_budget_remaining(history, step=7, phase="npt") == 0


def test_warning_retries_not_counted_against_retryable_budget():
    history = [
        {"step": 7, "phase": "npt", "tier": "warning", "cause": "pressure_coupling",
         "command": "x", "parameters": {"a": 1}},
        {"step": 7, "phase": "npt", "tier": "warning", "cause": "pressure_coupling",
         "command": "x", "parameters": {"a": 2}},
    ]
    assert V.retryable_budget_remaining(history, step=7, phase="npt") == 3
