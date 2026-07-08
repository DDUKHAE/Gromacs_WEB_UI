from lib.mdp_templates import base as MDP


def test_nvt_defaults_to_protein_non_protein_when_has_protein_true(tmp_path):
    out = MDP.render("nvt", {"has_protein": True}, output_dir=tmp_path)
    text = out.read_text()
    assert "tc-grps                  = Protein Non-Protein" in text
    assert "tau_t                    = 0.1 0.1" in text
    assert "ref_t                    = 300.0 300.0" in text


def test_nvt_uses_system_group_when_no_protein(tmp_path):
    out = MDP.render("nvt", {"has_protein": False}, output_dir=tmp_path)
    text = out.read_text()
    assert "tc-grps                  = System" in text
    assert "Protein Non-Protein" not in text
    assert "tau_t                    = 0.1" in text
    assert "tau_t                    = 0.1 0.1" not in text


def test_npt_uses_system_group_when_no_protein(tmp_path):
    out = MDP.render("npt", {"has_protein": False}, output_dir=tmp_path)
    text = out.read_text()
    assert "tc-grps                  = System" in text


def test_production_uses_system_group_when_no_protein(tmp_path):
    out = MDP.render("production", {"has_protein": False}, output_dir=tmp_path)
    text = out.read_text()
    assert "tc-grps                  = System" in text


def test_has_protein_defaults_true_when_unspecified(tmp_path):
    out = MDP.render("nvt", {}, output_dir=tmp_path)
    assert "Protein Non-Protein" in out.read_text()


def test_explicit_tc_grps_override_wins(tmp_path):
    out = MDP.render("nvt", {"tc_grps": "Membrane Water"}, output_dir=tmp_path)
    text = out.read_text()
    assert "tc-grps                  = Membrane Water" in text
    assert "tau_t                    = 0.1 0.1" in text  # two groups -> two values


def test_npt_default_barostat_is_berendsen_not_parrinello_rahman(tmp_path):
    out = MDP.render("npt", {}, output_dir=tmp_path)
    text = out.read_text()
    assert "pcoupl                   = Berendsen" in text
    assert "Parrinello-Rahman" not in text


def test_production_default_barostat_is_parrinello_rahman(tmp_path):
    out = MDP.render("production", {}, output_dir=tmp_path)
    text = out.read_text()
    assert "pcoupl                   = Parrinello-Rahman" in text


def test_umbrella_and_free_energy_still_use_system_unaffected(tmp_path):
    # Regression guard: FE/umbrella templates were already correct and must
    # not be touched by the tc-grps parameterization.
    out = MDP.render("umbrella", {}, output_dir=tmp_path)
    assert "tc-grps                  = System" in out.read_text()
