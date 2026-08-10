"""Building the KALP-15/DPPC system, following the tutorial's InflateGRO route.

Reproduces `docs/tutorial/KALP15_in_DPPC/define_box_and_solvate/` and the
reference script `tutorial_data/KALP15_in_DPPC/run_inflategro.sh`. Intermediate
file names match that script so its output can be compared step for step.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lib import berger_forcefield as BFF
from lib import gmx_wrapper as GW
from lib import gro_file
from lib import inflate_gro
from lib.mdp_templates import base as MDP

#: DPPC's experimental area per lipid in the liquid-crystalline phase at 323 K.
TARGET_APL = 0.64
#: The reference script needs 26; this only has to stop a runaway loop.
MAX_SHRINK_ITERATIONS = 40
#: 27 minimisations each writing several files would otherwise leave hundreds
#: of #file.N# backups in stage1_env.
GMX_ENV = {"GMX_MAXBACKUP": "-1"}

#: Every grompp against gromos53a6_lipid.ff raises exactly two warnings: the
#: GROMOS twin-range cut-off notice (which the tutorial's own -maxwarn 1
#: covers), and a "Bondtype LJ-14 was defined previously" from merging
#: lipid.itp's [pairtypes] into ffnonbonded.itp. Both are expected, so every
#: grompp here allows two -- the reference script's plain `gmx grompp` aborts
#: with "Too many warnings (2)".
GROMPP_MAXWARN = "2"

#: The tutorial's own minim_inflategro.mdp settings: a plain cut-off at 1.2 nm
#: rather than PME. Not cosmetic -- the system carries KALP-15's +4 e with no
#: counter-ions until solvation, and Ewald with a net charge is a warning that
#: must stay fatal for the runs after genion, so it cannot be waved through with
#: a higher -maxwarn. The tutorial switches back to PME in minim.mdp once the
#: system is solvated and neutralised.
PACKING_MDP = {"coulombtype": "cutoff", "rcoulomb": 1.2, "rvdw": 1.2}

_GRO_RESNAME = slice(5, 10)
_GRO_RESID = slice(0, 5)
_PDB_RESNAME = slice(17, 20)
_PDB_RESID = slice(21, 27)


class MembraneAssemblyError(Exception):
    pass


def _stage(workspace: Path) -> Path:
    return Path(workspace) / "stage1_env"


def _run(workspace: Path, args: list[str], **kwargs: Any):
    """GW.run with the assembly's environment and the run's log."""
    # Merged, not setdefault: a caller passing its own env must not silently
    # lose GMX_MAXBACKUP and bury stage1_env under #file.N# backups.
    kwargs["env"] = {**GMX_ENV, **(kwargs.get("env") or {})}
    result = GW.run(args, cwd=_stage(workspace),
                    progress_log=Path(workspace) / "runner.log", **kwargs)
    if not result.ok:
        raise MembraneAssemblyError(
            f"gmx {args[0]} failed [{result.classification}]: {result.stderr[-500:]}"
        )
    return result


def residue_counts(path: Path) -> dict[str, int]:
    """Residues per name, counted by (residue number, name) pairs.

    Handles both `.gro` and `.pdb`: the pre-equilibrated bilayer is
    distributed as a PDB, where the residue is called DPP because the format
    allows only three characters.
    """
    path = Path(path)
    if path.suffix.lower() == ".pdb":
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
                 if ln.startswith(("ATOM", "HETATM"))]
        name_at, id_at = _PDB_RESNAME, _PDB_RESID
    else:
        lines = gro_file.read(path).atoms
        name_at, id_at = _GRO_RESNAME, _GRO_RESID
    seen: dict[str, set[str]] = {}
    for line in lines:
        seen.setdefault(line[name_at].strip(), set()).add(line[id_at])
    return {name: len(ids) for name, ids in seen.items()}


def write_dppc_topology(workspace: Path, bilayer_gro: Path, out: Path) -> dict[str, int]:
    """A lipid-and-water-only topology for the first grompp.

    The tutorial ships one with `DPPC 128 / SOL 3655` hardcoded and warns it
    "serves no other purpose and you should not use it in any remaining step".
    Counting instead keeps a different bilayer working.
    """
    counts = residue_counts(bilayer_gro)
    lipid = counts.get("DPPC") or counts.get("DPP")
    if not lipid:
        raise MembraneAssemblyError(
            f"{bilayer_gro} holds no DPPC residues; found {sorted(counts)}"
        )
    lines = [
        "; Generated for the DPPC-only grompp of the membrane assembly.",
        "; Used once, to build a .tpr for trjconv -pbc mol. Not used again.",
        "",
        '#include "gromos53a6_lipid.ff/forcefield.itp"',
        '#include "dppc.itp"',
        '#include "gromos53a6_lipid.ff/spc.itp"',
        '#include "gromos53a6_lipid.ff/ions.itp"',
        "",
        "[ system ]",
        "DPPC bilayer",
        "",
        "[ molecules ]",
        "; molecule name  nr.",
        f"DPPC {lipid}",
    ]
    water = counts.get("SOL")
    if water:
        lines.append(f"SOL {water}")
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"DPPC": lipid, **({"SOL": water} if water else {})}


def prepare_bilayer(workspace: Path) -> Path:
    """Make the bilayer's molecules whole and normalise its residue names.

    Passing the coordinates through a .tpr does two things: it removes
    periodicity, and it renames the residue DPP (the PDB three-character limit)
    to DPPC, which is the name inflategro is given later.
    """
    stage = _stage(workspace)
    bilayer_pdb = _require(Path(workspace) / "inputs" / "dppc128.pdb")
    topol_dppc = stage / "topol_dppc.top"
    write_dppc_topology(workspace, bilayer_pdb, topol_dppc)

    mdp = MDP.render("em", dict(PACKING_MDP), stage)
    _run(workspace, ["grompp", "-f", mdp.name, "-c", str(bilayer_pdb),
                     "-p", topol_dppc.name, "-o", "dppc.tpr",
                     "-maxwarn", GROMPP_MAXWARN])
    _run(workspace, ["trjconv", "-s", "dppc.tpr", "-f", str(bilayer_pdb),
                     "-o", "dppc128_whole.gro", "-pbc", "mol", "-ur", "compact"],
         interactive_inputs=["0"])
    return _require(stage / "dppc128_whole.gro")


def place_peptide(workspace: Path, bilayer_whole: Path) -> Path:
    """Centre the peptide inside the bilayer's unit cell."""
    stage = _stage(workspace)
    box = gro_file.box_vectors(gro_file.read(bilayer_whole))
    _run(workspace, ["editconf", "-f", "processed.gro", "-o", "KALP_newbox.gro",
                     "-c", "-box", f"{box[0]:.5f}", f"{box[1]:.5f}", f"{box[2]:.5f}"])
    return _require(stage / "KALP_newbox.gro")


