from __future__ import annotations
import shutil
import subprocess
import tempfile
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
    return list(SUPPORTED_LIPIDS)


def _leaflet_cmd(lipids: list[dict]) -> tuple[str, str]:
    """Return (names_str, ratios_str) for packmol-memgen --lipids / --ratio flags."""
    names = ":".join(e["name"] for e in lipids)
    total_frac = sum(e["fraction"] for e in lipids)
    raw = [e["fraction"] / total_frac * 100 for e in lipids]
    ints = [int(r) for r in raw]
    diff = 100 - sum(ints)
    if diff:
        ints[0] += diff
    ratios = ":".join(str(i) for i in ints)
    return names, ratios


def build_membrane(config: dict, workspace: Path) -> dict:
    """Run packmol-memgen to build a lipid bilayer system.

    config keys:
      lipids_upper: list[{name, fraction}]
      lipids_lower: list[{name, fraction}]
      protein_pdb: str (optional)
      protein_orientation: "opm"|"auto"|"manual"
      dist_nm: float (default 1.0)
      water_z_nm: float (default 2.0)
      salt_M: float (default 0.15)

    Returns:
      {"available": False, "gro": "", "top": ""}
      {"available": True, "gro": str, "top": str}
      {"available": True, "error": str, "gro": "", "top": ""}
    """
    if not is_packmol_memgen_available():
        return {"available": False, "gro": "", "top": ""}

    workspace = Path(workspace)

    upper = config.get("lipids_upper", [])
    lower = config.get("lipids_lower", [])

    for label, leaflet in (("lipids_upper", upper), ("lipids_lower", lower)):
        if leaflet:
            total = sum(e["fraction"] for e in leaflet)
            if abs(total - 1.0) > 0.001:
                raise ValueError(
                    f"{label} fractions must sum to 1.0, got {total:.4f}"
                )

    cmd = ["packmol-memgen"]

    protein_pdb = config.get("protein_pdb")
    if protein_pdb:
        cmd += ["--pdb", str(protein_pdb)]
        if config.get("protein_orientation") == "auto":
            cmd.append("--orient")

    upper_symmetric = upper == lower
    if upper_symmetric and upper:
        names, ratios = _leaflet_cmd(upper)
        cmd += ["--lipids", names, "--ratio", ratios]
    else:
        if upper:
            u_names, u_ratios = _leaflet_cmd(upper)
            cmd += ["--upper_lipids", u_names, "--upper_ratio", u_ratios]
        if lower:
            l_names, l_ratios = _leaflet_cmd(lower)
            cmd += ["--lower_lipids", l_names, "--lower_ratio", l_ratios]

    cmd += [
        "--dist",    str(config.get("dist_nm", 1.0)),
        "--water_z", str(config.get("water_z_nm", 2.0)),
        "--salt",    str(config.get("salt_M", 0.15)),
        "--notprotonate",
        "--nottrim",
        "--output",  "membrane_system",
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=tmpdir)

        gro_path = Path(tmpdir) / "membrane_system.gro"
        top_path = Path(tmpdir) / "membrane_system.top"

        if not gro_path.exists():
            return {
                "available": True,
                "gro": "",
                "top": "",
                "error": (proc.stderr or proc.stdout)[:500],
            }

        gro_content = gro_path.read_text()
        top_content = top_path.read_text() if top_path.exists() else ""

        (workspace / "membrane_system.gro").write_text(gro_content)
        if top_content:
            (workspace / "membrane_system.top").write_text(top_content)

        return {"available": True, "gro": gro_content, "top": top_content}
