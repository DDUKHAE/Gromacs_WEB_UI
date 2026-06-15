import pytest
import shutil
from pathlib import Path
from lib.ligand_params import is_acpype_available, run_acpype, assemble_complex


def test_is_acpype_available_returns_bool():
    assert isinstance(is_acpype_available(), bool)


def test_is_acpype_available_false_when_absent(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert is_acpype_available() is False


def test_is_acpype_available_true_when_present(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/acpype")
    assert is_acpype_available() is True


def test_run_acpype_graceful_when_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr("lib.ligand_params.is_acpype_available", lambda: False)
    ligand = tmp_path / "lig.pdb"
    ligand.write_text("ATOM      1  C1  LIG A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n")
    result = run_acpype(ligand, charge=0)
    assert result["available"] is False
    assert result["itp"] == ""
    assert result["gro"] == ""
    assert result["posre"] == ""
    assert result["penalty"] == 0.0


def test_run_acpype_returns_dict_with_required_keys(monkeypatch, tmp_path):
    monkeypatch.setattr("lib.ligand_params.is_acpype_available", lambda: False)
    ligand = tmp_path / "lig.pdb"
    ligand.write_text("END\n")
    result = run_acpype(ligand)
    for key in ("available", "itp", "gro", "posre", "penalty"):
        assert key in result, f"Missing key: {key}"


def test_run_acpype_default_charge_is_zero(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        import types
        return types.SimpleNamespace(returncode=1, stdout="", stderr="mock")

    monkeypatch.setattr("lib.ligand_params.is_acpype_available", lambda: True)
    monkeypatch.setattr("lib.ligand_params.subprocess.run", fake_run)

    ligand = tmp_path / "lig.pdb"
    ligand.write_text("END\n")
    run_acpype(ligand)
    cmd_str = " ".join(captured.get("cmd", []))
    assert "-n" in cmd_str
    assert "0" in cmd_str


_PROTEIN_GRO = """\
Protein in water
5
    1ALA      N    1   1.000   1.000   1.000
    1ALA     CA    2   1.100   1.000   1.000
    1ALA      C    3   1.200   1.000   1.000
    1ALA      O    4   1.300   1.000   1.000
    1ALA     CB    5   1.100   1.100   1.000
   5.000   5.000   5.000
"""

_LIGAND_GRO = """\
LIG
3
    1LIG     C1    1   2.000   2.000   2.000
    1LIG     C2    2   2.100   2.000   2.000
    1LIG     O1    3   2.200   2.000   2.000
   5.000   5.000   5.000
"""

_LIGAND_ITP = """\
; LIG force field parameters
[ moleculetype ]
LIG  3

[ atoms ]
1  ca  1  LIG  C1  1  0.000  12.011
"""

_TOPOL_TOP = """\
#include "amber99sb-ildn.ff/forcefield.itp"
#include "amber99sb-ildn.ff/tip3p.itp"

[ system ]
Protein in water

[ molecules ]
Protein_chain_A  1
SOL              100
"""


def test_assemble_complex_merges_atom_counts(tmp_path):
    protein = tmp_path / "protein.gro"
    protein.write_text(_PROTEIN_GRO)
    lig_gro = tmp_path / "LIG.gro"
    lig_gro.write_text(_LIGAND_GRO)
    lig_itp = tmp_path / "LIG.itp"
    lig_itp.write_text(_LIGAND_ITP)
    topol = tmp_path / "topol.top"
    topol.write_text(_TOPOL_TOP)

    result = assemble_complex(protein, lig_gro, lig_itp, topol, tmp_path)
    lines = result["complex_gro"].splitlines()
    assert int(lines[1].strip()) == 8


def test_assemble_complex_includes_itp_in_topol(tmp_path):
    protein = tmp_path / "protein.gro"
    protein.write_text(_PROTEIN_GRO)
    lig_gro = tmp_path / "LIG.gro"
    lig_gro.write_text(_LIGAND_GRO)
    lig_itp = tmp_path / "LIG.itp"
    lig_itp.write_text(_LIGAND_ITP)
    topol = tmp_path / "topol.top"
    topol.write_text(_TOPOL_TOP)

    result = assemble_complex(protein, lig_gro, lig_itp, topol, tmp_path)
    assert '#include "LIG.itp"' in result["topol_top"]


def test_assemble_complex_adds_lig_to_molecules(tmp_path):
    protein = tmp_path / "protein.gro"
    protein.write_text(_PROTEIN_GRO)
    lig_gro = tmp_path / "LIG.gro"
    lig_gro.write_text(_LIGAND_GRO)
    lig_itp = tmp_path / "LIG.itp"
    lig_itp.write_text(_LIGAND_ITP)
    topol = tmp_path / "topol.top"
    topol.write_text(_TOPOL_TOP)

    result = assemble_complex(protein, lig_gro, lig_itp, topol, tmp_path)
    assert "LIG" in result["topol_top"]
    mol_lines = [l for l in result["topol_top"].splitlines() if l.startswith("LIG")]
    assert len(mol_lines) == 1
    assert "1" in mol_lines[0]
