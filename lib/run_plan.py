"""Compile browser inputs into a user-authoritative MD execution plan."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lib import tutorial_registry as TR
from lib.system_config import load_config


FILENAME = "resolved_run_plan.json"
SCHEMA_VERSION = "1.0"


class RunPlanError(RuntimeError):
    pass


def path(workspace: Path) -> Path:
    return Path(workspace) / FILENAME


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _pdb_hints(pdb_path: Path) -> dict[str, bool]:
    text = Path(pdb_path).read_text(encoding="utf-8", errors="replace")
    solvent = {"HOH", "WAT", "SOL", "NA", "CL", "MG", "CA", "K", "ZN"}
    return {
        "has_protein": any(line.startswith("ATOM") for line in text.splitlines()),
        "has_membrane": any(token in text for token in ("DPPC", "POPC", "DMPC", "DOPC")),
        "has_ligand": any(line.startswith("HETATM") and line[17:20].strip() not in solvent
                          for line in text.splitlines()),
    }


def _provided_inputs(config: dict[str, Any]) -> set[str]:
    provided = {"protein_pdb"}
    ligand = config.get("ligand", {})
    if ligand.get("itp_file") or ligand.get("complex_gro") or ligand.get("residue_name"):
        provided.update({"ligand_structure", "ligand_topology"})
    membrane = config.get("membrane", {})
    if membrane.get("lipids_upper") or membrane.get("lipids_lower"):
        provided.add("membrane_composition")
    return provided


def _select_tutorial(requested_id: str | None, config: dict[str, Any], pdb_path: Path) -> tuple[str, str]:
    if requested_id:
        manifest = TR.load_manifest(requested_id)
        if manifest is None:
            raise RunPlanError(f"unknown tutorial: {requested_id}")
        return requested_id, "selected"
    builder_type = config.get("build_type") or config.get("builder_type")
    if builder_type == "membrane" or config.get("membrane"):
        return "KALP15_in_DPPC", "auto"
    if builder_type == "ligand" or config.get("ligand"):
        return "Protein_Ligand_Complex", "auto"
    decision = TR.route("", _pdb_hints(pdb_path), {key: True for key in _provided_inputs(config)})
    return decision.tutorial_id, "auto"


def compile_plan(workspace: Path, pdb_path: Path,
                 requested_tutorial_id: str | None = None) -> dict[str, Any]:
    workspace = Path(workspace)
    config = load_config(workspace) or {}
    tutorial_id, tutorial_mode = _select_tutorial(requested_tutorial_id, config, pdb_path)
    entry = TR.get_entry(tutorial_id)
    manifest = TR.load_manifest(tutorial_id)
    if entry is None or manifest is None:
        raise RunPlanError(f"tutorial registry is incomplete: {tutorial_id}")
    defaults = manifest.get("defaults", {})
    ff, box, ions, sim = (config.get("forcefield", {}), config.get("box", {}),
                          config.get("ions", {}), config.get("simulation", {}))
    locked = {
        "forcefield": ff.get("name") or defaults.get("forcefield"),
        "water_model": ff.get("water_model") or defaults.get("water_model"),
        "box_type": box.get("type") or defaults.get("box_type"),
        "box_distance_nm": box.get("edge_distance_nm", defaults.get("box_distance_nm")),
        "ion_concentration_M": ions.get("concentration_M", 0.15),
        "neutralize": ions.get("neutralize", True),
    }
    expected = {"forcefield": defaults.get("forcefield"), "water_model": defaults.get("water_model"),
                "box_type": defaults.get("box_type"), "box_distance_nm": defaults.get("box_distance_nm")}
    compatibility = []
    for field, tutorial_value in expected.items():
        user_value = locked[field]
        if tutorial_value is not None and user_value != tutorial_value:
            compatibility.append({"field": field, "user_value": user_value,
                                  "tutorial_recommendation": tutorial_value,
                                  "severity": "warning", "policy": "experimental_override"})
    required = set(entry.get("required_inputs", [])) - {"protein_pdb"}
    missing = sorted(required - _provided_inputs(config))
    status = "blocked" if missing else ("warning" if compatibility else "pass")
    plan = {
        "schema_version": SCHEMA_VERSION,
        "tutorial": {"id": tutorial_id, "mode": tutorial_mode,
                     "pipeline_variant": manifest.get("pipeline_variant"),
                     "validation_profile": manifest.get("validation_profile")},
        "user_locked_settings": locked,
        "user_locked_mdp_settings": ({
            key: sim[key] for key in ("temperature_K", "pressure_bar", "dt_ps", "thermostat", "barostat",
            "rcoulomb_nm", "rvdw_nm", "coulombtype", "constraints", "constraint_algorithm",
            "pme_order", "fourierspacing_nm", "lincs_order") if key in sim
        } if sim.get("_expert_mode") else {}),
        "required_inputs": sorted(required), "missing_inputs": missing,
        "compatibility": {"status": status, "items": compatibility},
        "execution_policy": {"raw_shell": False,
                             "allowed_entry_points": ["build_environment", "run_simulation", "illustrate"]},
    }
    plan["plan_sha256"] = _digest(plan)
    return plan


def materialize(workspace: Path, pdb_path: Path,
                requested_tutorial_id: str | None = None) -> dict[str, Any]:
    plan = compile_plan(workspace, pdb_path, requested_tutorial_id)
    path(workspace).write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    return plan


def load(workspace: Path) -> dict[str, Any] | None:
    plan_path = path(workspace)
    return json.loads(plan_path.read_text()) if plan_path.exists() else None


def assert_valid(workspace: Path) -> dict[str, Any] | None:
    plan = load(workspace)
    if plan is None:
        return None
    recorded = plan.pop("plan_sha256", None)
    actual = _digest(plan)
    plan["plan_sha256"] = recorded
    if not recorded or recorded != actual:
        raise RunPlanError("resolved run plan checksum mismatch")
    return plan
