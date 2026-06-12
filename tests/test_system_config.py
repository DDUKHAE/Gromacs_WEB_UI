import pytest
from lib.system_config import validate_solution_config, build_constraint_prompt, load_config
from pathlib import Path
import json


# ── validate_solution_config ──────────────────────────────────────────────────

def test_empty_config_is_valid():
    assert validate_solution_config({}) == []


def test_valid_full_config_is_valid():
    config = {
        "forcefield": {"name": "charmm36-jul2022", "water_model": "tip3p"},
        "box": {"type": "dodecahedron", "edge_distance_nm": 1.0},
        "ions": {"salt_type": "NaCl", "concentration_M": 0.15, "neutralize": True},
        "simulation": {
            "_expert_mode": True,
            "temperature_K": 300,
            "pressure_bar": 1.0,
            "sim_time_ns": 1.0,
            "thermostat": "V-rescale",
            "barostat": "Parrinello-Rahman",
        },
    }
    assert validate_solution_config(config) == []


def test_invalid_box_type_returns_error():
    errors = validate_solution_config({"box": {"type": "hexagonal"}})
    assert len(errors) == 1
    assert "box type" in errors[0].lower()


def test_edge_distance_too_small_returns_error():
    errors = validate_solution_config({"box": {"edge_distance_nm": 0.1}})
    assert any("edge_distance_nm" in e for e in errors)


def test_edge_distance_too_large_returns_error():
    errors = validate_solution_config({"box": {"edge_distance_nm": 9.9}})
    assert any("edge_distance_nm" in e for e in errors)


def test_concentration_out_of_range_returns_error():
    errors = validate_solution_config({"ions": {"concentration_M": 5.0}})
    assert any("concentration_M" in e for e in errors)


def test_temperature_too_low_returns_error():
    errors = validate_solution_config({"simulation": {"temperature_K": 50}})
    assert any("temperature_K" in e for e in errors)


def test_temperature_too_high_returns_error():
    errors = validate_solution_config({"simulation": {"temperature_K": 600}})
    assert any("temperature_K" in e for e in errors)


def test_invalid_thermostat_returns_error():
    errors = validate_solution_config({"simulation": {"thermostat": "Langevin"}})
    assert any("thermostat" in e.lower() for e in errors)


def test_invalid_barostat_returns_error():
    errors = validate_solution_config({"simulation": {"barostat": "MonteCarloMembrane"}})
    assert any("barostat" in e.lower() for e in errors)


# ── build_constraint_prompt ──────────────────────────────────────────────────

def test_constraint_prompt_has_header():
    prompt = build_constraint_prompt({})
    assert "SYSTEM BUILDER CONSTRAINTS" in prompt


def test_constraint_prompt_includes_forcefield_name():
    config = {"forcefield": {"name": "charmm36-jul2022"}}
    assert "charmm36-jul2022" in build_constraint_prompt(config)


def test_constraint_prompt_includes_box_info():
    config = {"box": {"type": "dodecahedron", "edge_distance_nm": 1.2}}
    prompt = build_constraint_prompt(config)
    assert "dodecahedron" in prompt
    assert "1.2" in prompt


def test_constraint_prompt_includes_ions():
    config = {"ions": {"salt_type": "KCl", "concentration_M": 0.1, "neutralize": True}}
    prompt = build_constraint_prompt(config)
    assert "KCl" in prompt
    assert "0.1" in prompt


def test_constraint_prompt_excludes_sim_params_when_not_expert():
    config = {"simulation": {"_expert_mode": False, "temperature_K": 400}}
    prompt = build_constraint_prompt(config)
    assert "400" not in prompt


def test_constraint_prompt_includes_sim_params_when_expert():
    config = {"simulation": {"_expert_mode": True, "temperature_K": 350, "sim_time_ns": 2.0}}
    prompt = build_constraint_prompt(config)
    assert "350" in prompt
    assert "2.0" in prompt


# ── load_config ──────────────────────────────────────────────────────────────

def test_load_config_returns_none_when_absent(tmp_path):
    assert load_config(tmp_path) is None


def test_load_config_returns_dict_when_present(tmp_path):
    data = {"version": "1.0", "builder_type": "solution"}
    (tmp_path / "system_config.json").write_text(json.dumps(data))
    result = load_config(tmp_path)
    assert result == data

# ── protonation validation ──────────────────────────────────────────────────────

def test_valid_protonation_config():
    config = {
        "protonation": {
            "ph": 7.0,
            "his_states": {"A:15": "HSD"},
            "disulfide_bridges": [["A:6", "A:127"]],
        }
    }
    assert validate_solution_config(config) == []


def test_ph_out_of_range_returns_error():
    errors = validate_solution_config({"protonation": {"ph": 15.0}})
    assert any("ph" in e.lower() for e in errors)


def test_invalid_his_state_returns_error():
    errors = validate_solution_config({"protonation": {"his_states": {"A:15": "INVALID"}}})
    assert len(errors) == 1


# ── extended MDP validation ────────────────────────────────────────────────────

def test_valid_extended_mdp_config():
    config = {
        "simulation": {
            "dt_ps": 0.002,
            "rcoulomb_nm": 1.0,
            "rvdw_nm": 1.0,
            "coulombtype": "PME",
            "pme_order": 4,
            "fourierspacing_nm": 0.16,
            "constraints": "all-bonds",
            "constraint_algorithm": "LINCS",
            "lincs_order": 4,
        }
    }
    assert validate_solution_config(config) == []


def test_invalid_dt_returns_error():
    errors = validate_solution_config({"simulation": {"dt_ps": 0.1}})
    assert any("dt_ps" in e for e in errors)


def test_invalid_rcoulomb_returns_error():
    errors = validate_solution_config({"simulation": {"rcoulomb_nm": 5.0}})
    assert any("rcoulomb_nm" in e for e in errors)


def test_invalid_coulombtype_returns_error():
    errors = validate_solution_config({"simulation": {"coulombtype": "Reaction-Field"}})
    assert len(errors) == 1


def test_invalid_constraints_returns_error():
    errors = validate_solution_config({"simulation": {"constraints": "all-angles"}})
    assert len(errors) == 1


def test_invalid_pme_order_returns_error():
    errors = validate_solution_config({"simulation": {"pme_order": 3}})
    assert any("pme_order" in e for e in errors)


# ── build_constraint_prompt v1.1 ───────────────────────────────────────────────

def test_constraint_prompt_includes_protonation():
    config = {
        "protonation": {
            "ph": 7.0,
            "his_states": {"A:15": "HSD"},
            "disulfide_bridges": [["A:6", "A:127"]],
        }
    }
    prompt = build_constraint_prompt(config)
    assert "pH: 7.0" in prompt
    assert "A:15=HSD" in prompt
    assert "A:6-A:127" in prompt


def test_constraint_prompt_includes_extended_mdp():
    config = {
        "simulation": {
            "_expert_mode": True,
            "temperature_K": 300,
            "dt_ps": 0.002,
            "coulombtype": "PME",
            "constraints": "all-bonds",
        }
    }
    prompt = build_constraint_prompt(config)
    assert "0.002 ps" in prompt
    assert "PME" in prompt
    assert "all-bonds" in prompt
