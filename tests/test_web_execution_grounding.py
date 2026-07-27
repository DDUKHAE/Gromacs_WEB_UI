"""Web entry paths must materialize the same verified grounding artifacts.

These tests deliberately stop before GROMACS/LLM execution.  They verify the
common API boundary where browser input becomes an immutable run plan and
protocol contract, which is the point both runners depend on.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lib import protocol_contract as pc
from lib import run_plan as rp
from web.llm_adapters import ADAPTERS
from web.server import create_app


PDB = b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000\n"


class _FakeProcess:
    pid = 4321


@pytest.mark.parametrize(
    ("tutorial_id", "llm", "expected_mode"),
    [
        ("", "", "auto"),
        ("Lysozyme_in_water", "", "selected"),
        ("", "fake", "auto"),
        ("Lysozyme_in_water", "fake", "selected"),
    ],
)
def test_web_paths_share_verified_run_plan_and_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tutorial_id: str, llm: str, expected_mode: str,
):
    """Selected/auto x direct/LLM must cross the identical grounding gate."""
    direct_calls: list[list[str]] = []
    llm_calls: list[dict] = []

    def fake_popen(command, **_kwargs):
        direct_calls.append(command)
        return _FakeProcess()

    async def fake_llm_agent(**kwargs):
        llm_calls.append(kwargs)

    monkeypatch.setattr("web.server.subprocess.Popen", fake_popen)
    monkeypatch.setattr("web.server.llm_runner.check_cli", lambda _adapter: True)
    monkeypatch.setattr("web.server.llm_runner.run_llm_agent", fake_llm_agent)
    monkeypatch.setitem(ADAPTERS, "fake", object())

    client = TestClient(create_app(tmp_path))
    response = client.post(
        "/api/runs",
        data={"tutorial_id": tutorial_id, "llm": llm},
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

    if llm:
        assert len(llm_calls) == 1
        assert not direct_calls
        assert llm_calls[0]["workspace"] == workspace
    else:
        assert len(direct_calls) == 1
        assert "--skill" in direct_calls[0]
        assert "all" in direct_calls[0]
        assert not llm_calls
