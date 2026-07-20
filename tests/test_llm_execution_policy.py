from pathlib import Path

from fastapi.testclient import TestClient

from web.llm_adapters.claude import ClaudeAdapter
from web.llm_adapters.codex import CodexAdapter
from web.llm_adapters.gemini import GeminiAdapter
from web.server import create_app


PDB = b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000\n"


def test_adapters_never_add_unattended_execution_flags():
    assert ClaudeAdapter().build_command(auto_approve=True) == ["claude"]
    assert CodexAdapter().build_command(auto_approve=True) == ["codex", "--approval-mode", "suggest"]
    assert GeminiAdapter().build_command(auto_approve=True) == ["agy"]


def test_web_rejects_llm_auto_approval_before_runner_starts(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    response = client.post(
        "/api/runs",
        data={"llm": "claude", "auto_approve": "true"},
        files={"pdb_file": ("protein.pdb", PDB, "text/plain")},
    )
    assert response.status_code == 403
    assert "sandboxed runner" in response.json()["detail"]
    assert not (tmp_path / "runs").exists()
