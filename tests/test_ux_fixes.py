import pytest
from unittest.mock import MagicMock


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
            "Allow? [y/n] y\n"
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