def merge_system(workspace: Path, peptide_gro: Path, bilayer_whole: Path) -> Path:
    """Concatenate peptide and bilayer into one coordinate file."""
    stage = _stage(workspace)
    peptide = gro_file.read(peptide_gro)
    bilayer = gro_file.read(bilayer_whole)
    merged = gro_file.concat(peptide, bilayer, "KALP-15 in DPPC")
    expected = len(peptide.atoms) + len(bilayer.atoms)
    if len(merged.atoms) != expected:
        raise MembraneAssemblyError(
            f"merge produced {len(merged.atoms)} atoms, expected {expected}"
        )
    out = stage / "system.gro"
    gro_file.write(out, merged)
    return out


def install_strong_restraints(workspace: Path, peptide_gro: Path) -> Path:
    """Generate the InflateGRO restraints and switch them on in the topology."""
    stage = _stage(workspace)
    BFF.add_ifdef_block(stage / "topol.top", "STRONG_POSRES", "strong_posre.itp")
    _run(workspace, ["genrestr", "-f", peptide_gro.name, "-o", "strong_posre.itp",
                     "-fc", "100000", "100000", "100000"],
         interactive_inputs=["0"])
    return _require(stage / "strong_posre.itp")


def inflate_once(workspace: Path, system_gro: Path) -> inflate_gro.InflateResult:
    """Inflate by 4 and record the lipids that were dropped.

    The lipids overlapping the peptide are deleted by the P-CA cutoff, and
    `[ molecules ]` must be corrected to match or the next grompp fails on an
    atom-count mismatch.
    """
    stage = _stage(workspace)
    result = inflate_gro.inflate(
        script=_script(workspace, "inflategro.pl"),
        gro=system_gro, scale=4.0, resname="DPPC", cutoff_a=14,
        out=stage / "system_inflated.gro", gridsize=5,
        area_dat=stage / "area.dat", cwd=stage,
    )
    if result.removed:
        topol = stage / "topol.top"
        expected = _lipid_count(topol) - result.removed
        try:
            BFF.set_molecule_count(topol, "DPPC", expected)
        except BFF.BergerForceFieldError as exc:
            raise MembraneAssemblyError(
                f"inflategro deleted {result.removed} lipids but [molecules] "
                f"could not be updated: {exc}"
            ) from exc
        # Read the file back rather than trusting the write: an unmodified
        # [ molecules ] is fatal, not something the next grompp should discover.
        if _lipid_count(topol) != expected:
            raise MembraneAssemblyError(
                f"[molecules] DPPC is {_lipid_count(topol)}, expected {expected} "
                f"after inflategro deleted {result.removed} lipids"
            )
    return result


