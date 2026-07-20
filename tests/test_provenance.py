"""Task B5 — provenance capture: gmx_version, mdp hashes, seed handling."""
import subprocess


from lib import gmx_wrapper as GW
from lib import state
from lib.mdp_templates import base as MDP


# ---------------------------------------------------------------------------
# gmx_wrapper.get_version()
# ---------------------------------------------------------------------------

def test_get_version_parses_gmx_version_line(monkeypatch):
    fake_stdout = (
        "                     :-) GROMACS - gmx, 2023.3 (-:\n"
        "\n"
        "GROMACS version:    2023.3\n"
        "Precision:          mixed\n"
    )

    def _fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, 0, stdout=fake_stdout, stderr="")

    monkeypatch.setattr(GW.subprocess, "run", _fake_run)
    monkeypatch.setattr(GW, "_resolve_gmx_bin", lambda default="gmx": "gmx")
    assert GW.get_version() == "2023.3"


def test_get_version_returns_none_when_gmx_missing(monkeypatch):
    def _raise(cmd, capture_output, text, timeout):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(GW.subprocess, "run", _raise)
    monkeypatch.setattr(GW, "_resolve_gmx_bin", lambda default="gmx": "gmx")
    assert GW.get_version() is None


def test_get_version_returns_none_on_nonzero_exit(monkeypatch):
    def _fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")

    monkeypatch.setattr(GW.subprocess, "run", _fake_run)
    monkeypatch.setattr(GW, "_resolve_gmx_bin", lambda default="gmx": "gmx")
    assert GW.get_version() is None


