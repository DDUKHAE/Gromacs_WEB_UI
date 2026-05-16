# Tutorial-Guided LLM Autonomy Plan

## 1. Objective

Build a tutorial-guided autonomy layer so the agent can:

1. Read the input PDB and user prompt.
2. Select the correct GROMACS tutorial workflow.
3. Map the workflow to `ARCHITECTURE.md` Step 0-8.
4. Execute with existing skills (`StateManager`, `GmxExecutor`, `MdpComposer`, `SystemValidator`, `TrajectoryAnalyzer`).
5. Recover from errors with bounded retries and state-safe rollback.

The key design rule is: keep `ARCHITECTURE.md` as the stable execution contract, and treat tutorial content as selectable protocol variants.

## 2. Scope and Non-Goals

In scope:

1. Tutorial selection and planning logic.
2. Machine-readable tutorial manifests.
3. Step-level command plan generation.
4. Integration with current skills and state tracking.

Out of scope (Phase 1):

1. Full support for every tutorial family from day one.
2. Major rewrite of existing skill internals.
3. Replacing Step 0-8 contract with a new pipeline.

## 3. Proposed Skill Additions

### 3.1 `TutorialRouter`

Role:

1. Classify system type from prompt + PDB context.
2. Choose one tutorial family.
3. Return missing required inputs.

Output contract:

```json
{
  "selected_tutorial": "Lysozyme_in_water",
  "pipeline_variant": "protein_aqueous_standard",
  "confidence": 0.91,
  "required_inputs": ["protein_pdb"],
  "missing_inputs": []
}
```

### 3.2 `TutorialPlanner`

Role:

1. Convert selected tutorial into Step 0-8 execution plan.
2. Bind tutorial docs to each step for rationale traceability.
3. Emit expected artifacts and validator gates.

Output contract:

```json
{
  "workflow": [
    {"step": 1, "action": "topology_generation", "doc": "generate_topology/prepare_the_topology.md"},
    {"step": 2, "action": "box_definition", "doc": "define_box_and_solvate/defining_the_unit_cell_and_adding_solvent.md"},
    {"step": 3, "action": "solvation", "doc": "define_box_and_solvate/defining_the_unit_cell_and_adding_solvent.md"}
  ]
}
```

### 3.3 `ProtocolCompiler`

Role:

1. Compile step actions into executable command specs for `GmxExecutor`.
2. Mark topology-mutating steps (`solvate`, `genion`) for backup/rollback policy.
3. Include retry parameter mutation policy.

Output contract:

```json
{
  "step": 3,
  "command": "gmx solvate",
  "args": {"-cp": "protein_box.gro", "-cs": "spc216.gro", "-p": "topol.top", "-o": "protein_solv.gro"},
  "topology_mutates": true,
  "requires_backup": true
}
```

## 4. Tutorial Manifest Standard

Each tutorial folder should include `tutorial.manifest.json` so runtime logic is deterministic.

Example path:

`docs/tutorial/Lysozyme_in_water/tutorial.manifest.json`

Required keys:

1. `id`
2. `system_type`
3. `required_inputs`
4. `defaults` (forcefield, water model, box preferences)
5. `architecture_steps`
6. `documents` (step-to-doc mapping)
7. `validation_profile`

## 5. Runtime Flow

1. Pre-flight:
   Read prompt, detect PDB file, initialize `simulation_state.json`.
2. Routing:
   Run `TutorialRouter` and select tutorial variant.
3. Planning:
   Run `TutorialPlanner` to map tutorial to Step 0-8.
4. Compilation:
   Run `ProtocolCompiler` for executable command specs.
5. Execution:
   Use existing skills in loop:
   `StateManager -> GmxExecutor -> SystemValidator`.
6. Analysis:
   Step 8 uses `TrajectoryAnalyzer` only for downsampled stats.
7. Final report:
   Tutorial selected, deviations, retries, quality gate results.

## 6. Mapping Policy to Existing Mandatory Rules

1. State tracking:
   `StateManager` update at every step boundary.
2. Topology version control:
   Backup `topol.top` before Step 3 and Step 5.
3. Hardware awareness:
   Step 0 collects CPU/GPU and tunes `mdrun` flags.
4. Infinite loop breaker:
   Max 3 retries, command or parameters must change each retry.
5. Warning and termination:
   `WARNING` continues with note in state; `FAIL` terminates after 3 attempts.
6. Data downsampling:
   No direct large `.xvg` reads by LLM; use `TrajectoryAnalyzer`.

## 7. Phased Delivery Plan

### Phase 1: Baseline (Lysozyme in water only)

1. Add manifest for `Lysozyme_in_water`.
2. Implement `TutorialRouter` with basic classifier rules.
3. Implement `TutorialPlanner` for standard protein aqueous flow.
4. Implement `ProtocolCompiler` minimal spec output.
5. Dry-run plan generation and state transitions.

Exit criteria:

1. One input PDB runs end-to-end through Step 8 plan generation.
2. Generated commands align with tutorial docs and architecture contract.

### Phase 2: Expand to protein-ligand and membrane

1. Add manifests for `Protein_Ligand_Complex`, `KALP15_in_DPPC`.
2. Add missing-input checks (ligand topology, membrane prerequisites).
3. Extend planner for variant steps.

Exit criteria:

1. Router chooses correct variant with explicit missing input report.
2. Planner emits valid step map for both new variants.

### Phase 3: Advanced methods

1. Add manifests for umbrella and free-energy families.
2. Add windowed run planning and specialized analysis hooks.
3. Extend validation profiles for advanced workflows.

Exit criteria:

1. Advanced tutorial workflows compile into executable specs.
2. Failure handling remains bounded and state-consistent.

## 8. Risks and Controls

1. Risk: ambiguous tutorial selection.
   Control: confidence score + explicit missing input list + conservative fallback to standard MD.
2. Risk: tutorial text drift vs command behavior.
   Control: manifest is source of runtime truth, docs are explanatory.
3. Risk: topology corruption during retries.
   Control: enforced backup/rollback around topology-mutating steps.
4. Risk: unstable LLM parsing from raw Markdown.
   Control: avoid freeform parsing at runtime; compile from manifest contracts.

## 9. Deliverables

1. This plan document.
2. `tutorial.manifest.json` files (starting with `Lysozyme_in_water`).
3. New skill skeletons:
   `skills/tutorial-router/`, `skills/tutorial-planner/`, `skills/protocol-compiler/`.
4. Architecture addendum section for tutorial-guided layer.

## 10. Acceptance Criteria

1. For a protein-water prompt, the system selects `Lysozyme_in_water` and generates a valid Step 0-8 plan.
2. Every step update is persisted in `simulation_state.json`.
3. Topology backup/rollback is always applied for destructive topology updates.
4. Validation gates are applied after each required step.
5. Final report includes tutorial choice, retries, deviations, and quality decision.
