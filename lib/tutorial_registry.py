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


# ── System Type × Protocol axis (browser wizard routing layer) ──────────────
# Independent of the free-text route() above. Maps the 2-step System
# Type / Protocol picker in the browser onto the existing fixed tutorial_id
# presets. Membrane systems are deliberately excluded — they use the
# separate /api/membrane/* pipeline, not this matrix.

SYSTEM_TYPES = [
    {"id": "aqueous_protein", "label": "Aqueous Protein / Peptide"},
    {"id": "protein_ligand_complex", "label": "Protein-Ligand Complex"},
    {"id": "small_molecule_solution", "label": "Small Molecule / Solution System"},
]

PROTOCOLS = [
    {"id": "standard_md", "label": "Standard Equilibrium & Production MD"},
    {"id": "umbrella_sampling", "label": "Pulling & Umbrella Sampling"},
    {"id": "alchemical_fe", "label": "Alchemical Free Energy Calculation"},
    {"id": "virtual_sites", "label": "Virtual Sites / High-Timestep MD"},
]

# (system_type_id, protocol_id) -> [tutorial_id, ...]. A missing key means
# the combination is not supported yet.
COMBO_MATRIX: dict[tuple[str, str], list[str]] = {
    ("aqueous_protein", "standard_md"): ["Lysozyme_in_water"],
    ("protein_ligand_complex", "standard_md"): ["Protein_Ligand_Complex"],
    ("aqueous_protein", "umbrella_sampling"): ["Umbrella_Sampling"],
    ("small_molecule_solution", "standard_md"): ["Building_Biphasic_Systems"],
    ("small_molecule_solution", "alchemical_fe"): [
        "Free_Energy_Calculations_Methane_in_Water",
        "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol",
    ],
    ("small_molecule_solution", "virtual_sites"): ["Virtual_Sites"],
}


def resolve_tutorial_id(system_type: str, protocol: str,
                        tutorial_id_hint: str | None = None) -> str | None:
    """Resolve a (system_type, protocol) pair to a tutorial_id.

    Returns None if the combination is not in COMBO_MATRIX. If the cell
    has more than one tutorial_id (currently only the Free Energy cell)
    and `tutorial_id_hint` names one of them, that one is returned;
    otherwise the first entry in the cell is the default.
    """
    candidates = COMBO_MATRIX.get((system_type, protocol))
    if not candidates:
        return None
    if tutorial_id_hint and tutorial_id_hint in candidates:
        return tutorial_id_hint
    return candidates[0]


def combo_matrix_response() -> dict:
    """JSON-serializable payload for GET /api/system-protocol-matrix."""
    combos = [
        {"system_type": st, "protocol": pr, "tutorial_ids": tids}
        for (st, pr), tids in COMBO_MATRIX.items()
    ]
    return {"system_types": SYSTEM_TYPES, "protocols": PROTOCOLS, "combos": combos}
