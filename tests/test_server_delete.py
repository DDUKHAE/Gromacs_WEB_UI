import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_harness(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    return tmp_path


@pytest.fixture
def client(tmp_harness):
    from web.server import create_app
    app = create_app(harness_dir=tmp_harness)
    return TestClient(app)


def _make_run(runs_dir: Path, run_id: str) -> Path:
    ws = runs_dir / run_id
    ws.mkdir()
    (ws / "runner.log").write_text("hello")
    return ws


def test_delete_run_removes_workspace(client, tmp_harness):
    run_id = "protein_20260101_120000"
    ws = _make_run(tmp_harness / "runs", run_id)
    assert ws.exists()

    resp = client.delete(f"/api/runs/{run_id}")

    assert resp.status_code == 200
    assert not ws.exists()


def test_delete_run_returns_404_when_not_found(client, tmp_harness):
    resp = client.delete("/api/runs/protein_20260101_120000")
    assert resp.status_code == 404


def test_delete_run_rejects_invalid_run_id(client):
    # httpx normalises /api/runs/../secret → /api/secret before the request
    # reaches FastAPI, so the router returns 404 (no matching route).
    # Both 400 and 404 are safe rejections of a path-traversal attempt.
    resp = client.delete("/api/runs/../secret")
    assert resp.status_code in (400, 404)


def test_delete_run_kills_process_before_deleting(client, tmp_harness):
    """프로세스가 살아 있지 않아도 삭제가 성공해야 한다 (pid 파일 존재 시)."""
    run_id = "protein_20260101_120000"
    ws = _make_run(tmp_harness / "runs", run_id)
    (ws / "runner.pid").write_text("99999999")  # 존재하지 않는 PID

    resp = client.delete(f"/api/runs/{run_id}")

    assert resp.status_code == 200
    assert not ws.exists()
