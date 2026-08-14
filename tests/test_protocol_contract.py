import json

import pytest

from lib import protocol_contract as pc
from lib.mdp_templates import base as mdp


def test_contract_uses_manifest_defaults_and_hashes_grounding_docs(tmp_path):
    contract = pc.materialize(tmp_path, "Lysozyme_in_water")

    assert contract["locked_parameters"]["forcefield"] == "charmm36"
    assert contract["locked_parameters"]["box_type"] == "cubic"
    assert contract["phase_sequence"] == ["em", "nvt", "npt", "npt_pr", "production"]
    assert contract["grounding_documents"]
    assert {p["stage"] for p in contract["context_packs"]} == {
        "environment", "simulation", "analysis"
    }
    environment = tmp_path / "tutorial_context" / "environment.md"
    assert "Tutorial Context Pack: Lysozyme_in_water / environment" in environment.read_text()
    assert "Source SHA-256" in environment.read_text()
    assert len(contract["contract_sha256"]) == 64
    assert pc.assert_valid(tmp_path)["tutorial_id"] == "Lysozyme_in_water"


def test_contract_rejects_tampering(tmp_path):
    pc.materialize(tmp_path, "Lysozyme_in_water")
    path = tmp_path / pc.FILENAME
    payload = json.loads(path.read_text())
    payload["locked_parameters"]["forcefield"] = "oplsaa"
    path.write_text(json.dumps(payload))

    with pytest.raises(pc.ProtocolContractError, match="checksum mismatch"):
        pc.assert_valid(tmp_path)


def test_contract_rejects_changed_context_pack(tmp_path):
    pc.materialize(tmp_path, "Lysozyme_in_water")
    pack = tmp_path / "tutorial_context" / "simulation.md"
    pack.write_text(pack.read_text() + "untrusted instruction\n")

    with pytest.raises(pc.ProtocolContractError, match="context pack checksum mismatch"):
        pc.assert_valid(tmp_path)


def test_expert_config_is_applied_and_validated_in_rendered_mdp(tmp_path):
    (tmp_path / "system_config.json").write_text(json.dumps({
        "forcefield": {"name": "charmm36", "water_model": "tip3p"},
        "simulation": {
            "_expert_mode": True, "temperature_K": 310.0,
            "pressure_bar": 1.5, "dt_ps": 0.001,
            "thermostat": "V-rescale", "barostat": "Berendsen",
            "rcoulomb_nm": 1.2, "rvdw_nm": 1.2, "coulombtype": "PME",
            "constraints": "h-bonds", "constraint_algorithm": "LINCS",
            "pme_order": 4, "fourierspacing_nm": 0.16, "lincs_order": 4,
        },
    }))
    pc.materialize(tmp_path, "Lysozyme_in_water")
    out = tmp_path / "md"
    out.mkdir()
    rendered = mdp.render("npt", pc.phase_overrides(tmp_path, "npt"), out)

    assert "ref_t                    = 310.0 310.0" in rendered.read_text()
    assert "ref_p                    = 1.5" in rendered.read_text()
    assert pc.validate_rendered_mdp(tmp_path, rendered) == []
    # Fix 1 re-review: the membrane exception in phase_overrides must only
    # fire for the membrane variant. Pinning membrane=True unconditionally
    # (instead of reading contract["pipeline_variant"]) would silently move
    # every aqueous expert-mode npt off its deliberate Berendsen relaxation
    # stage onto Parrinello-Rahman -- and both suites would still pass,
    # because this test renders with the same overrides it validates, so the
    # barostat is self-consistent whatever the lock says. Assert the raw
    # locked value instead of round-tripping through render.
    assert pc.phase_overrides(tmp_path, "npt")["pcoupl"] == "Berendsen"


def test_expert_config_on_a_membrane_run_locks_parrinello_rahman_not_berendsen(tmp_path):
    """Task 8 review, Fix 1: PC.phase_overrides forced pcoupl="Berendsen" for
    every npt phase regardless of variant, so any expert-mode membrane run
    (any one of the 13 MDP_LOCK_MAP keys, e.g. temperature_K) collided with
    md_runner's own pcoupl="Parrinello-Rahman" override and died at npt with
    a StateContractError the retry machinery cannot recover from. A locked
    ref_p (pressure_bar) must also survive as the plain scalar that
    _same_mdp_value already knows how to compare against a doubled
    semiisotropic actual -- not get pre-joined into "X X" here.
    """
    (tmp_path / "system_config.json").write_text(json.dumps({
        "simulation": {"_expert_mode": True, "temperature_K": 310.0,
                       "pressure_bar": 2.0},
    }))
    pc.materialize(tmp_path, "KALP15_in_DPPC")
    out = tmp_path / "md"
    out.mkdir()

    overrides = pc.phase_overrides(tmp_path, "npt")
    assert overrides["pcoupl"] == "Parrinello-Rahman"
    assert overrides["ref_p"] == 2.0

    # The membrane render path (run_simulation's own branch, exercised via
    # md_runner) doubles a locked ref_p into the two-value semiisotropic
    # form; simulate that here the way md_runner.run_simulation does.
    overrides = dict(overrides)
    overrides["pcoupltype"] = "semiisotropic"
    ref_p = overrides.pop("ref_p")
    overrides["ref_p_list"] = f"{ref_p} {ref_p}"
    overrides["tc_grps"] = "Protein_DPPC Water_and_ions"
    rendered = mdp.render("npt", overrides, out)

    assert "pcoupl                   = Parrinello-Rahman" in rendered.read_text()
    assert "ref_p                    = 2.0 2.0" in rendered.read_text()
    assert pc.validate_rendered_mdp(tmp_path, rendered, "npt") == []


def test_contract_reports_changed_rendered_expert_parameter(tmp_path):
    (tmp_path / "system_config.json").write_text(json.dumps({
        "simulation": {"_expert_mode": True, "temperature_K": 310.0},
    }))
    pc.materialize(tmp_path, "Lysozyme_in_water")
    out = tmp_path / "md"
    out.mkdir()
    rendered = mdp.render("nvt", {"ref_t": 300.0}, out)

    errors = pc.validate_rendered_mdp(tmp_path, rendered)
    assert any("ref_t" in error for error in errors)
