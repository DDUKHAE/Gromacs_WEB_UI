# Advanced troubleshooting: membrane equilibration

Adapted from `advanced_troubleshooting.html` of the upstream tutorial, which has
no counterpart elsewhere in these local docs.

## How membrane equilibration fails

Two failure modes dominate:

* The lipid headgroups collapse into themselves, driven by the attractive and
  repulsive forces in that highly charged region.
* The bilayer separates and a void develops in the hydrophobic core, because the
  headgroups are strongly attracted to the aqueous solvent.

Either shows up as LINCS warnings while molecules are sheared apart, as
distortions of the unit cell, or as visible voids inside the lipid core.

**This pipeline does not detect or recover from either failure mode
automatically.** There is no `lipid_collapse` entry in `MUTATION_BY_CAUSE`
(`skills/md_runner/md_runner.py`) — no validator in this codebase can classify
a phase failure as lipid collapse, so there is nothing for such an entry to
key off. If equilibration collapses, the run fails and a person has to look at
the trajectory and intervene by hand using the two remedies below. Do not
expect the pipeline to retry its way out of this one.

## Remedy 1: restrain the lipid headgroups in z

Position-restrain the DPPC `P8` atoms along the bilayer normal. The lipids stay
free to re-orient within the plane of the bilayer, but cannot pull apart from
one another, which is what opens the void.

`tutorial_data/KALP15_in_DPPC/lipid_posre.itp` holds:

```
[ position_restraints ]
;  i funct       fcx        fcy        fcz
   8    1       0       0       1000
```

Note that the upstream page describes this as restraining "in the x-y plane"
while the file restrains z and leaves x-y free. The file matches the stated
purpose, so the file is right and the prose is wrong.

`dppc.itp` already carries the matching include, guarded by `POSRES_LIPID`:

```
#ifdef POSRES_LIPID
#include "lipid_posre.itp"
#endif
```

**This is a manual remedy, not a wired-in one.** `lipid_posre.itp` sits in
`tutorial_data/KALP15_in_DPPC/` for reference only — nothing in
`skills/env_builder` copies it into a run's `stage1_env/`, the directory
`pdb2gmx`/`grompp` actually read from (compare how `dppc.itp` itself is staged
in `skills/env_builder/env_builder.py`). If you add `-DPOSRES_LIPID` to an
`mdp`'s `define` without first copying `lipid_posre.itp` into the run
directory yourself, `grompp` fails outright on the missing include — this
define is unmaskably fatal until you do that copy by hand.

## Remedy 2: simulated annealing under NPT

Warm the system from 0 K to the target temperature over 500 ps with the
restraints in place, so water soaks slowly into the voids around the headgroups.
NPT rather than NVT, because rapid lipid rearrangement and void closure
otherwise distort the cell.

`tutorial_data/KALP15_in_DPPC/mdp/anneal_npt.mdp` carries the upstream
protocol, unmodified. It is a reference copy of the tutorial's file, not a
ready-to-run template: it declares `annealing`, `annealing_npoints`,
`annealing_time`, and `annealing_temp` as three space-separated values
(`single single single`, `2 2 2`, …) while `tc_grps`, `tau_t`, and `ref_t` all
list only the pipeline's two coupling groups
(`Protein_DPPC Water_and_ions`). GROMACS wants exactly one annealing entry per
`tc_grps` member, so `grompp` will reject this file as-is — trim every
`annealing*` line to two values before using it, and don't assume the copy in
this repository has already been fixed.

## How to actually use these if collapse happens

There is no automation to invoke. If a real run shows LINCS warnings, cell
distortion, or a visible core void during equilibration:

1. Copy `lipid_posre.itp` into the run's `stage1_env/` (or wherever
   `topol.top`'s `#include "dppc.itp"` resolves from) so the existing
   `#ifdef POSRES_LIPID` include in `dppc.itp` can find it.
2. Add `-DPOSRES_LIPID` alongside `-DPOSRES` to the equilibration mdp's
   `define`, and re-run `grompp`/`mdrun` for that phase.
3. If the void persists, fix `anneal_npt.mdp`'s annealing block to two values
   per group (matching `tc_grps`) and run it as an extra equilibration phase
   ahead of `npt`, with restraints in place, before falling back to `npt` as
   the tutorial defines it.

None of this is triggered by `run_phase_with_recovery`; it is a manual
escape hatch for a failure mode the pipeline's validators cannot see.
