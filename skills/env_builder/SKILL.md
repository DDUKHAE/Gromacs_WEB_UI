---
name: env-builder
description: >-
  Build a CHARMM-GUI-style MD environment locally from a PDB file and a
  natural-language goal. Performs Step 0–5 of the GROMACS pipeline:
  hardware profiling, tutorial routing, topology, box, solvation,
  and ion neutralization. Outputs files to workspace/stage1_env/ and
  updates workspace/state.json. Invoke when the user supplies a PDB and
  wants the system prepared for MD.
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: env-builder

## Input Schema

```json
{
  "pdb_path": "/abs/path/input.pdb",
  "prompt": "natural-language goal",
  "workspace_dir": "/abs/path/workspace",
  "prerequisites": {
    "ligand_itp": "...",
    "membrane_composition": {"DPPC": 128},
    "reaction_coordinate": {"...": "..."},
    "lambda_schedule": ["..."]
  },
  "interactive": true
}
```

## Output Contract

Files under `workspace/stage1_env/`:
`processed.gro`, `topol.top`, `topol.top.bak`, `box.gro`,
`solv.gro`, `ions.tpr`, `ions.gro`, `index.ndx` (when applicable).

`workspace/state.json` is updated with `step_outputs.step_1..step_5`,
`tutorial`, `hardware`, `topology_backups`, and
`last_completed_stage = "env"`.

## Behavior

1. Initialize workspace and collect hardware profile (Step 0).
2. Route the tutorial based on PDB hints + prompt + prerequisites.
   Block on missing prerequisites for derived tutorials.
3. Step 1: `pdb2gmx` with force field defaults from the tutorial manifest.
4. Step 2: `editconf` with box defaults from the manifest.
5. Step 3: `solvate`. `topol.top.bak` is created before mutation.
6. Step 4: render `ions.mdp` and run `grompp`.
7. Step 5: `genion` with charge neutralization at 0.15 M.

## References

- `references/charmmgui_workflow.md`
- `references/forcefield_guide.md`
- `references/prerequisite_schema.md`
