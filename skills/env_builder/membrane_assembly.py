"""Building the KALP-15/DPPC system, following the tutorial's InflateGRO route.

Reproduces `docs/tutorial/KALP15_in_DPPC/define_box_and_solvate/` and the
reference script `tutorial_data/KALP15_in_DPPC/run_inflategro.sh`. Intermediate
file names match that script so its output can be compared step for step.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lib import berger_forcefield as BFF
from lib import gmx_wrapper as GW
from lib import gro_file
from lib import inflate_gro
from lib import state
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

#: grompp reports the pre-genion charge as a WARNING; its absence means the
#: system was already neutral.
_NET_CHARGE_RE = re.compile(r"non-zero total charge:\s*(-?\d+(?:\.\d+)?)",
                            re.IGNORECASE)

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


def add_lipid_molecules(workspace: Path, bilayer_whole: Path) -> int:
    """Add the bilayer's lipids to `[ molecules ]`: the tutorial's "add DPPC".

    pdb2gmx wrote a peptide-only topology, so without this row every later
    grompp sees 138 atoms of topology against a 6,438-atom system. The count is
    read off the bilayer rather than hardcoded to 128, like `write_dppc_topology`.
    """
    topol = _stage(workspace) / "topol.top"
    count = residue_counts(bilayer_whole).get("DPPC", 0)
    if not count:
        raise MembraneAssemblyError(
            f"{bilayer_whole} holds no DPPC residues to add to {topol}"
        )
    text = topol.read_text(encoding="utf-8", errors="replace")
    section = re.search(r"^\[\s*molecules\s*\]\s*$(.*)", text, re.M | re.S)
    if section is None:
        raise MembraneAssemblyError(f"{topol} has no [ molecules ] section")
    if re.search(r"^[ \t]*\[", section.group(1), re.M):
        raise MembraneAssemblyError(
            f"{topol} has a section after [ molecules ]; cannot append DPPC"
        )
    if re.search(r"^[ \t]*DPPC[ \t]+\d+[ \t]*$", section.group(1), re.M):
        BFF.set_molecule_count(topol, "DPPC", count)  # resumed run
    else:
        topol.write_text(text.rstrip("\n") + f"\nDPPC {count}\n", encoding="utf-8")
    return count


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


@dataclass
class ShrinkResult:
    final_gro: Path
    iterations: int
    apl_total: float
    apl_history: list[float]
    target_apl: float


def shrink_to_target(workspace: Path, inflated_em: Path,
                     target_apl: float = TARGET_APL,
                     max_iterations: int = MAX_SHRINK_ITERATIONS) -> ShrinkResult:
    """Shrink by 0.95 and minimise until the area per lipid reaches the target.

    The tutorial says to "repeat shrinking and EM iterations until the area per
    lipid reaches an appropriate value", and its reference script hardcodes 26
    (which lands at 0.698 nm^2, still above TARGET_APL). Stopping on the
    measured APL instead takes one further iteration on the real system --
    27, confirmed against real gmx -- and would track a different target APL
    or degree of inflation without a hardcoded count to retune. `resname` is
    still fixed to "DPPC", matching `inflate_once`, so this does not adapt to
    a different lipid.
    """
    stage = _stage(workspace)
    script = _script(workspace, "inflategro.pl")
    source = Path(inflated_em)
    history: list[float] = []

    for n in range(1, max_iterations + 1):
        result = inflate_gro.inflate(
            script=script, gro=source, scale=0.95, resname="DPPC", cutoff_a=0,
            out=stage / f"system_shrink{n}.gro", gridsize=5,
            area_dat=stage / f"area_shrink{n}.dat", cwd=stage,
        )
        history.append(result.apl_total)
        minimised = minimise(workspace, result.output, f"system_shrink{n}_em")
        if result.apl_total <= target_apl:
            return ShrinkResult(final_gro=minimised, iterations=n,
                                apl_total=result.apl_total,
                                apl_history=history, target_apl=target_apl)
        source = minimised

    last = f"{history[-1]:.4g}" if history else "n/a"
    raise MembraneAssemblyError(
        f"area per lipid did not reach {target_apl} nm^2 in {max_iterations} "
        f"shrink iterations; last value {last}, history {history}"
    )


_GROUP_HEADER_RE = re.compile(r"^\s*\[\s*(.+?)\s*\]\s*$")


def parse_index_groups(path: Path) -> dict[str, int]:
    """Atom count per group in an `.ndx` file."""
    groups: dict[str, int] = {}
    current: str | None = None
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        header = _GROUP_HEADER_RE.match(line)
        if header:
            current = header.group(1)
            groups.setdefault(current, 0)
            continue
        if current is not None:
            groups[current] += len(line.split())
    return groups


def _upsert_sol_count(topol: Path, count: int) -> None:
    """Add or correct the `[ molecules ]` SOL row.

    `solvate` and `genion` maintain this themselves via `-p`. `water_deletor.pl`
    is a plain perl script and does not touch the topology at all, so its count
    has to be written back by hand or the next grompp rejects the coordinate
    file for not matching [ molecules ].
    """
    text = Path(topol).read_text(encoding="utf-8", errors="replace")
    if re.search(r"^[ \t]*SOL[ \t]+\d+[ \t]*$", text, re.M):
        BFF.set_molecule_count(topol, "SOL", count)
    else:
        if not text.endswith("\n"):
            text += "\n"
        Path(topol).write_text(text + f"SOL {count}\n", encoding="utf-8")


def solvate_and_ionise(workspace: Path, packed_gro: Path) -> Path:
    """Add water, remove what ended up inside the bilayer, then neutralise.

    The topology carries no SOL row through the shrink loop (inflategro.pl
    writes only the protein and DPPC), so `solvate -p` is what reintroduces it.
    `water_deletor.pl` then trims some of those waters without touching the
    topology, so the SOL row is corrected again from what actually remains in
    the fixed coordinates before grompp/genion ever see it.
    """
    stage = _stage(workspace)
    _run(workspace, ["solvate", "-cp", packed_gro.name, "-cs", "spc216.gro",
                     "-o", "system_solv.gro", "-p", "topol.top"])
    solvated = _require(stage / "system_solv.gro")
    _upsert_sol_count(stage / "topol.top", residue_counts(solvated).get("SOL", 0))

    removed = inflate_gro.delete_trapped_water(
        script=_script(workspace, "water_deletor.pl"),
        gro=solvated, out=stage / "system_solv_fix.gro", cwd=stage,
    )
    fixed = _require(stage / "system_solv_fix.gro")
    final_sol = residue_counts(fixed).get("SOL", 0)
    _upsert_sol_count(stage / "topol.top", final_sol)

    # A fresh render: em.mdp (left by the shrink loop) still carries
    # -DSTRONG_POSRES, and this grompp must not restrain the lipids.
    #
    # The template's ions.mdp defaults to PME, which is fine once the system
    # is neutral. Here it is not yet -- genion hasn't run -- so PME raises
    # "You are using Ewald electrostatics in a system with net charge",
    # confirmed against real gmx as a genuine WARNING (not just the NOTE
    # about non-integer/non-zero total charge), landing on a total of 3
    # warnings against GROMPP_MAXWARN=2. PACKING_MDP's plain cut-off sidesteps
    # it the same way it does for the pre-solvation minimisations, for the
    # same reason: this warning must stay fatal for any grompp run *after*
    # genion, when a net charge would mean genion itself failed.
    ions_mdp = MDP.render("ions", dict(PACKING_MDP), stage)
    grompp = _run(workspace, ["grompp", "-f", ions_mdp.name, "-c", fixed.name,
                              "-p", "topol.top", "-o", "ions.tpr",
                              "-maxwarn", GROMPP_MAXWARN])
    _run(workspace, ["genion", "-s", "ions.tpr", "-o", "ions.gro",
                     "-p", "topol.top", "-pname", "NA", "-nname", "CL",
                     "-neutral"],
         interactive_inputs=["SOL"])
    ions = _require(stage / "ions.gro")

    # The aqueous arm's step_3/step_5 records, written from this arm's own
    # files: md_runner.assert_ready requires both keys, and the run is not
    # auditable without the solvent and ion counts it actually ended up with.
    ion_counts = residue_counts(ions)
    n_na, n_cl = ion_counts.get("NA", 0), ion_counts.get("CL", 0)
    charge = _NET_CHARGE_RE.search(grompp.stdout + grompp.stderr)
    initial_net_charge = float(charge.group(1)) if charge else 0.0
    s = state.read(workspace)
    s["step_outputs"]["step_3"] = {
        "solv_gro": f"stage1_env/{fixed.name}",
        "n_solvent_molecules": final_sol,
        "water_atoms_removed": removed,
    }
    s["step_outputs"]["step_5"] = {
        "ion_gro": f"stage1_env/{ions.name}",
        "n_na": n_na, "n_cl": n_cl,
        # NA/CL are monovalent, so the post-genion charge is the charge grompp
        # reported before genion plus the ions genion actually placed.
        "net_charge": initial_net_charge + n_na - n_cl,
    }
    state.write(workspace, s)
    return ions


def build_index(workspace: Path, gro: Path) -> Path:
    """Create index.ndx with the Protein_DPPC group the mdp files couple to.

    The tutorial enters `1 | 13` at the make_ndx prompt. Those are positional
    group numbers and shift as soon as the lipid count changes, so the merge is
    requested by name and the result is verified by atom count.
    """
    stage = _stage(workspace)
    _run(workspace, ["make_ndx", "-f", gro.name, "-o", "index.ndx"],
         interactive_inputs=['"Protein" | "DPPC"', "q"])
    index = _require(stage / "index.ndx")

    groups = parse_index_groups(index)
    merged = _named_merge(groups)
    if merged is None:
        raise MembraneAssemblyError(
            f"make_ndx produced no Protein_DPPC group; groups: {sorted(groups)}"
        )
    expected = groups.get("Protein", 0) + groups.get("DPPC", 0)
    if groups[merged] != expected:
        raise MembraneAssemblyError(
            f"{merged} holds {groups[merged]} atoms, expected "
            f"{expected} (Protein {groups.get('Protein', 0)} + "
            f"DPPC {groups.get('DPPC', 0)})"
        )
    if "Water_and_ions" not in groups:
        raise MembraneAssemblyError(
            f"index.ndx has no Water_and_ions group; groups: {sorted(groups)}"
        )
    return index


def _named_merge(groups: dict[str, int]) -> str | None:
    """The merged group's name, whichever spelling make_ndx produced."""
    if "Protein_DPPC" in groups:
        return "Protein_DPPC"
    for name in groups:
        if "Protein" in name and "DPPC" in name:
            return name
    return None


