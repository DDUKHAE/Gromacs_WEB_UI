import pytest

from lib import state
from lib import gmx_wrapper as GW
from skills.env_builder import env_builder as EB


def _init(ws):
    ws.mkdir(exist_ok=True)
    (ws / "stage1_env").mkdir(exist_ok=True)
    state.write(ws, state.initial(ws))


def _fake_gw_run(responses):
    """responses: dict keyed by first arg (command name) -> GmxResult kwargs."""
    def _run(args, cwd, interactive_inputs=None, **kwargs):
        cmd = args[0]
        resp = responses[cmd]
        return GW.GmxResult(command=list(args), returncode=resp.get("returncode", 0),
                             stdout=resp.get("stdout", ""), stderr=resp.get("stderr", ""),
                             classification=resp.get("classification", "success"))
    return _run


def test_step4_parses_nonzero_charge_warning(tmp_path, monkeypatch):
    _init(tmp_path)
    grompp_stderr = (
        "WARNING 1 [file topol.top, line 10]:\n"
        "  System has non-zero total charge: -3.000000\n"
    )
    monkeypatch.setattr(GW, "run", _fake_gw_run({
        "grompp": {"stderr": grompp_stderr},  # returncode 0: within -maxwarn budget
    }))
    EB.run_step4_ions_prep(tmp_path)
    s = state.read(tmp_path)
    assert s["step_outputs"]["step_4"]["initial_net_charge"] == -3.0


def test_step4_defaults_to_zero_charge_when_no_warning(tmp_path, monkeypatch):
    _init(tmp_path)
    monkeypatch.setattr(GW, "run", _fake_gw_run({"grompp": {}}))
    EB.run_step4_ions_prep(tmp_path)
    s = state.read(tmp_path)
    assert s["step_outputs"]["step_4"]["initial_net_charge"] == 0.0


def _seed_step4(ws, initial_net_charge):
    s = state.read(ws)
    s["step_outputs"]["step_4"] = {"initial_net_charge": initial_net_charge}
    (ws / "stage1_env" / "topol.top").write_text("; fake topology\n")
    state.write(ws, s)


def test_step5_computes_real_net_charge_not_hardcoded_zero(tmp_path, monkeypatch):
    _init(tmp_path)
    _seed_step4(tmp_path, initial_net_charge=-3.0)
    monkeypatch.setattr(GW, "run", _fake_gw_run({
        "genion": {"stdout": "Will try to add 3 NA ions and 0 CL ions.\n"},
    }))
    EB.run_step5_genion(tmp_path)
    s = state.read(tmp_path)
    step5 = s["step_outputs"]["step_5"]
    # -3.0 + 3 NA (+1 each) - 0 CL == 0.0, properly neutralized
    assert step5["net_charge"] == 0.0
    assert step5["neutrality_tier"] == "pass"


def test_step5_fatal_charge_raises_and_blocks_pipeline(tmp_path, monkeypatch):
    _init(tmp_path)
    _seed_step4(tmp_path, initial_net_charge=-3.0)
    # genion only adds 1 NA -> residual net charge -2.0 -> fatal (> 0.5 tol)
    monkeypatch.setattr(GW, "run", _fake_gw_run({
        "genion": {"stdout": "Will try to add 1 NA ions and 0 CL ions.\n"},
    }))
    with pytest.raises(RuntimeError, match="neutralization gate FATAL"):
        EB.run_step5_genion(tmp_path)
    s = state.read(tmp_path)
    # current_step must NOT have advanced past the gate on fatal charge
    assert s["current_step"] != 5 or s["last_completed_stage"] != "env"


def test_step5_never_hardcodes_net_charge_to_zero_source(tmp_path):
    import inspect
    src = inspect.getsource(EB.run_step5_genion)
    assert '"net_charge": 0.0' not in src


def test_select_tutorial_records_has_protein_false_for_ethanol(tmp_path):
    _init(tmp_path)
    pdb = tmp_path / "input.pdb"
    pdb.write_text("HETATM    1  C1  ETH A   1       0.000   0.000   0.000\n")
    EB.select_tutorial(
        tmp_path, pdb, prompt="ethanol solvation",
        prerequisites={"solute_topology": "eth.itp",
                        "coulomb_vdw_lambda_schedule": "0 0.5 1"})
    s = state.read(tmp_path)
    assert s["tutorial"]["has_protein"] is False


def test_select_tutorial_records_has_protein_true_for_lysozyme(tmp_path):
    _init(tmp_path)
    pdb = tmp_path / "input.pdb"
    pdb.write_text(
        "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n"
    )
    EB.select_tutorial(tmp_path, pdb, prompt="lysozyme in water", prerequisites={})
    s = state.read(tmp_path)
    assert s["tutorial"]["has_protein"] is True
