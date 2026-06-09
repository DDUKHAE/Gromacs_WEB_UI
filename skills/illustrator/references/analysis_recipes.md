# Analysis Recipes

| Analysis | gmx tool | Default groups |
|---|---|---|
| RMSD | `gmx rms` | Backbone vs Backbone |
| RMSF | `gmx rmsf -res` | Protein |
| Radius of gyration | `gmx gyrate` | Protein |
| SASA | `gmx sasa` | Protein |
| H-bonds | `gmx hbond -num` | Protein/Protein |
| Secondary structure | `gmx do_dssp` | Protein |
| Energy terms | `gmx energy` | Potential, Kinetic, Total, Temperature, Pressure, Density |
| PCA | `gmx covar` + `gmx anaeig -2d -first 1 -last 2` | Backbone |
| Umbrella PMF | `gmx wham` | requires pull files |
| Free energy ΔG | `gmx bar` | requires per-lambda `md_l*.edr` |
| Membrane (stub) | extensions | thickness, area per lipid, order parameters |
| Protein-ligand (stub) | extensions | ligand RMSD, binding distance, interaction map |

All analyses pass `.xvg` outputs through `lib/xvg_parser` for
downsampled JSON; the LLM never reads raw `.xvg`.
