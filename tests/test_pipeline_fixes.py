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


# ── Task 2 ──────────────────────────────────────────────────────────────────

def test_run_viz_sets_last_completed_stage(tmp_path):
    """_run_viz must write last_completed_stage='viz' to state.json."""
    import json as _json
    from lib import state as _state

    ws = tmp_path
    (ws / "stage2_md").mkdir()
    (ws / "stage3_viz").mkdir()
    _state.write(ws, {
        "step_outputs": {"step_7": {"production_gro": "stage2_md/production.gro"}},
        "last_completed_stage": "md",
        "current_step": 7,
        "tutorial": {},
        "hardware": {},
        "topology_backups": [],
    })

    with patch("skills.illustrator.illustrator.run_core_analyses", return_value={}), \
         patch("skills.illustrator.illustrator.assert_ready", return_value={
             "step_outputs": {"step_7": {"production_gro": "stage2_md/production.gro"}}
         }):
        from web.runner import _run_viz
        _run_viz(ws)

    s = _json.loads((ws / "state.json").read_text())
    assert s["last_completed_stage"] == "viz"


def test_api_create_run_uses_skill_all():
    """api_create_run must launch runner.py with --skill all, not --skill env."""
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
                data={"forcefield": "charmm36", "water": "tip3p", "box_type": "dodecahedron"},
                files={"pdb_file": ("protein.pdb", fake_pdb, "chemical/x-pdb")},
            )

        assert r.status_code == 201
        call_args = mock_popen.call_args[0][0]  # first positional arg = cmd list
        assert "--skill" in call_args
        skill_idx = call_args.index("--skill")
        assert call_args[skill_idx + 1] == "all"


# ── Task 3 ──────────────────────────────────────────────────────────────────

def test_trjconv_nopbc_creates_corrected_trajectory(tmp_path):
    """_trjconv_nopbc must call gmx trjconv with -pbc mol -center."""
    from skills.illustrator.illustrator import _trjconv_nopbc
    from lib import gmx_wrapper as GW

    ws = tmp_path
    (ws / "stage2_md").mkdir()

    fake_result = MagicMock()
    fake_result.ok = True

    with patch.object(GW, "run", return_value=fake_result) as mock_run:
        result = _trjconv_nopbc(ws, "production")

    assert result == "production_noPBC"
    call_cmd = mock_run.call_args[0][0]
    assert "trjconv" in call_cmd
    assert "-pbc" in call_cmd
    assert "mol" in call_cmd
    assert "-center" in call_cmd
    assert "-f" in call_cmd
    f_idx = call_cmd.index("-f")
    assert call_cmd[f_idx + 1] == "production.xtc"
    assert "-o" in call_cmd
    o_idx = call_cmd.index("-o")
    assert "production_noPBC.xtc" in call_cmd[o_idx + 1]


def test_trjconv_nopbc_skips_if_file_exists(tmp_path):
    """_trjconv_nopbc must not re-run trjconv if the noPBC file already exists."""
    from skills.illustrator.illustrator import _trjconv_nopbc
    from lib import gmx_wrapper as GW

    ws = tmp_path
    md = ws / "stage2_md"
    md.mkdir()
    (md / "production_noPBC.xtc").touch()

    with patch.object(GW, "run") as mock_run:
        result = _trjconv_nopbc(ws, "production")

    assert result == "production_noPBC"
    mock_run.assert_not_called()


def test_run_core_analyses_uses_nopbc_trajectory(tmp_path):
    """run_core_analyses must pass the noPBC trajectory to rmsd/rmsf/gyrate/sasa."""
    from skills.illustrator.illustrator import run_core_analyses

    ws = tmp_path
    (ws / "stage2_md").mkdir()
    (ws / "stage3_viz").mkdir()

    with patch("skills.illustrator.illustrator.assert_ready", return_value={
            "step_outputs": {"step_7": {"production_gro": "stage2_md/production.gro"}}}), \
         patch("skills.illustrator.illustrator._trjconv_nopbc",
               return_value="production_noPBC") as mock_trjconv, \
         patch("skills.illustrator.illustrator._rmsd",
               return_value=tmp_path / "stage3_viz" / "rmsd.xvg") as mock_rmsd, \
         patch("skills.illustrator.illustrator._rmsf",
               return_value=tmp_path / "stage3_viz" / "rmsf.xvg") as mock_rmsf, \
         patch("skills.illustrator.illustrator._gyrate",
               return_value=tmp_path / "stage3_viz" / "gyrate.xvg") as mock_gyrate, \
         patch("skills.illustrator.illustrator._sasa",
               return_value=tmp_path / "stage3_viz" / "sasa.xvg") as mock_sasa, \
         patch("skills.illustrator.illustrator._energy_term",
               return_value=tmp_path / "stage3_viz" / "energy.xvg"), \
         patch("lib.xvg_parser.summary", return_value={"mean": 0.1, "std": 0.01, "count": 10}), \
         patch("lib.state.read", return_value={"step_outputs": {}}), \
         patch("lib.state.write"):
        run_core_analyses(workspace_dir=ws)

    mock_trjconv.assert_called_once_with(ws, "production")

    _, rmsd_kwargs = mock_rmsd.call_args
    assert rmsd_kwargs.get("xtc") == "production_noPBC"

    _, rmsf_kwargs = mock_rmsf.call_args
    assert rmsf_kwargs.get("xtc") == "production_noPBC"

    _, gyrate_kwargs = mock_gyrate.call_args
    assert gyrate_kwargs.get("xtc") == "production_noPBC"

    _, sasa_kwargs = mock_sasa.call_args
    assert sasa_kwargs.get("xtc") == "production_noPBC"
