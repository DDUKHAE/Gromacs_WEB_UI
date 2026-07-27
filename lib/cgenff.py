"""CGenFF-to-GROMACS conversion for the CHARMM36 ligand workflow."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lib.gmx_wrapper import get_gmxlib, run as run_gmx


def converter_path() -> Path | None:
    configured = os.environ.get("CGENFF_CONVERTER", "")
    if configured and Path(configured).is_file():
        return Path(configured)
    found = shutil.which("cgenff_charmm2gmx.py")
    return Path(found) if found else None


def is_available() -> bool:
    return converter_path() is not None


def charmm_forcefield_dir(name: str = "charmm36") -> Path | None:
    root = get_gmxlib()
    candidate = Path(root) / f"{name}.ff" if root else None
    return candidate if candidate and (candidate / "forcefield.itp").is_file() else None


def convert(mol2: Path, stream: Path, residue_name: str, forcefield: str = "charmm36") -> dict[str, str]:
    """Return CGenFF-derived .itp/.prm and a GROMACS ligand coordinate file."""
    converter, ff_dir = converter_path(), charmm_forcefield_dir(forcefield)
    if converter is None:
        raise RuntimeError("CGenFF converter unavailable; set CGENFF_CONVERTER to cgenff_charmm2gmx.py")
    if ff_dir is None:
        raise RuntimeError(f"CHARMM36 force field '{forcefield}.ff' is unavailable in GMXLIB")
    residue_name = residue_name.upper()
    if not residue_name.isalnum() or not 1 <= len(residue_name) <= 3:
        raise ValueError("residue name must be 1–3 alphanumeric characters")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        mol2_copy, str_copy = work / "ligand.mol2", work / "ligand.str"
        shutil.copy(mol2, mol2_copy)
        shutil.copy(stream, str_copy)
        result = subprocess.run([sys.executable, str(converter), residue_name,
                                 mol2_copy.name, str_copy.name, str(ff_dir)],
                                cwd=work, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout)[-1000:])
        itp, prm, initial = (next(iter(work.glob("*.itp")), None),
                             next(iter(work.glob("*.prm")), None),
                             next(iter(work.glob("*_ini.pdb")), None))
        if not (itp and prm and initial):
            raise RuntimeError("CGenFF converter did not produce .itp, .prm, and *_ini.pdb files")
        gmx = run_gmx(["editconf", "-f", initial.name, "-o", "ligand.gro"], cwd=work)
        gro = work / "ligand.gro"
        if not gmx.ok or not gro.exists():
            raise RuntimeError(f"GROMACS editconf failed: {gmx.stderr[-500:]}")
        return {"itp": itp.read_text(), "prm": prm.read_text(), "gro": gro.read_text()}
