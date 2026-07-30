from __future__ import annotations
import shutil
from pathlib import Path

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
