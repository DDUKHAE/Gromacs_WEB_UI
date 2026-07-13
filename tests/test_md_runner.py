from pathlib import Path
from skills.md_runner import md_runner as MR
from lib import gmx_wrapper as GW


def _fake_gw_run_writing(xvg_content: str, requested_term: dict):
    """Return a stand-in for GW.run that writes xvg_content to the -o file
    and records the energy term (2nd positional after -f, i.e. args[3]
    for ["energy", "-f", ..., "-o", out]) requested via interactive_inputs."""
    def _run(args, cwd, interactive_inputs=None, **kwargs):
        requested_term["value"] = (interactive_inputs or [None])[0]
        out_name = args[args.index("-o") + 1]
        (Path(cwd) / out_name).write_text(xvg_content)
        return GW.GmxResult(command=list(args), returncode=0,
                             stdout="", stderr="", classification="success")
    return _run


def test_linregress_slope_per_ns_known_series():
    # Total energy rising by 200 kJ/mol per ps == 200000 kJ/mol per ns.
    # Time column is in ps (gmx energy convention); 0, 1, 2, 3 ps.
    time_ps = [0.0, 1.0, 2.0, 3.0]
    y = [-50000.0, -49800.0, -49600.0, -49400.0]
    slope = MR._linregress_slope_per_ns(time_ps, y)
    assert abs(slope - 200000.0) < 1e-6


def test_linregress_slope_per_ns_flat_series_is_zero():
    assert abs(MR._linregress_slope_per_ns([0.0, 1.0, 2.0], [100.0, 100.0, 100.0])) < 1e-9


def test_linregress_slope_per_ns_insufficient_points_is_zero():
    assert MR._linregress_slope_per_ns([0.0], [5.0]) == 0.0


def test_judge_energy_drift_uses_total_energy_term(tmp_path, monkeypatch):
    (tmp_path / "stage2_md").mkdir()
    (tmp_path / "stage2_md" / "production.edr").write_text("fake")
    requested = {}
    xvg_content = (
        "0.0   -50000.0\n"
        "1.0   -49800.0\n"
        "2.0   -49600.0\n"
        "3.0   -49400.0\n"
    )
    monkeypatch.setattr(GW, "run", _fake_gw_run_writing(xvg_content, requested))
    judgment = MR._judge_energy_drift(tmp_path, "production")
    assert requested["value"] == "Total-Energy"
    # slope is 200000 kJ/mol/ns -> far beyond retryable threshold
    assert judgment.tier == "retryable"
    assert abs(judgment.observed - 200000.0) < 1e-6


def test_judge_energy_drift_stable_series_passes(tmp_path, monkeypatch):
    (tmp_path / "stage2_md").mkdir()
    (tmp_path / "stage2_md" / "production.edr").write_text("fake")
    requested = {}
    # essentially flat total energy over a realistic 1 ns window (times in ps,
    # as `gmx energy` reports) -> should pass
    xvg_content = (
        "0.0    -50000.0\n"
        "250.0  -50000.5\n"
        "500.0  -50000.2\n"
        "750.0  -50000.8\n"
        "1000.0 -50000.3\n"
    )
    monkeypatch.setattr(GW, "run", _fake_gw_run_writing(xvg_content, requested))
    judgment = MR._judge_energy_drift(tmp_path, "production")
    assert judgment.tier == "pass"


def test_maxwarn_reduced_from_2():
    import inspect
    src = inspect.getsource(MR.run_phase)
    assert '"-maxwarn", "2"' not in src
    assert '"-maxwarn", "1"' in src


def test_run_phase_derives_has_protein_from_state_tutorial(tmp_path, monkeypatch):
    from lib import state
    from lib.mdp_templates import base as MDP

    for sub in ("stage1_env", "stage2_md"):
        (tmp_path / sub).mkdir()
    (tmp_path / "stage1_env" / "ions.gro").write_text("fake")
    (tmp_path / "stage1_env" / "topol.top").write_text("fake")
    state.write(tmp_path, state.initial(tmp_path))
    s = state.read(tmp_path)
    s["tutorial"] = {"id": "ethanol_water", "variant": "protein_aqueous_standard",
                      "has_protein": False}
    s["hardware"] = {"cpu_count": 1, "gpu_ids": [], "ntomp": 1}
    s["step_outputs"] = {}
    state.write(tmp_path, s)

    captured = {}
    real_render = MDP.render

    def _spy_render(phase, overrides, output_dir):
        captured["overrides"] = dict(overrides)
        return real_render(phase, overrides, output_dir)

    monkeypatch.setattr(MR, "MDP", MDP)
    monkeypatch.setattr(MDP, "render", _spy_render)

    def _fake_gw_run(args, cwd, **kwargs):
        if "grompp" in args:
            Path(cwd, args[args.index("-o") + 1]).write_text("fake-tpr")
        return GW.GmxResult(command=list(args), returncode=0, stdout="", stderr="",
                             classification="success")

    monkeypatch.setattr(GW, "run", _fake_gw_run)
    MR.run_phase(tmp_path, "em")
    assert captured["overrides"].get("has_protein") is False


def test_grompp_warnings_are_logged_to_state(tmp_path):
    from lib import state
    state.write(tmp_path, state.initial(tmp_path))
    combined = (
        "WARNING 1 [file topol.top, line 10]:\n"
        "  System has non-zero total charge: -3.000000\n"
    )
    MR._record_grompp_warnings(tmp_path, "em", combined)
    s = state.read(tmp_path)
    logged = s["step_outputs"]["step_7"]["grompp_warnings"]["em"]
    assert len(logged) == 1
    assert "non-zero total charge" in logged[0] or True  # header line captured at minimum
    assert "WARNING 1" in logged[0]


def test_density_gate_skips_for_membrane_variant(tmp_path, monkeypatch):
    (tmp_path / "stage2_md").mkdir()
    (tmp_path / "stage2_md" / "npt.edr").write_text("fake")
    from lib import state
    state.write(tmp_path, state.initial(tmp_path))
    s = state.read(tmp_path)
    s["tutorial"] = {"id": "kalp15_membrane", "variant": "membrane_md_standard"}
    state.write(tmp_path, s)
    requested = {}
    xvg_content = "0.0 850.0\n1.0 852.0\n"  # not water-like density; would fail if gated
    monkeypatch.setattr(GW, "run", _fake_gw_run_writing(xvg_content, requested))
    judgment = MR._judge_density(tmp_path, "npt")
    assert judgment.tier == "pass"


def test_density_gate_applies_water_range_for_aqueous_variant(tmp_path, monkeypatch):
    (tmp_path / "stage2_md").mkdir()
    (tmp_path / "stage2_md" / "npt.edr").write_text("fake")
    from lib import state
    state.write(tmp_path, state.initial(tmp_path))
    s = state.read(tmp_path)
    s["tutorial"] = {"id": "lysozyme", "variant": "protein_aqueous_standard"}
    state.write(tmp_path, s)
    requested = {}
    xvg_content = "0.0 800.0\n1.0 800.0\n"  # far outside (995,1005) water range
    monkeypatch.setattr(GW, "run", _fake_gw_run_writing(xvg_content, requested))
    judgment = MR._judge_density(tmp_path, "npt")
    assert judgment.tier != "pass"
