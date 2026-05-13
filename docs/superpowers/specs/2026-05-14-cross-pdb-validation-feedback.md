# Cross-PDB Validation Feedback (2026-05-14)

## Scope
- Goal: Check whether the harness works beyond `1UBQ.pdb` and identify generalization blockers.
- Additional test inputs:
  - `1CRN.pdb`
  - `1AKI.pdb`

## Results Summary
- `1UBQ`: progresses to NVT, then fails on physical instability (LINCS / NaN potential) with validator gate active.
- `1CRN`: fails at Step 4 (`grompp`) with topology/coordinate count mismatch.
- `1AKI`: fails at Step 2 (`editconf`) due to polluted argument state.

## Reproduced Failures
1. **Run-to-run state pollution (critical)**
- Evidence: `1AKI` run executed `gmx editconf -c crn_box.gro` (boolean flag `-c` incorrectly overwritten with prior run filename).
- Impact: Commands become invalid when multiple PDBs are run in sequence.
- Root cause class: global state reuse + broad argument auto-refresh logic.

2. **Topology/coordinate mismatch in ions prep (critical)**
- Evidence: `1CRN` Step 4 reported:
  - coordinates in `crn_solv.gro`: `13398`
  - topology count in `topol.top`: `14950`
- Impact: Pipeline aborts before ionization/equilibration.
- Root cause class: topology mutation/rollback and per-run file hygiene not fully isolated.

3. **NVT physical instability still unresolved (important)**
- Evidence on `1UBQ`: LINCS warning, unsettled waters, NaN potential energy.
- Impact: not yet production-safe for autonomous continuation across proteins.

## Why This Is Not 1UBQ-Specific
- Failures include:
  - command argument corruption (`1AKI`)
  - topology consistency break (`1CRN`)
  - physical instability (`1UBQ`)
- These are framework-level issues, not tied to one structure only.

## Required Hardening Before Claiming Generality
1. **Per-run isolation**
- Use unique run directory per target (`runs/<target>/<timestamp>`), avoid sharing `topol.top`, `*.gro`, `*.tpr`, `*.cpt`.
- Reset/initialize `simulation_state.json` per run and never reuse prior-run `latest_gro` paths.

Status update (2026-05-14):
- Implemented with run directories in the form `runs/<target>_<timestamp>`.

2. **Safe argument refresh rules**
- Do not mutate boolean flags (`-c` for `editconf`) into path values.
- Refresh only known coordinate/path flags by command schema (`-f`, `-cp`, `-c`, `-r`, `-t`, `-p`) with strict typing.

3. **Topology integrity gate**
- After `solvate` and `genion`, enforce consistency check:
  - atom count in `*.gro`
  - molecule block consistency in `topol.top`
- Fail fast with explicit remediation before `grompp`.

4. **NVT stabilization fallback ladder**
- On LINCS/NaN patterns:
  - lower `dt`
  - stronger restraints / simplified coupling groups
  - short pre-NVT warmup stage
- Retry policy should escalate physically meaningful knobs, not only runtime flags.

5. **Regression matrix**
- Minimum recurring suite:
  - `1UBQ` (small soluble protein)
  - `1CRN` (very small, sensitive)
  - `1AKI` (larger soluble protein)
- Pass condition: all complete through Step 8 without cross-run contamination.

Regression artifact:
- Aggregated machine-readable summary is written to `/tmp/harness_regression_summary.json`.

## Immediate Action Items
- Refactor runner to per-run working directories.
- Tighten `_refresh_args_from_state` to command-aware safe mapping.
- Add post-solution topology consistency validator prior to each `grompp`.
- Add structured regression script for the 3-PDB matrix.
