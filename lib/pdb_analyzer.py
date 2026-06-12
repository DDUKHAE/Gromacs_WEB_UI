from __future__ import annotations
import math
from pathlib import Path


class PDBAnalyzer:
    """Pure-Python PDB file analyzer. No external dependencies."""

    _CHARGE_MAP = {"ARG": 1, "LYS": 1, "ASP": -1, "GLU": -1}

    def __init__(self, pdb_path: str | Path):
        self._path = Path(pdb_path)
        self._lines = self._path.read_text().splitlines()

    def analyze(self) -> dict:
        chains: set[str] = set()
        residues: set[tuple] = set()
        atom_count = 0
        hetatm: dict[str, dict] = {}
        cys_sg: list[dict] = []
        altloc_seen: set[str] = set()
        altloc_residues: list[str] = []
        seqres: dict[str, int] = {}
        charged_seen: set[tuple] = set()
        net_charge = 0

        for line in self._lines:
            rec = line[:6].strip()

            if rec == "SEQRES":
                chain = line[11]
                count = int(line[13:17].strip() or 0)
                if chain not in seqres:
                    seqres[chain] = count

            elif rec == "ATOM":
                chain = line[21]
                resseq = line[22:26].strip()
                icode = line[26].strip()
                altloc = line[16].strip()
                resname = line[17:20].strip()
                atom_name = line[12:16].strip()

                chains.add(chain)
                residues.add((chain, resseq, icode))
                atom_count += 1

                if altloc:
                    key = f"{chain}:{resseq}"
                    if key not in altloc_seen:
                        altloc_seen.add(key)
                        altloc_residues.append(key)

                charged_key = (chain, resseq)
                if charged_key not in charged_seen and resname in self._CHARGE_MAP:
                    charged_seen.add(charged_key)
                    net_charge += self._CHARGE_MAP[resname]

                if resname == "CYS" and atom_name == "SG":
                    try:
                        x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
                        cys_sg.append({"chain": chain, "resseq": resseq, "x": x, "y": y, "z": z})
                    except ValueError:
                        pass

            elif rec == "HETATM":
                resname = line[17:20].strip()
                chain = line[21]
                if resname != "HOH":
                    key = f"{resname}:{chain}"
                    if key not in hetatm:
                        hetatm[key] = {"resname": resname, "chain": chain, "count": 0}
                    hetatm[key]["count"] += 1

        disulfide_candidates = self._find_disulfides(cys_sg)
        missing_residues = self._find_missing(seqres, residues)

        return {
            "chains": sorted(chains),
            "residue_count": len(residues),
            "atom_count": atom_count,
            "net_charge": net_charge,
            "hetatm": list(hetatm.values()),
            "missing_residues": missing_residues,
            "disulfide_candidates": disulfide_candidates,
            "altloc_residues": altloc_residues,
        }

    @staticmethod
    def _find_disulfides(cys_sg: list[dict]) -> list[dict]:
        candidates = []
        for i, c1 in enumerate(cys_sg):
            for c2 in cys_sg[i + 1:]:
                dist = math.sqrt(
                    (c1["x"] - c2["x"]) ** 2
                    + (c1["y"] - c2["y"]) ** 2
                    + (c1["z"] - c2["z"]) ** 2
                )
                if dist <= 2.5:
                    candidates.append({
                        "cys1": f"{c1['chain']}:{c1['resseq']}",
                        "cys2": f"{c2['chain']}:{c2['resseq']}",
                        "distance_angstrom": round(dist, 2),
                    })
        return candidates

    @staticmethod
    def _find_missing(seqres: dict[str, int], residues: set[tuple]) -> list[dict]:
        atom_by_chain: dict[str, set] = {}
        for (chain, resseq, icode) in residues:
            atom_by_chain.setdefault(chain, set()).add(resseq)

        missing = []
        for chain, total in seqres.items():
            atom_count = len(atom_by_chain.get(chain, set()))
            if total > atom_count:
                missing.append({
                    "chain": chain,
                    "seqres_count": total,
                    "atom_residue_count": atom_count,
                    "missing_count": total - atom_count,
                })
        return missing
