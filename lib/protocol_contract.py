"""Executable, versioned grounding contract for tutorial-driven MD runs.

The tutorial markdown remains useful context for an agent, but prose alone is
not an enforceable safety boundary.  This module compiles the selected
tutorial and explicit builder choices into a small immutable run artifact.
Skills validate the artifact before running and audits compare run outputs to
it afterwards.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lib import tutorial_registry as TR
from lib.system_config import load_config
from lib import run_plan as RP


FILENAME = "protocol_contract.json"
SCHEMA_VERSION = "1.0"
CONTEXT_DIRNAME = "tutorial_context"
_MAX_CHARS_PER_SOURCE = 6000

PHASE_SEQUENCE_BY_VARIANT = {
    "protein_aqueous_standard": ["em", "nvt", "npt", "production"],
    "membrane_md_standard": ["em", "nvt", "npt", "npt", "production"],
    "protein_ligand_complex": ["em", "nvt", "npt", "production"],
    "umbrella_sampling": ["em", "nvt", "npt", "umbrella"],
    "free_energy_alchemical": ["em", "nvt", "npt", "free_energy"],
    "biphasic_system": ["em", "nvt", "npt", "production"],
    "virtual_sites_topology": ["em", "production"],
}


class ProtocolContractError(RuntimeError):
    """A run does not have a valid, untampered protocol contract."""


def path(workspace: Path) -> Path:
    return Path(workspace) / FILENAME


def _sha256_file(file_path: Path) -> str:
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def _digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _docs_for_manifest(tutorial_id: str, manifest: dict[str, Any]) -> list[dict[str, str]]:
    root = Path("docs/tutorial") / tutorial_id
    docs = []
    for rel in sorted(set(manifest.get("documents", {}).values())):
        item = root / rel
        if item.exists():
            docs.append({"path": str(item), "sha256": _sha256_file(item)})
    manifest_path = root / "tutorial.manifest.json"
    if manifest_path.exists():
        docs.insert(0, {"path": str(manifest_path), "sha256": _sha256_file(manifest_path)})
    return docs


def _context_stage(document_key: str) -> str:
    """Map manifest document keys to the skill stage that consumes them."""
    if document_key.startswith(("step_1", "step_2", "step_3", "step_4", "step_5")):
        return "environment"
    if document_key.startswith(("step_6", "step_7")):
        return "simulation"
    if document_key.startswith("step_8"):
        return "analysis"
    return "environment"


def _render_context_pack(tutorial_id: str, stage: str,
                         sources: list[tuple[str, Path]]) -> str:
    """Create a bounded, cited Markdown context pack from tutorial sources."""
    lines = [
        f"# Tutorial Context Pack: {tutorial_id} / {stage}",
        "",
        "This is a derived, read-only excerpt of the versioned tutorial corpus.",
        "Follow the protocol contract for executable parameter values. If this pack",
        "and the contract disagree, stop and report the discrepancy rather than choosing.",
        "",
    ]
    for key, source in sources:
        body = source.read_text(encoding="utf-8", errors="replace")
        clipped = body[:_MAX_CHARS_PER_SOURCE]
        if len(body) > len(clipped):
            clipped += "\n\n[Excerpt truncated; consult the immutable source only for explanation, not new parameters.]\n"
        lines.extend([
            f"## Source: `{source}`", "",
            f"- Manifest key: `{key}`", f"- Source SHA-256: `{_sha256_file(source)}`", "",
            clipped.rstrip(), "",
        ])
    return "\n".join(lines) + "\n"


def _materialize_context_packs(workspace: Path, tutorial_id: str,
                               manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Write stage-specific derived packs and return their integrity metadata."""
    grouped: dict[str, list[tuple[str, Path]]] = {"environment": [], "simulation": [], "analysis": []}
    root = Path("docs/tutorial") / tutorial_id
    for key, rel in manifest.get("documents", {}).items():
        source = root / rel
        if source.exists():
            grouped[_context_stage(key)].append((key, source))
    context_dir = Path(workspace) / CONTEXT_DIRNAME
    context_dir.mkdir(parents=True, exist_ok=True)
    packs = []
    for stage, sources in grouped.items():
        if not sources:
            continue
        pack_path = context_dir / f"{stage}.md"
        pack_path.write_text(_render_context_pack(tutorial_id, stage, sources))
        packs.append({"stage": stage, "path": str(pack_path.relative_to(workspace)),
                      "sha256": _sha256_file(pack_path)})
    return packs


