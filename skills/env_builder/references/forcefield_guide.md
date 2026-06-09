# Force Field Selection Guide

- Default: `charmm36` + `tip3p`.
- Membrane systems (KALP15_in_DPPC etc.): require lipid parameters
  bundled with `charmm36`. Verify the installed `GMXLIB` contains
  the appropriate `.rtp`/`.itp` entries before Step 1.
- Protein-ligand: force-field choice must support the ligand
  parameter set. If `ligand_itp` is provided, the include lines for
  the ligand topology must be merged into `topol.top` before Step 4.
- Free-energy systems: the alchemically-coupled moltype must match
  `couple-moltype` in `free_energy.mdp`.

The harness reads tutorial manifest `defaults.forcefield` /
`defaults.water_model` when present. Override via `prerequisites`
fields if a custom force field is needed.
