import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from web.server import create_app

RUN_ID = "protein_20260101_120000"


def _client(root: "Path"):
    return TestClient(create_app(root))


def test_download_returns_zip(ws_factory):
    root, ws = ws_factory(RUN_ID)
    resp = _client(root).get(f"/api/runs/{RUN_ID}/download")
    assert resp.status_code == 200
    assert "application/zip" in resp.headers["content-type"]
    assert f"{RUN_ID}.zip" in resp.headers.get("content-disposition", "")


def test_download_zip_contains_state_and_pdb(ws_factory):
    root, ws = ws_factory(RUN_ID)
    resp = _client(root).get(f"/api/runs/{RUN_ID}/download")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any("state.json" in n for n in names)
    assert any("input.pdb" in n for n in names)


def test_download_excludes_large_binary_files(ws_factory):
    root, ws = ws_factory(
        RUN_ID,
        files={
            "traj.xtc": b"\x00" * 200,
            "run.edr": b"\x00" * 200,
            "run.tpr": b"\x00" * 200,
            "run.cpt": b"\x00" * 200,
            "run.trr": b"\x00" * 200,
        },
    )
    resp = _client(root).get(f"/api/runs/{RUN_ID}/download")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    for ext in (".xtc", ".edr", ".tpr", ".cpt", ".trr"):
        assert all(not n.endswith(ext) for n in names), f"{ext} found in zip"


def test_download_includes_nested_files(ws_factory):
    root, ws = ws_factory(
        RUN_ID,
        files={"stage2_md/em.gro": "GROMACS\n", "stage3_viz/rmsd.xvg": "@ title\n"},
    )
    resp = _client(root).get(f"/api/runs/{RUN_ID}/download")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any("em.gro" in n for n in names)
    assert any("rmsd.xvg" in n for n in names)


def test_download_unknown_run_returns_404(ws_factory):
    root, _ = ws_factory(RUN_ID)
    resp = _client(root).get("/api/runs/ghost_20260101_120000/download")
    assert resp.status_code == 404