def minimise(workspace: Path, gro: Path, tag: str) -> Path:
    """Energy-minimise with the peptide held by STRONG_POSRES, then unwrap.

    `-r` is passed explicitly: since GROMACS 2018 position restraints need a
    reference structure, and md_runner's automatic `-r` only triggers on
    `-DPOSRES`.
    """
    stage = _stage(workspace)
    mdp = MDP.render("em", {**PACKING_MDP, "define": "-DSTRONG_POSRES"}, stage)
    _run(workspace, ["grompp", "-f", mdp.name, "-c", gro.name, "-r", gro.name,
                     "-p", "topol.top", "-o", f"{tag}.tpr",
                     "-maxwarn", GROMPP_MAXWARN])
    _run(workspace, ["mdrun", "-deffnm", tag])
    out = _require(stage / f"{tag}.gro")
    _run(workspace, ["trjconv", "-s", f"{tag}.tpr", "-f", out.name,
                     "-o", "tmp.gro", "-pbc", "mol"],
         interactive_inputs=["0"])
    tmp = _require(stage / "tmp.gro")
    tmp.replace(out)
    return out


def _lipid_count(topol: Path) -> int:
    body = Path(topol).read_text(encoding="utf-8", errors="replace")
    section = re.search(r"^\[\s*molecules\s*\]\s*$(.*)", body, re.M | re.S)
    if section is None:
        raise MembraneAssemblyError(f"{topol} has no [ molecules ] section")
    row = re.search(r"^[ \t]*DPPC[ \t]+(\d+)[ \t]*$", section.group(1), re.M)
    if row is None:
        raise MembraneAssemblyError(f"{topol} [ molecules ] has no DPPC row")
    return int(row.group(1))


def _script(workspace: Path, name: str) -> Path:
    for candidate in (Path(workspace) / "inputs" / name, Path(workspace) / name):
        if candidate.is_file():
            return candidate
    raise MembraneAssemblyError(f"{name} not found under {workspace}/inputs")


def _require(path: Path) -> Path:
    if not Path(path).is_file():
        raise MembraneAssemblyError(f"expected file was not produced: {path}")
    return Path(path)
