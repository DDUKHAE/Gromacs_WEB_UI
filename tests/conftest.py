import shutil
from pathlib import Path
import pytest


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Per-test isolated workspace."""
    ws = tmp_path / "workspace"
    (ws / "inputs").mkdir(parents=True)
    (ws / "stage1_env").mkdir()
    (ws / "stage2_md").mkdir()
    (ws / "stage3_viz").mkdir()
    return ws


@pytest.fixture
def gmx_available() -> bool:
    return shutil.which("gmx") is not None


@pytest.fixture
def ubq_pdb_path() -> Path:
    p = Path(__file__).resolve().parents[1] / "1UBQ.pdb"
    assert p.exists(), f"1UBQ.pdb missing: {p}"
    return p
