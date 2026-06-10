import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── Task 1 ──────────────────────────────────────────────────────────────────

def test_api_create_run_saves_user_preferences_to_meta():
    """POST /api/runs must persist forcefield/water/box_type to meta.json."""
    from fastapi.testclient import TestClient
    from web.server import create_app

    with tempfile.TemporaryDirectory() as tmp:
        hd = Path(tmp)
        (hd / "runs").mkdir()
        app = create_app(harness_dir=hd)
        client = TestClient(app)

        fake_pdb = (
            b"ATOM      1  N   ALA A   1       1.000   1.000   1.000"
            b"  1.00  0.00\nEND\n"
        )
        with patch("web.server.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=99999)
            r = client.post(
                "/api/runs",
                data={
                    "forcefield": "amber99sb-ildn",
                    "water": "tip4p",
                    "box_type": "cubic",
                },
                files={"pdb_file": ("protein.pdb", fake_pdb, "chemical/x-pdb")},
            )

        assert r.status_code == 201
        run_id = r.json()["run_id"]
        meta = json.loads((hd / "runs" / run_id / "meta.json").read_text())
        prefs = meta["user_preferences"]
        assert prefs["forcefield"] == "amber99sb-ildn"
        assert prefs["water"] == "tip4p"
        assert prefs["box_type"] == "cubic"


def test_build_environment_respects_meta_forcefield(tmp_path):
    """build_environment must use user_preferences from meta.json over manifest defaults."""
    from skills.env_builder.env_builder import build_environment

    ws = tmp_path
    (ws / "inputs").mkdir(parents=True)
    pdb = ws / "inputs" / "input.pdb"
    pdb.write_text("ATOM\nEND\n")
    (ws / "meta.json").write_text(json.dumps({
        "user_preferences": {
            "forcefield": "amber99sb-ildn",
            "water": "tip4p",
            "box_type": "cubic",
        }
    }))

    manifest = {
        "defaults": {
            "forcefield": "charmm36",
            "water_model": "tip3p",
            "box_type": "dodecahedron",
            "box_distance_nm": 1.0,
        }
    }

    with patch("skills.env_builder.env_builder.collect_hardware"), \
         patch("skills.env_builder.env_builder._strip_hetatm_water"), \
         patch("skills.env_builder.env_builder.select_tutorial") as mock_sel, \
         patch("skills.env_builder.env_builder.run_step1_topology") as mock_s1, \
         patch("skills.env_builder.env_builder.run_step2_box") as mock_s2, \
         patch("skills.env_builder.env_builder.run_step3_solvate"), \
         patch("skills.env_builder.env_builder.run_step4_ions_prep"), \
         patch("skills.env_builder.env_builder.run_step5_genion"), \
         patch("lib.tutorial_registry.load_manifest", return_value=manifest), \
         patch("lib.state.read", return_value={"step_outputs": {}}), \
         patch("lib.state.write"), \
         patch("lib.state.path", return_value=ws / "state.json"), \
         patch("lib.state.initial", return_value={}):
        mock_sel.return_value = MagicMock(
            tutorial_id="lysozyme_aqueous",
            pipeline_variant="standard",
            unsupported_reason=None,
        )
        build_environment(pdb_path=pdb, prompt="", workspace_dir=ws, interactive=False)

    # user's amber99sb-ildn must override manifest charmm36
    mock_s1.assert_called_once_with(ws, "amber99sb-ildn", "tip4p")
    mock_s2.assert_called_once_with(ws, "cubic", 1.0)
