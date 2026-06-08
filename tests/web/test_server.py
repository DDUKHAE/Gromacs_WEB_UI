import json
import os
import signal
import io
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def harness_dir(tmp_path):
    (tmp_path / "runs").mkdir()
    return tmp_path


@pytest.fixture
def app(harness_dir):
    from web.server import create_app
    return create_app(harness_dir=harness_dir)


async def test_list_runs_empty(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_runs_with_one_run(app, harness_dir):
    ws = harness_dir / "runs" / "aki_20260608_120000"
    ws.mkdir()
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({
        "last_completed_stage": "env",
        "current_step": 5,
        "pending_warnings": [],
    }))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    item = data[0]
    assert item["run_id"] == "aki_20260608_120000"
    assert item["status"] == "paused"
    assert item["protein"] == "aki"
    assert item["last_completed_stage"] == "env"


async def test_get_run_detail(app, harness_dir):
    ws = harness_dir / "runs" / "aki_20260608_120000"
    ws.mkdir()
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({
        "last_completed_stage": "env",
        "current_step": 5,
        "pending_warnings": [],
    }))
    (ws / "runner.log").write_text("step 1 done\nstep 2 done\n")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/aki_20260608_120000")
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == "aki_20260608_120000"
    assert data["status"] == "paused"
    assert data["log_tail"] == "step 1 done\nstep 2 done\n"


async def test_get_run_not_found(app):
    # valid format but no such directory → 404
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/ghost_20260608_120000")
    assert r.status_code == 404


async def test_get_run_invalid_id(app):
    # invalid format → 400
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/nonexistent")
    assert r.status_code == 400


async def test_create_run_spawns_subprocess(app, harness_dir):
    pdb_content = b"ATOM      1  N   ALA A   1       1.000   1.000   1.000\nEND\n"
    mock_proc = MagicMock()
    mock_proc.pid = 12345

    with patch("web.server.subprocess.Popen", return_value=mock_proc) as mock_popen:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/runs",
                files={"pdb_file": ("1AKI.pdb", io.BytesIO(pdb_content), "application/octet-stream")},
                data={"forcefield": "charmm36", "water": "tip3p", "box_type": "dodecahedron"},
            )
    assert r.status_code == 201
    data = r.json()
    run_id = data["run_id"]
    assert run_id.startswith("aki_")
    assert mock_popen.called
    ws = harness_dir / "runs" / run_id
    assert ws.is_dir()
    assert (ws / "inputs" / "input.pdb").exists()
    assert (ws / "runner.pid").read_text() == "12345"


async def test_abort_run(app, harness_dir):
    ws = harness_dir / "runs" / "aki_20260608_120000"
    ws.mkdir()
    (ws / "runner.pid").write_text(str(os.getpid()))

    with patch("web.server.os.kill") as mock_kill:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/runs/aki_20260608_120000/action", json={"action": "abort"})
    assert r.status_code == 200
    mock_kill.assert_called_once_with(os.getpid(), signal.SIGTERM)


async def test_continue_run_spawns_md(app, harness_dir):
    ws = harness_dir / "runs" / "aki_20260608_120000"
    ws.mkdir()
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({
        "last_completed_stage": "env", "current_step": 5, "pending_warnings": [],
    }))

    mock_proc = MagicMock()
    mock_proc.pid = 99001
    with patch("web.server.subprocess.Popen", return_value=mock_proc):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/runs/aki_20260608_120000/action", json={"action": "continue"})
    assert r.status_code == 200
    assert (ws / "runner.pid").read_text() == "99001"


async def test_action_invalid(app, harness_dir):
    ws = harness_dir / "runs" / "aki_20260608_120000"
    ws.mkdir()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/runs/aki_20260608_120000/action", json={"action": "explode"})
    assert r.status_code == 400
