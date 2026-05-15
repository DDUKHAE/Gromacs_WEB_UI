from pathlib import Path
from lib.mdp_templates import base as M


def test_render_em_defaults(tmp_path: Path):
    out = M.render("em", overrides={}, output_dir=tmp_path)
    content = out.read_text()
    assert "integrator" in content
    assert "steep" in content


def test_render_nvt_with_overrides(tmp_path: Path):
    out = M.render("nvt", overrides={"nsteps": 100000, "tau_t": 0.5},
                   output_dir=tmp_path)
    content = out.read_text()
    assert "nsteps                   = 100000" in content
    assert "tau_t                    = 0.5" in content


def test_render_ions(tmp_path: Path):
    out = M.render("ions", overrides={}, output_dir=tmp_path)
    assert out.exists()
    assert "integrator" in out.read_text()


def test_unknown_template_raises(tmp_path: Path):
    import pytest
    with pytest.raises(KeyError):
        M.render("nonexistent", overrides={}, output_dir=tmp_path)


def test_render_umbrella(tmp_path: Path):
    out = M.render("umbrella", overrides={"pull_coord_init": 0.5}, output_dir=tmp_path)
    text = out.read_text()
    assert "pull" in text
    assert "pull_coord1_init         = 0.5" in text


def test_render_free_energy(tmp_path: Path):
    out = M.render("free_energy",
                   overrides={"init_lambda_state": 3,
                              "vdw_lambdas": "0.0 0.25 0.5 0.75 1.0"},
                   output_dir=tmp_path)
    text = out.read_text()
    assert "free_energy" in text
    assert "init_lambda_state        = 3" in text
