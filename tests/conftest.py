import pytest
from pathlib import Path


@pytest.fixture
def ws_factory(tmp_path):
    """Return a factory that creates a valid run workspace under tmp_path/runs/."""
    def _make(run_id: str, files: dict[str, str | bytes] | None = None) -> tuple[Path, Path]:
        ws = tmp_path / "runs" / run_id
        ws.mkdir(parents=True)
        (ws / "state.json").write_text('{"status": "completed", "step": 8}')
        (ws / "runner.log").write_text("simulation completed\n")
        (ws / "inputs").mkdir()
        (ws / "inputs" / "input.pdb").write_text("ATOM      1  CA  ALA A   1      0.0   0.0   0.0\n")
        if files:
            for rel_path, content in files.items():
                target = ws / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, bytes):
                    target.write_bytes(content)
                else:
                    target.write_text(content)
        return tmp_path, ws
    return _make
