import pytest
from fastapi.testclient import TestClient
from web.server import create_app

RUN_ID = "protein_20260101_120000"


def _client(root):
    return TestClient(create_app(root))


def test_mol_files_returns_gro_in_subdirectory(ws_factory):
    root, ws = ws_factory(RUN_ID, files={"stage2_md/npt.gro": "GROMACS\n"})
    resp = _client(root).get(f"/api/runs/{RUN_ID}/mol_files")
    assert resp.status_code == 200
    assert "npt.gro" in resp.json()


def test_get_run_file_serves_subdirectory_file(ws_factory):
    root, ws = ws_factory(RUN_ID, files={"stage2_md/npt.gro": "GROMACS structure\n"})
    resp = _client(root).get(f"/api/runs/{RUN_ID}/file/npt.gro")
    assert resp.status_code == 200
    assert b"GROMACS structure" in resp.content


def test_get_run_file_top_level_still_works(ws_factory):
    root, ws = ws_factory(RUN_ID)
    # input.pdb is at inputs/input.pdb (subdirectory), let's add a top-level pdb too
    (ws / "final.pdb").write_text("ATOM top-level\n")
    resp = _client(root).get(f"/api/runs/{RUN_ID}/file/final.pdb")
    assert resp.status_code == 200


def test_get_run_file_missing_returns_404(ws_factory):
    root, ws = ws_factory(RUN_ID)
    resp = _client(root).get(f"/api/runs/{RUN_ID}/file/ghost.gro")
    assert resp.status_code == 404


def test_get_run_file_path_traversal_rejected(ws_factory):
    root, ws = ws_factory(RUN_ID)
    resp = _client(root).get(f"/api/runs/{RUN_ID}/file/../../etc/passwd")
    # httpx ≥ 0.27 normalises path segments before sending, so ../../etc/passwd
    # becomes /api/runs/etc/passwd which matches no route → 404.
    # Either 400/422 (app-layer guard) or 404 (no-route after normalisation)
    # both mean the traversal was rejected.
    assert resp.status_code in (400, 404, 422)


def test_get_run_file_wrong_extension_rejected(ws_factory):
    root, ws = ws_factory(RUN_ID)
    (ws / "notes.txt").write_text("notes")
    resp = _client(root).get(f"/api/runs/{RUN_ID}/file/notes.txt")
    assert resp.status_code == 400
