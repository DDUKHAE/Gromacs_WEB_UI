import json
import pytest
from pathlib import Path
from web.llm_runner import _apply_system_config_constraint


def test_returns_empty_string_when_no_config(tmp_path):
    assert _apply_system_config_constraint(tmp_path) == ""


def test_returns_constraint_block_when_config_present(tmp_path):
    config = {
        "forcefield": {"name": "charmm36-jul2022", "water_model": "tip3p"},
        "box": {"type": "dodecahedron", "edge_distance_nm": 1.0},
    }
    (tmp_path / "system_config.json").write_text(json.dumps(config))
    result = _apply_system_config_constraint(tmp_path)
    assert "SYSTEM BUILDER CONSTRAINTS" in result
    assert "charmm36-jul2022" in result


def test_constraint_block_mentions_ion_settings(tmp_path):
    config = {"ions": {"salt_type": "KCl", "concentration_M": 0.2, "neutralize": True}}
    (tmp_path / "system_config.json").write_text(json.dumps(config))
    result = _apply_system_config_constraint(tmp_path)
    assert "KCl" in result
    assert "0.2" in result
