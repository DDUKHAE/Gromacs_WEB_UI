---
name: md-runner
description: >-
  Execute the GROMACS MD pipeline (Step 6–7) on a workspace that already
  contains stage1_env/ artifacts. Selects the phase sequence by tutorial
  variant, runs grompp+mdrun for each phase, validates each phase, and
  handles WARNING decisions via accept/decline re-invocation. Outputs go
  to workspace/stage2_md/. Invoke when env-builder has completed, or when
  the user supplies a pre-built environment.
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: md-runner

## Entry Point

```python
from skills.md_runner.md_runner import run_simulation
run_simulation(workspace_dir, phase_overrides=None, interactive=False)
```

## Input Schema

```json
{
  "workspace_dir": "/abs/path/workspace",
  "phase_overrides": {"nvt": {"nsteps": 50000, "tau_t": 0.5}},
  "interactive": true,
  "accept_warning_mutation": "uuid-or-null",
  "decline_warning_mutation": "uuid-or-null"
}
```

## Output Contract

Files under `workspace/stage2_md/`:
`{em,nvt,npt,production}.{tpr,xtc,trr,edr,gro,log,cpt}` or
variant-specific analogues. `workspace/state.json` is updated with
`step_outputs.step_7`, `retry_history[]`, and `last_completed_stage="md"`.

## Return Status Codes

- `complete` — all phases passed (or auto-declined).
- `warning_pending_decision` — user input required to accept/decline a
  proposed mutation. The next invocation supplies
  `accept_warning_mutation` or `decline_warning_mutation`.
- `warning_accepted` — mutation applied; the caller re-invokes with the
  same `phase_overrides` adjusted to resume the phase.
- `warning_declined` — proceeds to the next phase.

## Behavior

1. Validate stage1_env/ artifacts and state.json keys.
2. Resolve the phase sequence from the tutorial variant.
3. For each phase: compose .mdp → `gmx grompp` → `gmx mdrun` → validator.
4. RETRYABLE outcomes mutate parameters up to 3 attempts per phase.
5. WARNING outcomes return `warning_pending_decision` to the caller
   when `interactive=True`, or auto-decline when `interactive=False`.
6. FATAL outcomes stop the pipeline and surface the cause.