def assemble(workspace_dir: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Build the bilayer-embedded system and record what happened."""
    workspace = Path(workspace_dir)
    bilayer_whole = prepare_bilayer(workspace)
    peptide = place_peptide(workspace, bilayer_whole)
    system = merge_system(workspace, peptide, bilayer_whole)
    add_lipid_molecules(workspace, bilayer_whole)
    install_strong_restraints(workspace, peptide)

    inflated = inflate_once(workspace, system)
    inflated_em = minimise(workspace, inflated.output, "system_inflated_em")
    shrink = shrink_to_target(
        workspace, inflated_em,
        target_apl=float(params.get("target_apl", TARGET_APL)),
    )
    ions = solvate_and_ionise(workspace, shrink.final_gro)
    index = build_index(workspace, ions)

    summary = {
        "lipids_removed": inflated.removed,
        "lipids_removed_upper": inflated.removed_upper,
        "lipids_removed_lower": inflated.removed_lower,
        "apl_after_inflation": inflated.apl_total,
        "shrink_iterations": shrink.iterations,
        "apl_final": shrink.apl_total,
        "apl_target": shrink.target_apl,
        "apl_history": shrink.apl_history,
        "index_file": str(index.relative_to(workspace)),
        "index_groups": parse_index_groups(index),
    }
    s = state.read(workspace)
    # step_2 is env_builder's box slot and is read by name elsewhere
    # (lib/tutorial_auditor.py, lib/system_config_validator.py), so this
    # merges into it rather than replacing it. The box is not built here: it
    # is the pre-equilibrated bilayer's own cell, which is rectangular with
    # 90 degree angles -- the same shape `editconf -bt triclinic` produces,
    # which is what the manifest asks for. There is no -d distance to record.
    step_2 = s["step_outputs"].setdefault("step_2", {})
    step_2.setdefault("box_type", params.get("box_type", "triclinic"))
    step_2.setdefault("box_distance", "n/a (bilayer cell reused)")
    step_2.setdefault("box_gro", "stage1_env/KALP_newbox.gro")
    step_2["membrane_assembly"] = summary
    # step_3 (solvate) and step_5 (ions) are written by solvate_and_ionise.
    s["current_step"] = 5
    s["last_completed_stage"] = "env"
    state.write(workspace, s)
    return summary


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
