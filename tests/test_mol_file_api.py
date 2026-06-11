import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from web.server import create_app


def _make_client_with_run(tmp_path: Path, files: dict[str, bytes]) -> tuple[TestClient, str]:
    """Create TestClient with a fake completed run containing given files."""
    runs_dir = tmp_path / "runs"
    run_id = "protein_20260101_000000"
    ws = runs_dir / run_id
    ws.mkdir(parents=True)
    for name, content in files.items():
        (ws / name).write_bytes(content)
    (ws / "meta.json").write_text(json.dumps({
        "run_id": run_id, "status": "done",
        "user_preferences": {"forcefield": "charmm36", "water": "tip3p", "box_type": "cubic"},
        "protein": "protein", "created_at": "2026-01-01T00:00:00"
    }))
    app = create_app(harness_dir=tmp_path)
    return TestClient(app), run_id


def test_mol_files_lists_gro_and_xtc(tmp_path):
    client, run_id = _make_client_with_run(tmp_path, {
        "em.gro": b"fake gro",
        "md_0_10.xtc": b"fake xtc",
    })
    r = client.get(f"/api/runs/{run_id}/mol_files")
    assert r.status_code == 200
    names = r.json()
    assert "em.gro" in names
    assert "md_0_10.xtc" in names


def test_mol_files_excludes_non_mol_files(tmp_path):
    client, run_id = _make_client_with_run(tmp_path, {"runner.log": b"log data"})
    r = client.get(f"/api/runs/{run_id}/mol_files")
    assert r.status_code == 200
    assert "runner.log" not in r.json()


def test_get_run_file_returns_content(tmp_path):
    content = b"CRYST1 fake gro content"
    client, run_id = _make_client_with_run(tmp_path, {"em.gro": content})
    r = client.get(f"/api/runs/{run_id}/file/em.gro")
    assert r.status_code == 200
    assert r.content == content


def test_get_run_file_rejects_disallowed_extension(tmp_path):
    client, run_id = _make_client_with_run(tmp_path, {"em.gro": b"data"})
    r = client.get(f"/api/runs/{run_id}/file/runner.log")
    assert r.status_code == 400


def test_get_run_file_returns_404_for_missing_file(tmp_path):
    client, run_id = _make_client_with_run(tmp_path, {"em.gro": b"data"})
    r = client.get(f"/api/runs/{run_id}/file/nonexistent.gro")
    assert r.status_code == 404


def test_mol_files_invalid_run_id_format(tmp_path):
    (tmp_path / "runs").mkdir()
    app = create_app(harness_dir=tmp_path)
    client = TestClient(app)
    r = client.get("/api/runs/../../etc/mol_files")
    assert r.status_code in (400, 404, 422)