def compile_contract(workspace: Path, tutorial_id: str,
                     context_packs: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Compile tutorial defaults plus explicit System Builder choices.

    A system_config value is an explicit user choice and therefore overrides a
    tutorial default.  Generic web-form defaults deliberately do *not*
    override a selected tutorial: otherwise selecting e.g. an OPLS tutorial
    silently turns into CHARMM merely because the HTML form has a default.
    """
    manifest = TR.load_manifest(tutorial_id)
    if manifest is None:
        raise ProtocolContractError(f"unknown tutorial for protocol contract: {tutorial_id}")
    defaults = manifest.get("defaults", {})
    plan = RP.assert_valid(workspace)
    config = load_config(workspace) or {}
    ff = config.get("forcefield", {})
    box = config.get("box", {})
    ions = config.get("ions", {})
    sim = config.get("simulation", {})

    locked = (plan or {}).get("user_locked_settings") or {
        "forcefield": ff.get("name", defaults.get("forcefield")),
        "water_model": ff.get("water_model", defaults.get("water_model")),
        "box_type": box.get("type", defaults.get("box_type")),
        "box_distance_nm": box.get("edge_distance_nm", defaults.get("box_distance_nm")),
        "ion_concentration_M": ions.get("concentration_M", 0.15),
        "neutralize": ions.get("neutralize", True),
    }
    # Only explicitly enabled expert controls are locked.  This prevents an
    # agent from inventing a parameter while leaving normal tutorial defaults
    # free to evolve with the versioned MDP templates.
    mdp = {}
    if plan is not None:
        mapping = {
            "temperature_K": "ref_t", "pressure_bar": "ref_p", "dt_ps": "dt",
            "thermostat": "tcoupl", "barostat": "pcoupl", "rcoulomb_nm": "rcoulomb",
            "rvdw_nm": "rvdw", "coulombtype": "coulombtype", "constraints": "constraints",
            "constraint_algorithm": "constraint_algorithm", "pme_order": "pme_order",
            "fourierspacing_nm": "fourierspacing", "lincs_order": "lincs_order",
        }
        mdp = {output: plan["user_locked_mdp_settings"][key]
               for key, output in mapping.items() if key in plan["user_locked_mdp_settings"]}
    elif sim.get("_expert_mode"):
        mapping = {
            "temperature_K": "ref_t", "pressure_bar": "ref_p",
            "dt_ps": "dt", "thermostat": "tcoupl", "barostat": "pcoupl",
            "rcoulomb_nm": "rcoulomb", "rvdw_nm": "rvdw",
            "coulombtype": "coulombtype", "constraints": "constraints",
            "constraint_algorithm": "constraint_algorithm", "pme_order": "pme_order",
            "fourierspacing_nm": "fourierspacing", "lincs_order": "lincs_order",
        }
        mdp = {out: sim[key] for key, out in mapping.items() if key in sim}

    contract = {
        "schema_version": SCHEMA_VERSION,
        "tutorial_id": tutorial_id,
        "pipeline_variant": manifest.get("pipeline_variant"),
        "validation_profile": manifest.get("validation_profile"),
        "architecture_steps": manifest.get("architecture_steps", []),
        "phase_sequence": PHASE_SEQUENCE_BY_VARIANT.get(manifest.get("pipeline_variant"), []),
        "locked_parameters": locked,
        "locked_mdp_parameters": mdp,
        "grounding_documents": _docs_for_manifest(tutorial_id, manifest),
        "context_packs": context_packs or [],
        "run_plan": ({"path": RP.FILENAME, "sha256": plan["plan_sha256"]} if plan else None),
    }
    contract["contract_sha256"] = _digest(contract)
    return contract


def materialize(workspace: Path, tutorial_id: str) -> dict[str, Any]:
    workspace = Path(workspace)
    manifest = TR.load_manifest(tutorial_id)
    if manifest is None:
        raise ProtocolContractError(f"unknown tutorial for protocol contract: {tutorial_id}")
    packs = _materialize_context_packs(workspace, tutorial_id, manifest)
    contract = compile_contract(workspace, tutorial_id, context_packs=packs)
    path(workspace).write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    return contract


def load(workspace: Path) -> dict[str, Any] | None:
    contract_path = path(workspace)
    if not contract_path.exists():
        return None
    return json.loads(contract_path.read_text())


def assert_valid(workspace: Path) -> dict[str, Any] | None:
    """Return a verified contract, or raise when its digest was altered."""
    contract = load(workspace)
    if contract is None:
        return None
    recorded = contract.pop("contract_sha256", None)
    actual = _digest(contract)
    contract["contract_sha256"] = recorded
    if not recorded or recorded != actual:
        raise ProtocolContractError("protocol contract checksum mismatch")
    workspace = Path(workspace)
    for pack in contract.get("context_packs", []):
        relative = Path(pack.get("path", ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ProtocolContractError("invalid context pack path in protocol contract")
        pack_path = workspace / relative
        if not pack_path.is_file() or _sha256_file(pack_path) != pack.get("sha256"):
            raise ProtocolContractError(f"context pack checksum mismatch: {relative}")
    plan_ref = contract.get("run_plan")
    if plan_ref:
        plan = RP.assert_valid(workspace)
        if plan is None or plan_ref.get("sha256") != plan.get("plan_sha256"):
            raise ProtocolContractError("resolved run plan checksum mismatch")
    return contract


def render_prompt(workspace: Path) -> str:
    """Render the machine-readable contract as a concise, auditable prompt."""
    contract = assert_valid(workspace)
    if contract is None:
        return ""
    locked = contract["locked_parameters"]
    docs = "\n".join(f"- {d['path']} (sha256={d['sha256'][:12]}…)"
                     for d in contract["grounding_documents"])
    packs = "\n".join(f"- {p['stage']}: {Path(workspace) / p['path']} (sha256={p['sha256'][:12]}…)"
                      for p in contract.get("context_packs", []))
    lines = [
        "",
        "[EXECUTABLE TUTORIAL PROTOCOL CONTRACT — DO NOT OVERRIDE]",
        f"- Tutorial: {contract['tutorial_id']} ({contract['pipeline_variant']})",
        f"- Contract SHA-256: {contract['contract_sha256']}",
        f"- Force field: {locked['forcefield']}; water: {locked['water_model']}",
        f"- Box: {locked['box_type']}; distance: {locked['box_distance_nm']} nm",
        f"- Ions: {locked['ion_concentration_M']} M; neutralize={locked['neutralize']}",
        f"- Required phases: {' → '.join(contract['phase_sequence'])}",
        f"- User settings are authoritative; tutorial differences are recorded as compatibility warnings, not silent overrides.",
        "- Grounding documents (read these exact versions):",
        docs or "- tutorial manifest only",
        "- Stage-specific context packs: read `environment` before build_environment,",
        "  `simulation` before run_simulation, and `analysis` before illustrate:",
        packs or "- no derived context pack available",
        "- Do not substitute another tutorial, force field, water model, box, or phase sequence.",
        "- Do not run raw gmx commands or create ad-hoc scripts; use the three skill entry points.",
        "- If an unsupported case needs literature evidence, do not search or alter the contract yourself;",
        "  stop and request a PaperQA evidence-only escalation for operator approval.",
        "",
    ]
    if contract["locked_mdp_parameters"]:
        lines.insert(-2, f"- Locked MDP parameters: {json.dumps(contract['locked_mdp_parameters'], sort_keys=True)}")
    return "\n".join(lines)


def _parse_mdp(mdp_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in Path(mdp_path).read_text().splitlines():
        line = raw.split(";", 1)[0].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().replace("-", "_").lower()] = value.strip()
    return values


def _same_mdp_value(expected: Any, actual: str) -> bool:
    """Compare MDP scalars while tolerating case and repeated group values."""
    exp = str(expected).strip().lower()
    values = actual.strip().lower().split()
    if not values:
        return False
    if all(value == exp for value in values):
        return True
    try:
        return all(abs(float(value) - float(exp)) < 1e-10 for value in values)
    except ValueError:
        return False


def validate_rendered_mdp(workspace: Path, mdp_path: Path) -> list[str]:
    """Return contract violations in an MDP rendered for this workspace."""
    contract = assert_valid(workspace)
    if not contract or not contract["locked_mdp_parameters"]:
        return []
    actual = _parse_mdp(mdp_path)
    errors = []
    for key, expected in contract["locked_mdp_parameters"].items():
        observed = actual.get(key)
        # Not every expert control is meaningful in every phase (e.g. a
        # barostat is intentionally absent from NVT and EM).  Validate the
        # parameters rendered by that phase; the contract prevents a changed
        # value without incorrectly demanding a barostat in NVT.
        if observed is None:
            continue
        elif not _same_mdp_value(expected, observed):
            errors.append(f"locked MDP parameter {key}={observed!r}, expected {expected!r}")
    return errors


def phase_overrides(workspace: Path, phase: str) -> dict[str, Any]:
    """Return enforced expert settings applicable to an MDP phase."""
    contract = assert_valid(workspace)
    if not contract:
        return {}
    values = dict(contract["locked_mdp_parameters"])
    if phase == "em":
        return {}
    if phase == "nvt":
        values.pop("pcoupl", None)
        values.pop("ref_p", None)
    elif phase not in ("npt", "production"):
        # Current special-workflow templates do not expose the standard
        # expert fields.  They remain tutorial-locked, not silently applied.
        return {}
    return values