def test_get_version_returns_none_on_timeout(monkeypatch):
    def _raise(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(GW.subprocess, "run", _raise)
    monkeypatch.setattr(GW, "_resolve_gmx_bin", lambda default="gmx": "gmx")
    assert GW.get_version() is None


# ---------------------------------------------------------------------------
# mdp_templates.base — gen_seed parameterization
# ---------------------------------------------------------------------------

def test_nvt_default_seed_is_nonreproducible(tmp_path):
    out = MDP.render("nvt", {}, output_dir=tmp_path)
    assert "gen_seed                 = -1" in out.read_text()


def test_nvt_reproducible_mode_uses_fixed_seed(tmp_path):
    out = MDP.render("nvt", {"reproducible_mode": True}, output_dir=tmp_path)
    text = out.read_text()
    assert f"gen_seed                 = {MDP.REPRODUCIBLE_SEED}" in text
    assert "gen_seed                 = -1" not in text


def test_nvt_explicit_seed_override_wins_over_reproducible_mode(tmp_path):
    out = MDP.render(
        "nvt", {"reproducible_mode": True, "gen_seed": 12345}, output_dir=tmp_path
    )
    text = out.read_text()
    assert "gen_seed                 = 12345" in text


def test_nvt_explicit_seed_override_without_reproducible_mode(tmp_path):
    out = MDP.render("nvt", {"gen_seed": 777}, output_dir=tmp_path)
    assert "gen_seed                 = 777" in out.read_text()


# ---------------------------------------------------------------------------
# state.py provenance helpers
# ---------------------------------------------------------------------------

def _init(ws):
    ws.mkdir(exist_ok=True)
    state.write(ws, state.initial(ws))


def test_initial_state_has_provenance_block(tmp_path):
    s = state.initial(tmp_path)
    assert "provenance" in s
    prov = s["provenance"]
    assert prov["gmx_version"] is None
    assert prov["mdp_hashes"] == {}
    assert prov["seed"] == {}


def test_capture_provenance_records_gmx_version_and_platform(tmp_path, monkeypatch):
    _init(tmp_path)
    monkeypatch.setattr(GW, "get_version", lambda: "2023.3")
    prov = state.capture_provenance(tmp_path)
    assert prov["gmx_version"] == "2023.3"
    assert prov["platform"]
    s = state.read(tmp_path)
    assert s["provenance"]["gmx_version"] == "2023.3"


def test_capture_provenance_gracefully_handles_missing_gmx(tmp_path, monkeypatch):
    _init(tmp_path)
    monkeypatch.setattr(GW, "get_version", lambda: None)
    prov = state.capture_provenance(tmp_path)
    assert prov["gmx_version"] is None  # no crash
    s = state.read(tmp_path)
    assert s["provenance"]["gmx_version"] is None


def test_capture_provenance_survives_get_version_raising(tmp_path, monkeypatch):
    _init(tmp_path)

    def _raise():
        raise RuntimeError("gmx exploded")

    monkeypatch.setattr(GW, "get_version", _raise)
    prov = state.capture_provenance(tmp_path)  # must not raise
    assert prov["gmx_version"] is None


def test_record_force_field(tmp_path):
    _init(tmp_path)
    state.record_force_field(tmp_path, "charmm36")
    s = state.read(tmp_path)
    assert s["provenance"]["force_field"] == "charmm36"


def test_record_mdp_hash_is_stable_sha256(tmp_path):
    _init(tmp_path)
    mdp_path = tmp_path / "nvt.mdp"
    mdp_path.write_text("nsteps = 50000\n")
    import hashlib
    expected = hashlib.sha256(b"nsteps = 50000\n").hexdigest()
    digest = state.record_mdp_hash(tmp_path, "nvt", mdp_path)
    assert digest == expected
    s = state.read(tmp_path)
    assert s["provenance"]["mdp_hashes"]["nvt"] == expected


def test_record_mdp_hash_differs_for_different_content(tmp_path):
    _init(tmp_path)
    mdp_a = tmp_path / "a.mdp"
    mdp_b = tmp_path / "b.mdp"
    mdp_a.write_text("nsteps = 1\n")
    mdp_b.write_text("nsteps = 2\n")
    h1 = state.record_mdp_hash(tmp_path, "em", mdp_a)
    h2 = state.record_mdp_hash(tmp_path, "nvt", mdp_b)
    assert h1 != h2


def test_record_seed(tmp_path):
    _init(tmp_path)
    state.record_seed(tmp_path, "nvt", 42)
    s = state.read(tmp_path)
    assert s["provenance"]["seed"]["nvt"] == 42


# ---------------------------------------------------------------------------
# md_runner.run_phase wiring: mdp hash + seed land in state.json
# ---------------------------------------------------------------------------

def test_run_phase_records_mdp_hash_and_seed(tmp_path, monkeypatch):
    from pathlib import Path
    from skills.md_runner import md_runner as MR

    for sub in ("stage1_env", "stage2_md"):
        (tmp_path / sub).mkdir()
    (tmp_path / "stage1_env" / "ions.gro").write_text("fake")
    (tmp_path / "stage1_env" / "topol.top").write_text("fake")
    state.write(tmp_path, state.initial(tmp_path))
    s = state.read(tmp_path)
    s["tutorial"] = {"id": "lysozyme", "variant": "protein_aqueous_standard",
                      "has_protein": True}
    s["hardware"] = {"cpu_count": 1, "gpu_ids": [], "ntomp": 1}
    state.write(tmp_path, s)

    def _fake_gw_run(args, cwd, **kwargs):
        if "grompp" in args:
            Path(cwd, args[args.index("-o") + 1]).write_text("fake-tpr")
        return GW.GmxResult(command=list(args), returncode=0, stdout="", stderr="",
                             classification="success")

    monkeypatch.setattr(GW, "run", _fake_gw_run)
    MR.run_phase(tmp_path, "nvt", {"reproducible_mode": True})

    s = state.read(tmp_path)
    prov = s["provenance"]
    assert "nvt" in prov["mdp_hashes"]
    assert len(prov["mdp_hashes"]["nvt"]) == 64  # sha256 hex length
    assert prov["seed"]["nvt"] == MDP.REPRODUCIBLE_SEED


# ---------------------------------------------------------------------------
# env_builder wiring: force field + ions mdp hash + gmx_version capture
# ---------------------------------------------------------------------------

def test_run_step1_topology_records_force_field(tmp_path, monkeypatch):
    from skills.env_builder import env_builder as EB

    _init(tmp_path)
    (tmp_path / "stage1_env").mkdir(exist_ok=True)
    (tmp_path / "inputs").mkdir(exist_ok=True)
    (tmp_path / "inputs" / "input.pdb").write_text("fake pdb\n")

    def _fake_gw_run(args, cwd, **kwargs):
        return GW.GmxResult(command=list(args), returncode=0, stdout="", stderr="",
                             classification="success")

    monkeypatch.setattr(GW, "run", _fake_gw_run)
    EB.run_step1_topology(tmp_path, "charmm36", "tip3p")
    s = state.read(tmp_path)
    assert s["provenance"]["force_field"] == "charmm36"


def test_collect_hardware_captures_provenance(tmp_path, monkeypatch):
    from skills.env_builder import env_builder as EB

    _init(tmp_path)
    monkeypatch.setattr(GW, "get_version", lambda: "2023.3")
    EB.collect_hardware(tmp_path)
    s = state.read(tmp_path)
    assert s["provenance"]["gmx_version"] == "2023.3"
    assert s["provenance"]["platform"]
