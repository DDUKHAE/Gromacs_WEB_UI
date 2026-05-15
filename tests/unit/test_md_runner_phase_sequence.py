# tests/unit/test_md_runner_phase_sequence.py
from skills.md_runner.md_runner import phase_sequence_for_variant


def test_standard_variant():
    assert phase_sequence_for_variant("protein_aqueous_standard") == \
        ["em", "nvt", "npt", "production"]


def test_membrane_variant_includes_two_npt_steps():
    seq = phase_sequence_for_variant("membrane_md_standard")
    assert "em" in seq and "production" in seq
    assert seq.count("npt") >= 2  # membrane needs two-stage barostat


def test_umbrella_variant_has_pulling_then_windows():
    seq = phase_sequence_for_variant("umbrella_sampling")
    assert "umbrella" in seq
    assert seq.index("em") < seq.index("umbrella")


def test_free_energy_variant_has_lambda_states():
    seq = phase_sequence_for_variant("free_energy_alchemical")
    assert "free_energy" in seq


def test_unknown_variant_falls_back_to_standard():
    assert phase_sequence_for_variant("nonexistent") == \
        ["em", "nvt", "npt", "production"]
