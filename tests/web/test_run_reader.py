import json
import os
from pathlib import Path
import pytest
from web.run_reader import derive_status, read_run, list_runs, RunInfo


def _make_ws(tmp_path, run_id="aki_20260608_120000"):
    ws = tmp_path / "runs" / run_id
    ws.mkdir(parents=True)
    return ws


def test_pending_when_no_pid(tmp_path):
    ws = _make_ws(tmp_path)
    assert derive_status(ws) == "pending"


def test_running_when_pid_alive(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text(str(os.getpid()))
    assert derive_status(ws) == "running"


def test_aborted_when_pid_dead_no_exit(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text("999999999")
    assert derive_status(ws) == "aborted"


def test_failed_when_nonzero_exit(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("1")
    assert derive_status(ws) == "failed"


def test_paused_after_env(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({"last_completed_stage": "env", "current_step": 5, "pending_warnings": []}))
    assert derive_status(ws) == "paused"


def test_paused_after_md(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({"last_completed_stage": "md", "current_step": 7, "pending_warnings": []}))
    assert derive_status(ws) == "paused"


def test_completed_after_viz(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({"last_completed_stage": "viz", "current_step": 8, "pending_warnings": []}))
    assert derive_status(ws) == "completed"


def test_read_run_parses_protein_and_date(tmp_path):
    ws = _make_ws(tmp_path, "aki_20260608_120000")
    (ws / "state.json").write_text(json.dumps({"last_completed_stage": None, "current_step": 0, "pending_warnings": []}))
    info = read_run("aki_20260608_120000", tmp_path / "runs")
    assert info is not None
    assert info.protein == "aki"
    assert info.created_at == "2026-06-08T12:00:00"
    assert info.run_id == "aki_20260608_120000"


def test_list_runs_returns_newest_first(tmp_path):
    runs_dir = tmp_path / "runs"
    for rid in ["aki_20260608_100000", "aki_20260608_120000"]:
        ws = runs_dir / rid
        ws.mkdir(parents=True)
    infos = list_runs(runs_dir)
    assert [i.run_id for i in infos] == ["aki_20260608_120000", "aki_20260608_100000"]
