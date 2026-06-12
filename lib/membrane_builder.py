from __future__ import annotations
import shutil
from pathlib import Path

SUPPORTED_LIPIDS: list[dict] = [
    {"name": "POPC", "full_name": "1-palmitoyl-2-oleoyl-sn-glycero-3-phosphocholine",   "charge": 0,  "description": "Generic PC bilayer"},
    {"name": "POPE", "full_name": "1-palmitoyl-2-oleoyl-sn-glycero-3-phosphoethanolamine", "charge": 0, "description": "PE component"},
    {"name": "POPS", "full_name": "1-palmitoyl-2-oleoyl-sn-glycero-3-phospho-L-serine", "charge": -1, "description": "Anionic, charge −1"},
    {"name": "DPPC", "full_name": "1,2-dipalmitoyl-sn-glycero-3-phosphocholine",         "charge": 0,  "description": "Gel-phase studies"},
    {"name": "DPPE", "full_name": "1,2-dipalmitoyl-sn-glycero-3-phosphoethanolamine",    "charge": 0,  "description": "Saturated PE"},
    {"name": "DPPS", "full_name": "1,2-dipalmitoyl-sn-glycero-3-phospho-L-serine",       "charge": -1, "description": "Saturated PS"},
    {"name": "CHL1", "full_name": "Cholesterol",                                          "charge": 0,  "description": "Raft, fluidity modulation"},
    {"name": "PSM",  "full_name": "Palmitoyl sphingomyelin",                              "charge": 0,  "description": "Raft domains"},
]


def is_packmol_memgen_available() -> bool:
    return shutil.which("packmol-memgen") is not None


def list_supported_lipids() -> list[dict]:
    return SUPPORTED_LIPIDS
