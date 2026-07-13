# Molecular Dynamics Simulation Architecture: GROMACS Harness

This document is the pipeline map for autonomous GROMACS execution.

## 1. System Workflow Overview

The harness automates Step 0-8 with GROMACS-native commands while preserving physical validity through validator gates.

## 2. Core Files

- `.pdb`: input coordinates
- `.gro`: state coordinates per step
- `.top`: topology and molecule counts
- `.mdp`: runtime parameters
- `.tpr`: compiled run input
- `.edr/.xtc/.trr/.log`: simulation outputs

## 3. Fixed Step Contract (0-8)

1. Step 0: hardware profile + state init
2. Step 1: topology generation
3. Step 2: box definition
4. Step 3: solvation
5. Step 4: ionization prep
6. Step 5: ionization
7. Step 6: execution prep (min/nvt/npt/md)
8. Step 7: run phases
9. Step 8: trajectory analysis

Step numbering is immutable. Tutorial variants may change implementation details but never change step ids.

## 4. Tutorial-Guided Autonomy Layer

### 4.1 Routing and Planning Chain (historical — replaced, see §7)

The three-stage `TutorialRouter` / `TutorialPlanner` / `ProtocolCompiler`
chain described below was the *original* design and is **no longer
present in the code**. It is kept here only for historical context;
do not treat it as current behavior. The routing/planning role it
described is now performed by `lib/tutorial_registry.py`, invoked
directly from the `env-builder` skill — see §7.

1. `TutorialRouter`: choose tutorial family and report missing inputs
2. `TutorialPlanner`: map selected tutorial to Step 0-8 plan with state/validator requirements
3. `ProtocolCompiler`: compile to executable `GmxExecutor` specs

### 4.2 Runtime Read Order

1. `docs/tutorial/TUTORIAL_OVERVIEW.md`
2. `docs/tutorial/tutorial_index.json`
3. tutorial manifest (if exists)
4. `docs/tutorial/LLM_TUTORIAL_GUIDE.md`
5. `docs/tutorial/LLM_ESSENTIALS_BY_STEP.md`
6. required tutorial part docs

### 4.3 Source Priority

1. Manifest is runtime truth.
2. `tutorial_index.json` is routing/index truth.
3. Tutorial markdown parts are rationale/reference.

## 5. Mandatory Safety Contracts

- Step 3 and Step 5 must backup `topol.top` and support rollback on retry.
- Retry max is 3; each retry must mutate parameters/flags and command configuration.
- A validator gate is required after Step 1-7. There is no separate `SystemValidator` skill/class in the current code (that name is historical, see §4.1); the gate is `lib/validators.py`'s `judge_*` functions, called directly from `skills/env_builder/env_builder.py` and `skills/md_runner/md_runner.py`.
- Step 8 analysis must use `TrajectoryAnalyzer` downsampled outputs.

## 6. Immediate FAIL Conditions

- Required `simulation_state.json` keys missing for the current step
- Missing hardware profile from Step 0
- Missing topology backup before Step 3 or Step 5
- Retry with equivalent command string/parameter set
- Missing retry_history cause and remediation mutation

These are FAIL conditions, not WARNING conditions.

## 7. 3-Skill Mapping (added 2026-05-14)

The fixed Step 0–8 contract is preserved. Skills group steps for
user-facing invocation:

| Stage | Skill | Steps |
|---|---|---|
| env | `env-builder` | 0, 1, 2, 3, 4, 5 |
| md | `md-runner` | 6, 7 |
| viz | `illustrator` | 8 |

`workspace/state.json.last_completed_stage` advances `env → md → viz`.
The old `TutorialRouter` / `TutorialPlanner` / `ProtocolCompiler`
skills are replaced by `lib/tutorial_registry.py` invoked inside
`env-builder`.
