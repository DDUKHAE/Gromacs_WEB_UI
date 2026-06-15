import pytest
from pathlib import Path
from lib.membrane_builder import (
    is_packmol_memgen_available,
    list_supported_lipids,
    SUPPORTED_LIPIDS,
    build_membrane,
)


def test_is_packmol_memgen_available_returns_bool():
    assert isinstance(is_packmol_memgen_available(), bool)


def test_list_supported_lipids_returns_8_species():
    assert len(list_supported_lipids()) == 8


def test_list_supported_lipids_all_have_required_keys():
    for lipid in list_supported_lipids():
        for key in ("name", "full_name", "charge", "description"):
            assert key in lipid, f"Missing key '{key}' in lipid {lipid}"


def test_list_supported_lipids_contains_expected_names():
    names = {lipid["name"] for lipid in list_supported_lipids()}
    assert names == {"POPC", "POPE", "POPS", "DPPC", "DPPE", "DPPS", "CHL1", "PSM"}


def test_supported_lipids_charge_types():
    charges = {lipid["name"]: lipid["charge"] for lipid in list_supported_lipids()}
    assert charges["POPS"] == -1
    assert charges["DPPS"] == -1
    assert charges["POPC"] == 0
    assert charges["CHL1"] == 0


def test_is_packmol_memgen_available_false_when_absent(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert is_packmol_memgen_available() is False


def test_is_packmol_memgen_available_true_when_present(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/packmol-memgen")
    assert is_packmol_memgen_available() is True


def test_build_membrane_graceful_when_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr("lib.membrane_builder.is_packmol_memgen_available", lambda: False)
    result = build_membrane({
        "lipids_upper": [{"name": "POPC", "fraction": 1.0}],
        "lipids_lower": [{"name": "POPC", "fraction": 1.0}],
    }, tmp_path)
    assert result["available"] is False
    assert result["gro"] == ""
    assert result["top"] == ""


def test_build_membrane_raises_on_invalid_fraction_sum(monkeypatch, tmp_path):
    monkeypatch.setattr("lib.membrane_builder.is_packmol_memgen_available", lambda: True)
    with pytest.raises(ValueError, match="fractions"):
        build_membrane({
            "lipids_upper": [
                {"name": "POPC", "fraction": 0.5},
                {"name": "POPE", "fraction": 0.3},
            ],
            "lipids_lower": [{"name": "POPC", "fraction": 1.0}],
        }, tmp_path)


def test_build_membrane_command_includes_protein_pdb(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        import types
        r = types.SimpleNamespace(returncode=1, stdout="", stderr="mock")
        return r

    monkeypatch.setattr("lib.membrane_builder.is_packmol_memgen_available", lambda: True)
    monkeypatch.setattr("lib.membrane_builder.subprocess.run", fake_run)

    protein = tmp_path / "protein.pdb"
    protein.write_text("ATOM")
    build_membrane({
        "lipids_upper": [{"name": "POPC", "fraction": 1.0}],
        "lipids_lower": [{"name": "POPC", "fraction": 1.0}],
        "protein_pdb": str(protein),
        "protein_orientation": "opm",
    }, tmp_path)
    assert "--pdb" in captured["cmd"]
