import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from web.server import create_app


@pytest.fixture
def tmp_harness(tmp_path):
    (tmp_path / "runs").mkdir()
    (tmp_path / "tmp").mkdir()
    return tmp_path


@pytest.fixture
def client(tmp_harness):
    return TestClient(create_app(harness_dir=tmp_harness))


class TestMembraneStatusEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/api/membrane/status")
        assert resp.status_code == 200

    def test_has_available_key(self, client):
        data = client.get("/api/membrane/status").json()
        assert "available" in data
        assert isinstance(data["available"], bool)

    def test_has_version_key(self, client):
        data = client.get("/api/membrane/status").json()
        assert "version" in data


class TestMembraneLipidsEndpoint:
    def test_returns_200(self, client):
        assert client.get("/api/membrane/lipids").status_code == 200

    def test_returns_8_lipids(self, client):
        data = client.get("/api/membrane/lipids").json()
        assert len(data) == 8

    def test_each_lipid_has_name_and_charge(self, client):
        for lipid in client.get("/api/membrane/lipids").json():
            assert "name" in lipid
            assert "charge" in lipid


class TestMembraneBuildEndpoint:
    def test_missing_lipids_returns_422_or_503(self, client):
        resp = client.post("/api/membrane/build", data={"config_json": "{}"})
        assert resp.status_code in (422, 503)

    def test_invalid_fraction_sum_returns_422(self, client, monkeypatch):
        import lib.membrane_builder as mb
        monkeypatch.setattr(mb, "is_packmol_memgen_available", lambda: True)
        config = {
            "lipids_upper": [{"name": "POPC", "fraction": 0.5}, {"name": "POPE", "fraction": 0.3}],
            "lipids_lower": [{"name": "POPC", "fraction": 1.0}],
        }
        resp = client.post("/api/membrane/build", data={"config_json": json.dumps(config)})
        assert resp.status_code == 422

    def test_unavailable_returns_503(self, client, monkeypatch):
        import lib.membrane_builder as mb
        monkeypatch.setattr(mb, "is_packmol_memgen_available", lambda: False)
        config = {
            "lipids_upper": [{"name": "POPC", "fraction": 1.0}],
            "lipids_lower": [{"name": "POPC", "fraction": 1.0}],
        }
        resp = client.post("/api/membrane/build", data={"config_json": json.dumps(config)})
        assert resp.status_code == 503
