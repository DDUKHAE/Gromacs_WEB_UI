import json

from lib import state
from skills.md_runner import md_runner
from skills.illustrator import illustrator


def _workspace(tmp_path):
    (tmp_path / "stage1_env").mkdir()
    (tmp_path / "stage1_env" / "topol.top").write_text("[ system ]\nunit\n")
    state.write(tmp_path, state.initial(tmp_path))
    return tmp_path


def test_free_energy_workflow_creates_one_directory_per_lambda(tmp_path, monkeypatch):
    ws = _workspace(tmp_path)
    (ws / "inputs.gro").write_text("coordinates\n0\n   1 1 1\n")
    calls = []
    monkeypatch.setattr(md_runner, "_run_local_phase", lambda *args, **kwargs: calls.append(args[1]))
    workflow = {"coordinate": "inputs.gro", "couple_moltype": "MET", "lambda_schedule": [
        {"id": "00", "init_lambda_state": 0, "coul_lambdas": [0.0, 0.0], "vdw_lambdas": [0.0, 1.0]},
        {"id": "01", "init_lambda_state": 1, "coul_lambdas": [0.0, 0.0], "vdw_lambdas": [0.0, 1.0]},
    ]}

    result = md_runner.run_free_energy_workflow(ws, workflow)

    assert result["completed_lambdas"] == ["00", "01"]
    assert calls == ["em", "nvt", "npt", "free_energy"] * 2
    saved = state.read(ws)["step_outputs"]["step_7"]["free_energy_lambdas"]
    assert saved == ["00", "01"]


def test_umbrella_workflow_creates_one_directory_per_window(tmp_path, monkeypatch):
    ws = _workspace(tmp_path)
    (ws / "window_000.gro").write_text("coordinates\n0\n   1 1 1\n")
    (ws / "window_001.gro").write_text("coordinates\n0\n   1 1 1\n")
    (ws / "index.ndx").write_text("[ Chain_A ]\n1\n[ Chain_B ]\n2\n")
    calls = []
    monkeypatch.setattr(md_runner, "_run_local_phase", lambda *args, **kwargs: calls.append(args[1]))
    workflow = {"group1": "Chain_A", "group2": "Chain_B", "index": "index.ndx", "windows": [
        {"id": "000", "coordinate": "window_000.gro"},
        {"id": "001", "coordinate": "window_001.gro"},
    ]}

    result = md_runner.run_umbrella_workflow(ws, workflow)

    assert result["completed_windows"] == ["000", "001"]
    assert calls == ["npt", "umbrella"] * 2


def test_bar_reports_missing_completed_lambda_output(tmp_path):
    ws = _workspace(tmp_path)
    saved = state.read(ws)
    saved["step_outputs"]["step_7"] = {"free_energy_lambdas": ["00"]}
    state.write(ws, saved)

    result = illustrator._run_bar(ws)

    assert result["status"] == "incomplete"
    assert result["missing"] == ["lambda_00/free_energy.edr"]


def test_wham_reports_missing_completed_window_output(tmp_path):
    ws = _workspace(tmp_path)
    saved = state.read(ws)
    saved["step_outputs"]["step_7"] = {"umbrella_windows": ["000"]}
    state.write(ws, saved)

    result = illustrator._run_wham(ws)

    assert result["status"] == "incomplete"
    assert result["missing"] == ["umbrella/window_000/umbrella.tpr", "umbrella/window_000/pullf.xvg"]


def test_local_phase_uses_hardware_thread_count(tmp_path, monkeypatch):
    ws = _workspace(tmp_path)
    saved = state.read(ws)
    saved["hardware"] = {"ntomp": 3}
    state.write(ws, saved)
    source = ws / "source.gro"
    source.write_text("coordinates\n0\n   1 1 1\n")
    commands = []

    class Result:
        ok = True
        classification = "success"
        stderr = ""

    monkeypatch.setattr(md_runner.GW, "run", lambda args, **kwargs: commands.append(args) or Result())
    md_runner._run_local_phase(ws, "em", ws / "phase", source, {})

    assert commands[1] == ["mdrun", "-v", "-deffnm", "em", "-ntomp", "3"]


def test_standard_variant_has_no_stub_summary(tmp_path):
    assert illustrator.run_variant_analyses(tmp_path) == {}
