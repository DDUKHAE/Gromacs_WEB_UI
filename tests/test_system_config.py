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
    assert len(errors) == 1
    assert "ph" in errors[0].lower()


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
    assert len(errors) == 1
    assert "dt_ps" in errors[0]


def test_invalid_rcoulomb_returns_error():
    errors = validate_solution_config({"simulation": {"rcoulomb_nm": 5.0}})
    assert len(errors) == 1
    assert "rcoulomb_nm" in errors[0]


def test_invalid_coulombtype_returns_error():
    errors = validate_solution_config({"simulation": {"coulombtype": "Reaction-Field"}})
    assert len(errors) == 1


def test_invalid_constraints_returns_error():
    errors = validate_solution_config({"simulation": {"constraints": "all-angles"}})
    assert len(errors) == 1


def test_invalid_pme_order_returns_error():
    errors = validate_solution_config({"simulation": {"pme_order": 3}})
    assert len(errors) == 1
    assert "pme_order" in errors[0]


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


def test_ph_boundary_values_are_valid():
    assert validate_solution_config({"protonation": {"ph": 0.0}}) == []
    assert validate_solution_config({"protonation": {"ph": 14.0}}) == []

# ── membrane config validation ─────────────────────────────────────────────

def test_valid_membrane_config():
    config = {
        "build_type": "membrane",
        "membrane": {
            "lipids_upper": [{"name": "POPC", "fraction": 0.7}, {"name": "CHL1", "fraction": 0.3}],
            "lipids_lower": [{"name": "POPC", "fraction": 0.7}, {"name": "CHL1", "fraction": 0.3}],
            "water_z_nm": 2.0,
            "salt_M": 0.15,
        }
    }
    assert validate_solution_config(config) == []


def test_membrane_fraction_sum_not_1_returns_error():
    config = {
        "membrane": {
            "lipids_upper": [{"name": "POPC", "fraction": 0.5}, {"name": "POPE", "fraction": 0.3}],
            "lipids_lower": [{"name": "POPC", "fraction": 1.0}],
        }
    }
    errors = validate_solution_config(config)
    assert len(errors) == 1
    assert "upper" in errors[0].lower()


def test_membrane_water_z_out_of_range_returns_error():
    config = {"membrane": {"water_z_nm": 6.0}}
    errors = validate_solution_config(config)
    assert len(errors) == 1
    assert "water_z_nm" in errors[0]


def test_membrane_salt_out_of_range_returns_error():
    config = {"membrane": {"salt_M": 3.0}}
    errors = validate_solution_config(config)
    assert len(errors) == 1
    assert "salt_M" in errors[0]


def test_constraint_prompt_includes_membrane_block():
    config = {
        "build_type": "membrane",
        "membrane": {
            "lipids_upper": [{"name": "POPC", "fraction": 0.7}, {"name": "CHL1", "fraction": 0.3}],
            "lipids_lower": [{"name": "POPC", "fraction": 0.6}, {"name": "CHL1", "fraction": 0.4}],
            "water_z_nm": 2.0,
            "salt_M": 0.15,
        }
    }
    prompt = build_constraint_prompt(config)
    assert "MEMBRANE BUILDER" in prompt
    assert "POPC" in prompt
    assert "CHL1" in prompt
    assert "2.0 nm" in prompt


# ── ligand config validation ───────────────────────────────────────────────

def test_valid_ligand_config():
    config = {
        "build_type": "ligand",
        "ligand": {
            "residue_name": "LIG",
            "net_charge": 0,
            "atom_type": "gaff2",
        }
    }
    assert validate_solution_config(config) == []


def test_ligand_net_charge_out_of_range_returns_error():
    errors = validate_solution_config({"ligand": {"net_charge": 15}})
    assert len(errors) == 1
    assert "net_charge" in errors[0]


def test_ligand_residue_name_too_long_returns_error():
    errors = validate_solution_config({"ligand": {"residue_name": "TOOLONG"}})
    assert len(errors) == 1
    assert "residue_name" in errors[0]


def test_ligand_invalid_atom_type_returns_error():
    errors = validate_solution_config({"ligand": {"atom_type": "opls"}})
    assert len(errors) == 1
    assert "atom_type" in errors[0]


def test_constraint_prompt_includes_ligand_block():
    config = {
        "build_type": "ligand",
        "ligand": {
            "residue_name": "LIG",
            "net_charge": -1,
            "atom_type": "gaff2",
            "itp_file": "LIG.itp",
        }
    }
    prompt = build_constraint_prompt(config)
    assert "LIGAND CONSTRAINTS" in prompt
    assert "LIG" in prompt
    assert "gaff2" in prompt.lower()
    assert "LIG.itp" in prompt
