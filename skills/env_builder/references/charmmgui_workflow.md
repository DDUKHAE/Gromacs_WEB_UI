# CHARMM-GUI Workflow Mapping (Local Reimplementation)

| CHARMM-GUI step | env-builder Step | GROMACS tool |
|---|---|---|
| Read PDB | Step 0 (workspace init) | n/a |
| Choose force field / water | Step 1 default selection | `gmx pdb2gmx` |
| Generate topology | Step 1 | `gmx pdb2gmx` |
| Position lipids/ligand | Step 1 merge of `.itp` from prerequisites | manual merge in `topol.top` |
| Define box | Step 2 | `gmx editconf` |
| Solvate | Step 3 (with `topol.top.bak`) | `gmx solvate` |
| Neutralize / add ions | Step 4 + Step 5 | `gmx grompp`, `gmx genion` |

The local reimplementation never calls the CHARMM-GUI web service.
Manifest defaults under `docs/tutorial/<id>/tutorial.manifest.json`
drive force-field and box choices.
