# Release Hardening Design

## Purpose

Make every tutorial advertised by the harness either execute through its
required scientific workflow or fail before execution with an actionable
missing-input error.  Correct the reviewed phase-input, retry, pressure
coupling, analysis, and documentation defects without changing user-owned
uncommitted work outside this scope.

## Scope

This change covers:

- virtual-sites phase input selection;
- classified, persisted, non-equivalent retry handling for GROMACS execution
  failures and validator retryable outcomes;
- variant-aware pressure-coupling settings for membrane systems;
- multi-window umbrella sampling and multi-lambda alchemical free-energy
  workflows;
- result aggregation for WHAM/BAR-compatible outputs;
- unit and contract regression tests; and
- README plus tutorial-specific operator guidance.

It does not infer reaction coordinates, generate umbrella windows, or invent
lambda schedules.  Those scientific inputs must be supplied and are validated
before a run starts.

## Workflow Configuration Contract

`system_config.json` gains an `advanced_workflow` object.

- `advanced_workflow.umbrella` requires `group1`, `group2`, and a non-empty
  `windows` list.  Each window has a stable `id` and a coordinate file path
  relative to the run workspace.  Optional force constant and per-window
  settings override the tutorial default.
- `advanced_workflow.free_energy` requires `couple_moltype` and a non-empty
  lambda schedule.  A lambda item contains its stable `id`, an
  `init_lambda_state`, and the complete Coulomb and van der Waals lambda
  vectors.  The schedule is kept verbatim in the materialized run plan.

The run plan rejects a selected umbrella/free-energy tutorial when the
corresponding contract is absent or malformed.  This prevents a seemingly
successful single-window or single-lambda calculation from being reported as a
complete PMF or free-energy calculation.

## Browser Input Delivery

The browser exposes an Advanced Workflow section only for umbrella and
free-energy tutorial selections.  It submits the validated JSON contract plus
the required uploaded files in the create-run request.

- Umbrella accepts an index file and one coordinate file for each declared
  window.  The server stores them under `inputs/umbrella/`, rewrites only the
  user-supplied filenames to safe workspace-relative paths, and rejects an
  undeclared, duplicate, missing, or oversized file.
- Free-energy accepts a starting coordinate/topology bundle and materializes
  the validated lambda schedule into `system_config.json`.  The server stores
  the bundle under `inputs/free_energy/` and rejects topology includes that
  escape the uploaded bundle.

The API validates the configuration before persisting a run directory.  File
paths exposed in the run plan are workspace-relative and are never accepted
from the browser as absolute paths.  The normal single-PDB workflow remains
unchanged for the other tutorials.

## Execution Model

Standard variants retain the named stage directory `stage2_md/`.  Virtual
Sites maps its production input directly to `em.gro`.

Membrane NPT and production phases render `pcoupltype = semiisotropic`; the
standard aqueous path remains isotropic.

Umbrella execution creates `stage2_md/umbrella/window_<id>/`.  For each input
window it runs its documented NPT equilibration followed by an umbrella
production run, records the actual output paths in state, and keeps the window
independent so a completed window can be resumed without rerunning it.

Free-energy execution creates `stage2_md/lambda_<id>/`.  Each lambda runs EM,
NVT, NPT, and production with the lambda-specific MDP values.  It records each
completed subphase and uses a deterministic directory/name convention that the
analysis layer consumes.

## Failure Handling

`run_phase` converts failed GROMACS results into a structured execution
judgment.  `run_phase_with_recovery` records the classifier, attempted command
parameters, and remediation in `state.json.retry_history` before each retry.
Every retry changes an effective setting: for a grompp warning budget it
changes the actual `-maxwarn` argument; for integration failures it changes
the applicable MDP parameters.  After three failed attempts it raises a
terminal error with the recorded history.

## Analysis and Reporting

Umbrella aggregation only invokes `gmx wham` when all configured windows have
the required pull-force outputs.  Free-energy aggregation discovers the
per-lambda production EDR files and passes them to BAR.  Missing files are
reported as incomplete workflow state, not as a successful skipped analysis.

## Testing and Documentation

Tests cover virtual-site input selection, retry mutations reaching the actual
command, retry history, membrane pressure coupling, invalid advanced workflow
configuration, multi-window/lambda path construction, resume behavior, and
analysis input discovery.  Documentation states the supplied prerequisites,
commands to run each tutorial, expected artifacts, and the limits of any
analysis that remains optional.

## Acceptance Criteria

- Virtual Sites production consumes `em.gro` and never references `npt_pr.gro`.
- Command failures are persisted and retried with non-equivalent effective
  commands up to the configured limit.
- Membrane templates use semi-isotropic pressure coupling.
- Umbrella and free-energy runs require explicit scientific inputs, create one
  isolated result directory per window/lambda, and expose aggregate-analysis
  inputs.
- The full Python test suite runs without collection/configuration warnings.
- README and tutorial guides match the resulting behavior.
