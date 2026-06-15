import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from web.server import create_app

_MINIMAL_PDB = (
    "ATOM      1  C1  LIG A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    "END\n"
)

_PROTEIN_GRO = (
    "Protein\n5\n"
    "    1ALA      N    1   1.000   1.000   1.000\n"
    "    1ALA     CA    2   1.100   1.000   1.000\n"
    "    1ALA      C    3   1.200   1.000   1.000\n"
    "    1ALA      O    4   1.300   1.000   1.000\n"
    "    1ALA     CB    5   1.100   1.100   1.000\n"
    "   5.000   5.000   5.000\n"
)

_LIGAND_GRO = (
    "LIG\n2\n"
    "    1LIG     C1    1   2.000   2.000   2.000\n"
    "    1LIG     C2    2   2.100   2.000   2.000\n"
    "   5.000   5.000   5.000\n"
)

_LIGAND_ITP = '; LIG\n[ moleculetype ]\nLIG  3\n'
_TOPOL_TOP = (
    '#include "ff.itp"\n[ system ]\nProtein\n[ molecules ]\nProtein 1\n'
)


@pytest.fixture
def tmp_harness(tmp_path):
    (tmp_path / "runs").mkdir()
    (tmp_path / "tmp").mkdir()
    return tmp_path


@pytest.fixture
def client(tmp_harness):
    return TestClient(create_app(harness_dir=tmp_harness))


class TestLigandStatusEndpoint:
    def test_returns_200(self, client):
        assert client.get("/api/ligand/status").status_code == 200

    def test_has_available_key(self, client):
        data = client.get("/api/ligand/status").json()
        assert "available" in data
        assert isinstance(data["available"], bool)

    def test_has_version_key(self, client):
        data = client.get("/api/ligand/status").json()
        assert "version" in data


class TestParameterizeEndpoint:
    def test_unavailable_returns_503(self, client, monkeypatch):
        import lib.ligand_params as lp
        monkeypatch.setattr(lp, "is_acpype_available", lambda: False)
        resp = client.post(
            "/api/ligand/parameterize",
            data={"charge": "0", "atom_type": "gaff2", "residue_name": "LIG"},
            files={"ligand": ("lig.pdb", _MINIMAL_PDB, "text/plain")},
        )
        assert resp.status_code == 503

    def test_valid_upload_returns_200_or_503(self, client):
        resp = client.post(
            "/api/ligand/parameterize",
            data={"charge": "0", "atom_type": "gaff2", "residue_name": "LIG"},
            files={"ligand": ("lig.pdb", _MINIMAL_PDB, "text/plain")},
        )
        assert resp.status_code in (200, 503)


class TestAssembleEndpoint:
    def test_returns_200_with_valid_files(self, client):
        resp = client.post(
            "/api/ligand/assemble",
            files={
                "protein_gro": ("protein.gro", _PROTEIN_GRO, "text/plain"),
                "ligand_gro":  ("LIG.gro",     _LIGAND_GRO,  "text/plain"),
                "ligand_itp":  ("LIG.itp",     _LIGAND_ITP,  "text/plain"),
                "topol_top":   ("topol.top",   _TOPOL_TOP,   "text/plain"),
            },
        )
        assert resp.status_code == 200

    def test_response_has_complex_gro_and_topol(self, client):
        resp = client.post(
            "/api/ligand/assemble",
            files={
                "protein_gro": ("protein.gro", _PROTEIN_GRO, "text/plain"),
                "ligand_gro":  ("LIG.gro",     _LIGAND_GRO,  "text/plain"),
                "ligand_itp":  ("LIG.itp",     _LIGAND_ITP,  "text/plain"),
                "topol_top":   ("topol.top",   _TOPOL_TOP,   "text/plain"),
            },
        )
        data = resp.json()
        assert "complex_gro" in data
        assert "topol_top" in data
