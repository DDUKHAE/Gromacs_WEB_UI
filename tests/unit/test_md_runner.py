from skills.md_runner.md_runner import phase_input_for


def test_virtual_sites_production_uses_em_output():
    assert phase_input_for("virtual_sites_topology", "production") == ("stage2_md", "em.gro")
