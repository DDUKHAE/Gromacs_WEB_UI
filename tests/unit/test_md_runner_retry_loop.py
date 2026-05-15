# tests/unit/test_md_runner_retry_loop.py
from pathlib import Path
from unittest.mock import patch
import pytest
from lib import state, validators as V


def _seed_state(ws: Path):
    s = state.initial(ws)
    s["last_completed_stage"] = "env"
    s["hardware"] = {"cpu_count": 4, "gpu_ids": [], "ntomp": 4}
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    for k in ("step_1","step_2","step_3","step_5"):
        s["step_outputs"][k] = {}
    state.write(ws, s)


def test_retryable_loop_mutates_until_success(tmp_workspace: Path):
    from skills.md_runner.md_runner import run_phase_with_recovery
    _seed_state(tmp_workspace)
    call_count = {"n": 0}

    def fake_phase(ws, phase, overrides):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return V.Judgment(tier="retryable", metric="energy_drift",
                              cause="unstable_energy", observed=10.0)
        return V.Judgment(tier="pass", metric="energy_drift", observed=0.0)

    result = run_phase_with_recovery(tmp_workspace, phase="npt",
                                     phase_runner=fake_phase)
    assert result.tier == "pass"
    s = state.read(tmp_workspace)
    assert sum(1 for e in s["retry_history"] if e["tier"] == "retryable") == 2


def test_retryable_exhausts_budget_and_raises(tmp_workspace: Path):
    from skills.md_runner.md_runner import run_phase_with_recovery, PhaseFatal
    _seed_state(tmp_workspace)

    def always_retryable(ws, phase, overrides):
        return V.Judgment(tier="retryable", metric="energy_drift",
                          cause="unstable_energy", observed=10.0)

    with pytest.raises(PhaseFatal):
        run_phase_with_recovery(tmp_workspace, phase="npt",
                                phase_runner=always_retryable)
