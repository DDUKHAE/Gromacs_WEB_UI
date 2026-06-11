import subprocess
import threading
import time
from pathlib import Path
import pytest
from unittest.mock import MagicMock
from lib.gmx_wrapper import run as gmx_run, GmxResult


def test_run_without_progress_log_returns_result(tmp_path, monkeypatch):
    """Baseline: existing call signature still works."""
    shim = tmp_path / "gmx"
    shim.write_text("#!/bin/sh\necho gmx version 2024\n")
    shim.chmod(0o755)
    monkeypatch.setenv("GMX_BIN", str(shim))
    result = gmx_run(["--version"], cwd=tmp_path)
    assert result.returncode == 0


def test_run_with_progress_log_writes_output(tmp_path, monkeypatch):
    """When progress_log is set, output is written to the file."""
    log_file = tmp_path / "progress.log"
    import os
    shim = tmp_path / "gmx"
    shim.write_text("#!/bin/sh\necho hello from gmx\n")
    shim.chmod(0o755)
    monkeypatch.setenv("GMX_BIN", str(shim))
    result = gmx_run(["--version"], cwd=tmp_path, progress_log=log_file)
    assert log_file.exists()
    content = log_file.read_text()
    assert "hello from gmx" in content


def make_info(last_stage, current_step, status="running"):
    """Build a minimal run info dict as returned by /api/runs/{id}."""
    return {
        "last_completed_stage": last_stage,
        "current_step": current_step,
        "status": status,
    }


def test_run_summary_includes_current_step():
    """_run_summary must include current_step so the frontend can use it."""
    from web.run_reader import RunInfo
    from pathlib import Path
    from web.server import _run_summary

    info = RunInfo(
        run_id="prot_20260610_120000",
        workspace=Path("/tmp/fake"),
        status="running",
        protein="prot",
        created_at="2026-06-10T12:00:00",
        last_completed_stage=None,
        current_step=3,
        pending_warnings=[],
    )
    summary = _run_summary(info)
    assert summary["current_step"] == 3
    assert "last_completed_stage" in summary


def test_chat_log_filter_removes_gromacs_noise():
    """chat_log endpoint must strip GROMACS output and shell prompts."""
    from fastapi.testclient import TestClient
    from web.server import create_app
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        hd = Path(tmp)
        runs_dir = hd / "runs"
        runs_dir.mkdir()

        ws = runs_dir / "prot_20260610_120000"
        ws.mkdir()
        log = ws / "runner.log"
        log.write_text(
            "I will now build the topology for your protein.\n"
            "$ gmx pdb2gmx -f input.pdb\n"
            ":-)  GROMACS - gmx pdb2gmx, version 2024  (-:\n"
            "NOTE: 3 improper dihedrals found\n"
            "\n"
            "The topology has been created successfully.\n"
            "Allow? [y/n]\n"
        )

        app = create_app(harness_dir=hd)
        client = TestClient(app)
        r = client.get("/api/runs/prot_20260610_120000/chat_log")
        assert r.status_code == 200
        body = r.text
        assert "I will now build the topology" in body
        assert "The topology has been created successfully" in body
        assert "gmx pdb2gmx" not in body
        assert "GROMACS - gmx" not in body
        assert "NOTE: 3 improper" not in body
        assert "Allow?" not in body


def test_patch_run_display_name():
    """PATCH /api/runs/{id} stores display_name in meta.json."""
    from fastapi.testclient import TestClient
    from web.server import create_app
    import tempfile, json
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        hd = Path(tmp)
        ws = hd / "runs" / "prot_20260610_120000"
        ws.mkdir(parents=True)

        app = create_app(harness_dir=hd)
        client = TestClient(app)

        r = client.patch(
            "/api/runs/prot_20260610_120000",
            json={"display_name": "My Favourite Run"},
        )
        assert r.status_code == 200
        assert r.json()["display_name"] == "My Favourite Run"

        meta = json.loads((ws / "meta.json").read_text())
        assert meta["display_name"] == "My Favourite Run"


def test_chat_log_returns_404_for_missing_run():
    """GET /api/runs/{id}/chat_log must return 404 if workspace doesn't exist."""
    from fastapi.testclient import TestClient
    from web.server import create_app
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        hd = Path(tmp)
        (hd / "runs").mkdir()
        app = create_app(harness_dir=hd)
        client = TestClient(app)
        r = client.get("/api/runs/prot_20260610_120000/chat_log")
        assert r.status_code == 404


def test_list_runs_includes_display_name():
    """GET /api/runs returns display_name when set."""
    from fastapi.testclient import TestClient
    from web.server import create_app
    import tempfile, json
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        hd = Path(tmp)
        ws = hd / "runs" / "prot_20260610_120000"
        ws.mkdir(parents=True)
        (ws / "meta.json").write_text(json.dumps({"display_name": "Custom Name"}))

        app = create_app(harness_dir=hd)
        client = TestClient(app)
        r = client.get("/api/runs")
        assert r.status_code == 200
        runs = r.json()
        assert len(runs) == 1
        assert runs[0]["display_name"] == "Custom Name"


def test_audit_endpoint_returns_report():
    """GET /api/runs/{run_id}/audit returns audit report."""
    from fastapi.testclient import TestClient
    from web.server import create_app
    import tempfile, json
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        runs_dir = Path(tmp) / "runs"
        run_id = "protein_20260101_120000"
        ws = runs_dir / run_id
        ws.mkdir(parents=True)
        state = {
            "schema_version": "1.0",
            "workspace_dir": str(ws),
            "current_step": 9,
            "last_completed_stage": "viz",
            "tutorial": {"id": "Lysozyme_in_water", "variant": "protein_aqueous_standard"},
            "hardware": {"ntomp": 4},
            "step_outputs": {
                "step_1": {"forcefield": "charmm36", "water_model": "tip3p"},
                "step_2": {"box_type": "dodecahedron"},
                "step_7": {"phase_sequence": ["em", "nvt", "npt", "production"]},
            },
            "retry_history": [], "pending_warnings": [], "topology_backups": [],
        }
        (ws / "state.json").write_text(json.dumps(state))
        (ws / "meta.json").write_text(json.dumps({"tutorial_id": "Lysozyme_in_water"}))

        app = create_app(harness_dir=Path(tmp))
        client = TestClient(app)
        resp = client.get(f"/api/runs/{run_id}/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tutorial_id"] == "Lysozyme_in_water"
        assert data["passed"] == 4
        assert data["failed"] == 0
