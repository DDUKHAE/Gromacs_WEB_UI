"""Web entry paths must materialize the same verified grounding artifacts.

These tests deliberately stop before GROMACS execution. They verify the
API boundary where browser input becomes an immutable run plan and
protocol contract, which the direct runner (web/runner.py) depends on.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lib import protocol_contract as pc
from lib import run_plan as rp
from web.server import create_app


PDB = b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000\n"


class _FakeProcess:
    pid = 4321


@pytest.mark.parametrize(
    ("tutorial_id", "expected_mode"),
    [
        ("", "auto"),
        ("Lysozyme_in_water", "selected"),
    ],
)
def test_web_path_materializes_verified_run_plan_and_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tutorial_id: str, expected_mode: str,
):
    """Selected/auto tutorial routing must cross the identical grounding gate."""
    direct_calls: list[list[str]] = []

    def fake_popen(command, **_kwargs):
        direct_calls.append(command)
        return _FakeProcess()

    monkeypatch.setattr("web.server.subprocess.Popen", fake_popen)

    client = TestClient(create_app(tmp_path))
    response = client.post(
        "/api/runs",
        data={"tutorial_id": tutorial_id},
        files={"pdb_file": ("protein.pdb", PDB, "text/plain")},
    )

    assert response.status_code == 201, response.text
    workspace = tmp_path / "runs" / response.json()["run_id"]
    plan = rp.assert_valid(workspace)
    contract = pc.assert_valid(workspace)
    assert plan is not None
    assert contract["run_plan"]["sha256"] == plan["plan_sha256"]
    assert plan["tutorial"]["mode"] == expected_mode
    assert contract["tutorial_id"] == plan["tutorial"]["id"]
    assert {pack["stage"] for pack in contract["context_packs"]} >= {"environment", "simulation", "analysis"}

    plan_response = client.get(f"/api/runs/{response.json()['run_id']}/plan")
    assert plan_response.status_code == 200
    assert plan_response.json()["plan_sha256"] == plan["plan_sha256"]

    assert len(direct_calls) == 1
    assert "--skill" in direct_calls[0]
    assert "all" in direct_calls[0]
