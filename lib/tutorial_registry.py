import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

INDEX_PATH = Path("docs/tutorial/tutorial_index.json")


def load_index(index_path: Path = INDEX_PATH) -> dict[str, Any]:
    with open(index_path) as f:
        return json.load(f)


def get_entry(tutorial_id: str, index_path: Path = INDEX_PATH) -> dict[str, Any] | None:
    idx = load_index(index_path)
    for entry in idx["entries"]:
        if entry["id"] == tutorial_id:
            return entry
    return None


def load_manifest(tutorial_id: str,
                  index_path: Path = INDEX_PATH) -> dict[str, Any] | None:
    entry = get_entry(tutorial_id, index_path)
    if not entry:
        return None
    mp = entry.get("manifest_path")
    if not mp:
        return None
    p = Path(mp)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


@dataclass
class RoutingDecision:
    tutorial_id: str
    pipeline_variant: str | None
    confidence: str
    missing_inputs: list[str]
    unsupported_reason: str | None
    selected_docs: list[str]


KEYWORDS = {
    "Umbrella_Sampling": ["umbrella", "pmf", "pulling", "wham"],
    "Free_Energy_Calculations_Methane_in_Water": ["methane", "free energy"],
    "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol":
        ["ethanol", "hydration free energy"],
    "Building_Biphasic_Systems": ["biphasic", "interface", "two-phase"],
    "Virtual_Sites": ["virtual sites", "vsite", "linear molecule"],
    "Protein_Ligand_Complex": ["ligand", "protein-ligand", "complex", "binding"],
    "KALP15_in_DPPC": ["membrane", "dppc", "lipid", "bilayer"],
    "Lysozyme_in_water": ["protein in water", "aqueous", "water", "lysozyme"],
}


def _prompt_match(prompt: str) -> str | None:
    p = prompt.lower()
    for tid, keys in KEYWORDS.items():
        if any(k in p for k in keys):
            return tid
    return None


def _pdb_match(pdb_hints: dict[str, bool]) -> str:
    if pdb_hints.get("has_membrane"):
        return "KALP15_in_DPPC"
    if pdb_hints.get("has_ligand"):
        return "Protein_Ligand_Complex"
    return "Lysozyme_in_water"


def route(prompt: str, pdb_hints: dict[str, bool],
          prerequisites: dict[str, Any]) -> RoutingDecision:
    tid = _prompt_match(prompt) or _pdb_match(pdb_hints)
    entry = get_entry(tid)
    confidence = entry["confidence"] if entry else "low"
    if not _prompt_match(prompt):
        confidence = "low"

    if entry is None:
        raise ValueError(f"unknown tutorial: {tid}")
    required = set(entry["required_inputs"]) - {"protein_pdb"}
    provided = set(prerequisites.keys())
    # ligand_structure satisfied by ligand_itp too
    if "ligand_structure" in required and "ligand_itp" in provided:
        provided.add("ligand_structure")
    missing = sorted(required - provided)

    unsupported = None
    autonomy = entry.get("unsupported_autonomy_level") if entry else "none"
    if autonomy and autonomy != "none" and missing:
        unsupported = (f"{tid} requires manual prerequisites "
                       f"(missing: {missing})")

    docs = entry.get("recommended_docs", {}).get("minimal", []) if entry else []
    variant = None
    manifest = load_manifest(tid)
    if manifest:
        variant = manifest.get("pipeline_variant")

    return RoutingDecision(
        tutorial_id=tid,
        pipeline_variant=variant,
        confidence=confidence,
        missing_inputs=missing,
        unsupported_reason=unsupported,
        selected_docs=docs,
    )
