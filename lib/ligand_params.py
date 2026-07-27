from __future__ import annotations
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

_PENALTY_RE = re.compile(r"Total\s+charge.*?penalty[:\s]+([0-9.]+)", re.IGNORECASE)


def is_acpype_available() -> bool:
    return shutil.which("acpype") is not None


def run_acpype(
    ligand_path: Path,
    charge: int = 0,
    atom_type: str = "gaff2",
    residue_name: str = "LIG",
) -> dict:
    """Run ACPYPE to generate GAFF2 parameters for a small-molecule ligand.

    Returns:
      {"available": False, "itp": "", "gro": "", "posre": "", "penalty": 0.0}
          when acpype not installed
      {"available": True, "itp": str, "gro": str, "posre": str, "penalty": float}
          on success
      {"available": True, "error": str, "itp": "", "gro": "", "posre": "", "penalty": 0.0}
          on tool failure
    """
    if not is_acpype_available():
        return {"available": False, "itp": "", "gro": "", "posre": "", "penalty": 0.0}

    ligand_path = Path(ligand_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_lig = Path(tmpdir) / ligand_path.name
        shutil.copy(ligand_path, tmp_lig)

        cmd = [
            "acpype",
            "-i", str(tmp_lig),
            "-n", str(charge),
            "-a", atom_type,
            "-r", residue_name,
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=tmpdir)

        stem = tmp_lig.stem
        acpype_dir = Path(tmpdir) / f"{stem}.acpype"

        if not acpype_dir.exists():
            return {
                "available": True,
                "error": (proc.stderr or proc.stdout)[:500],
                "itp": "", "gro": "", "posre": "", "penalty": 0.0,
            }

        itp_files = list(acpype_dir.glob("*GMX.itp"))
        gro_files = list(acpype_dir.glob("*.gro"))
        posre_files = list(acpype_dir.glob("posre*.itp"))

        itp = itp_files[0].read_text() if itp_files else ""
        gro = gro_files[0].read_text() if gro_files else ""
        posre = posre_files[0].read_text() if posre_files else ""

        penalty = 0.0
        m = _PENALTY_RE.search(proc.stdout)
        if m:
            try:
                penalty = float(m.group(1))
            except ValueError:
                pass

        return {"available": True, "itp": itp, "gro": gro, "posre": posre, "penalty": penalty}


def _parse_gro(text: str) -> tuple[str, list[str], str]:
    """Parse GRO content. Returns (title, atom_lines, box_line)."""
    lines = text.splitlines()
    title = lines[0]
    atom_lines = lines[2:-1]
    box_line = lines[-1]
    return title, atom_lines, box_line


def _renumber_gro_atoms(atom_lines: list[str], start_atom: int, start_res: int) -> list[str]:
    """Re-number atom and residue indices in GRO atom lines."""
    result = []
    prev_res_num = None
    res_offset = start_res - 1
    atom_num = start_atom
    for line in atom_lines:
        if len(line) < 20:
            result.append(line)
            continue
        res_num_str = line[:5]
        try:
            orig_res = int(res_num_str)
        except ValueError:
            result.append(line)
            continue
        if prev_res_num is None:
            res_offset = start_res - orig_res
        prev_res_num = orig_res
        new_res = (orig_res + res_offset) % 100000
        new_atom = atom_num % 100000
        new_line = f"{new_res:5d}{line[5:15]}{new_atom:5d}{line[20:]}"
        result.append(new_line)
        atom_num += 1
    return result


def assemble_complex(
    protein_gro: Path,
    ligand_gro: Path,
    ligand_itp: Path,
    topol_top: Path,
    workspace: Path,
    ligand_prm: Path | None = None,
) -> dict:
    """Merge protein GRO + ligand GRO and update topol.top.

    Returns {"complex_gro": str, "topol_top": str}.
    Files are also written to workspace.
    """
    protein_gro = Path(protein_gro)
    ligand_gro = Path(ligand_gro)
    ligand_itp = Path(ligand_itp)
    topol_top = Path(topol_top)
    workspace = Path(workspace)

    p_title, p_atoms, p_box = _parse_gro(protein_gro.read_text())
    _, l_atoms, _ = _parse_gro(ligand_gro.read_text())

    p_last_atom = len(p_atoms)
    p_last_res = int(p_atoms[-1][:5].strip()) if p_atoms else 0
    l_atoms_renumbered = _renumber_gro_atoms(l_atoms, p_last_atom + 1, p_last_res + 1)

    total_atoms = len(p_atoms) + len(l_atoms)
    combined_lines = [
        f"{p_title} + LIG",
        f"{total_atoms:5d}",
        *p_atoms,
        *l_atoms_renumbered,
        p_box,
    ]
    complex_gro = "\n".join(combined_lines) + "\n"

    top_text = topol_top.read_text()
    itp_name = ligand_itp.name

    if ligand_prm is not None and ligand_prm.exists():
        prm_name = ligand_prm.name
        if f'#include "{prm_name}"' not in top_text:
            # CGenFF bonded parameters must be read after the parent CHARMM
            # force field but before any molecule type definitions.
            marker = '#include "charmm36.ff/forcefield.itp"'
            if marker in top_text:
                top_text = top_text.replace(marker, marker + f'\n#include "{prm_name}"', 1)
            else:
                top_text = f'#include "{prm_name}"\n' + top_text
    if f'#include "{itp_name}"' not in top_text:
        top_text = top_text.replace(
            "[ system ]",
            f'#include "{itp_name}"\n\n[ system ]',
        )

    if "\nLIG " not in top_text and "\nLIG\t" not in top_text:
        if "[ molecules ]" in top_text:
            top_text = top_text.rstrip() + "\nLIG              1\n"

    complex_gro_path = workspace / "complex.gro"
    complex_gro_path.write_text(complex_gro)
    new_top_path = workspace / "topol_complex.top"
    new_top_path.write_text(top_text)

    shutil.copy2(ligand_itp, workspace / itp_name)
    if ligand_prm is not None and ligand_prm.exists():
        shutil.copy2(ligand_prm, workspace / ligand_prm.name)

    return {"complex_gro": complex_gro, "topol_top": top_text}
