import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

LYSOZYME_PDB = Path(__file__).parent.parent / "tutorial_data" / "Lysozyme_in_water" / "1AKI.pdb"


@pytest.fixture
def tmp_harness(tmp_path):
    (tmp_path / "runs").mkdir()
    (tmp_path / "tmp").mkdir()
    return tmp_path


@pytest.fixture
def client(tmp_harness):
    from web.server import create_app
    app = create_app(harness_dir=tmp_harness)
    return TestClient(app)


class TestAnalyzeEndpoint:
    def test_analyze_returns_200(self, client):
        pdb_bytes = LYSOZYME_PDB.read_bytes()
        resp = client.post(
            "/api/pdb/analyze",
            files={"pdb_file": ("1AKI.pdb", io.BytesIO(pdb_bytes), "text/plain")},
        )
        assert resp.status_code == 200

    def test_analyze_returns_chains(self, client):
        pdb_bytes = LYSOZYME_PDB.read_bytes()
        data = client.post(
            "/api/pdb/analyze",
            files={"pdb_file": ("1AKI.pdb", io.BytesIO(pdb_bytes), "text/plain")},
        ).json()
        assert data["chains"] == ["A"]

    def test_analyze_returns_disulfides(self, client):
        pdb_bytes = LYSOZYME_PDB.read_bytes()
        data = client.post(
            "/api/pdb/analyze",
            files={"pdb_file": ("1AKI.pdb", io.BytesIO(pdb_bytes), "text/plain")},
        ).json()
        assert len(data["disulfide_candidates"]) == 4

    def test_analyze_rejects_non_pdb(self, client):
        resp = client.post(
            "/api/pdb/analyze",
            files={"pdb_file": ("bad.txt", io.BytesIO(b"not a pdb"), "text/plain")},
        )
        # Should still return 200 with empty/minimal result (graceful)
        assert resp.status_code == 200


class TestFetchEndpoint:
    def test_fetch_invalid_id_returns_400(self, client):
        resp = client.get("/api/pdb/fetch?pdb_id=TOOLONG")
        assert resp.status_code == 400

    def test_fetch_missing_param_returns_422(self, client):
        resp = client.get("/api/pdb/fetch")
        assert resp.status_code == 422


class TestProtonateEndpoint:
    def test_protonate_returns_200(self, client):
        pdb_bytes = LYSOZYME_PDB.read_bytes()
        resp = client.post(
            "/api/pdb/protonate",
            files={"pdb_file": ("1AKI.pdb", io.BytesIO(pdb_bytes), "text/plain")},
            data={"ph": "7.0"},
        )
        assert resp.status_code == 200

    def test_protonate_returns_available_field(self, client):
        pdb_bytes = LYSOZYME_PDB.read_bytes()
        data = client.post(
            "/api/pdb/protonate",
            files={"pdb_file": ("1AKI.pdb", io.BytesIO(pdb_bytes), "text/plain")},
            data={"ph": "7.0"},
        ).json()
        assert "available" in data
        assert "his_states" in data
        assert "pka_list" in data

    def test_protonate_default_ph(self, client):
        pdb_bytes = LYSOZYME_PDB.read_bytes()
        resp = client.post(
            "/api/pdb/protonate",
            files={"pdb_file": ("1AKI.pdb", io.BytesIO(pdb_bytes), "text/plain")},
        )
        assert resp.status_code == 200

    def test_protonate_invalid_ph_returns_422(self, client):
        pdb_bytes = LYSOZYME_PDB.read_bytes()
        resp = client.post(
            "/api/pdb/protonate",
            files={"pdb_file": ("1AKI.pdb", io.BytesIO(pdb_bytes), "text/plain")},
            data={"ph": "99.0"},
        )
        assert resp.status_code == 422
