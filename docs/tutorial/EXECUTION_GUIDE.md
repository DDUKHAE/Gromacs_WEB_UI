# Tutorial Execution Guide

Run all commands from the repository root after activating the environment that provides `gmx`:

```bash
conda activate gromacs_web
python scripts/check_gromacs_env.py
```

For standard tutorials, upload the listed PDB through the browser or use the direct runner:

```bash
python web/runner.py --skill all --workspace runs/<run_id> --pdb <input.pdb>
```

| Tutorial | Required input beyond the primary structure | Expected final artifact |
|---|---|---|
| Lysozyme in Water | None | `stage2_md/production.gro` |
| KALP15 in DPPC | Prebuilt membrane topology/coordinates | `stage2_md/production.gro` |
| Protein–Ligand | Reviewed CGenFF topology and ligand coordinates | `stage2_md/production.gro` |
| Virtual Sites | Tutorial-compatible virtual-site topology | `stage2_md/production.gro` from `em.gro` |
| Building Biphasic Systems | Prebuilt two-phase coordinates/topology | `stage2_md/production.gro` |
| Umbrella Sampling | Reaction-coordinate groups, `index.ndx`, and one `.gro` per window | `stage2_md/umbrella/window_<id>/umbrella.gro`, then `stage3_viz/pmf.xvg` |
| Methane Free Energy | Solute coordinate/topology and lambda schedule | `stage2_md/lambda_<id>/free_energy.edr`, then `stage3_viz/bar.log` |
| Ethanol Free Energy | CGenFF solute coordinate/topology and Coulomb/VDW schedule | `stage2_md/lambda_<id>/free_energy.edr`, then `stage3_viz/bar.log` |

The validation contract for an umbrella or free-energy run is `advanced_workflow` in `system_config.json`. Paths are relative to the run workspace:

```json
{"advanced_workflow":{"umbrella":{"group1":"Chain_A","group2":"Chain_B","index":"inputs/umbrella/index.ndx","windows":[{"id":"000","coordinate":"inputs/umbrella/window_000.gro"}]}}}
```

```json
{"advanced_workflow":{"free_energy":{"coordinate":"inputs/free_energy/met.gro","topology":"inputs/free_energy/topol.top","topology_includes":["inputs/free_energy/met.itp"],"couple_moltype":"MET","lambda_schedule":[{"id":"00","init_lambda_state":0,"coul_lambdas":[0.0,0.0],"vdw_lambdas":[0.0,1.0]}]}}}
```

After every run, inspect `state.json.retry_history`, per-phase `.log` files, and `stage3_viz/report.md`. A failed GROMACS command should be retried only through the runner so its changed parameters are recorded.
