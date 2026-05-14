# Agent Skills Redesign — Design Spec

Date: 2026-05-14
Status: Approved (pending user review of written spec)
Scope: GROMACS harness skill layer (full rewrite)

## 1. Purpose and Scope

Replace the current 7-skill, low-level skill layer with a 3-skill, capability-aligned skill layer. Skills correspond to user-meaningful stages of the GROMACS pipeline:

1. `env-builder` — environment construction in the style of CHARMM-GUI, implemented entirely with local GROMACS tools (Step 0–5).
2. `md-runner` — MD execution following the GROMACS tutorial selected for the system (Step 6–7).
3. `illustrator` — analysis, plotting, structural rendering, trajectory animation, and report generation (Step 8).

The redesign supports all eight tutorials in `docs/tutorial/` (Lysozyme_in_water, KALP15_in_DPPC, Protein_Ligand_Complex, Umbrella_Sampling, Building_Biphasic_Systems, Free_Energy_Calculations_Methane_in_Water, Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol, Virtual_Sites). Derived tutorials with `unsupported_autonomy_level: manual_prerequisite_required` require explicit prerequisite inputs in the skill input schema.

All existing harness code under `skills/` and `run_autonomy.py` is scrapped. Existing tutorial documents under `docs/tutorial/` are retained; routing guidance in `docs/tutorial/LLM_TUTORIAL_GUIDE.md` is updated to the new model.

## 2. Architecture

```
                    ┌───────────────────────────────┐
                    │ User / LLM Agent              │
                    │ - PDB + natural-language prompt│
                    │ - (optional) prerequisite YAML │
                    └────────────┬──────────────────┘
                                 │ invoke any skill (independent entry)
                ┌────────────────┼──────────────────┐
                ▼                ▼                  ▼
        ┌──────────────┐  ┌─────────────┐   ┌──────────────┐
        │ env-builder  │  │ md-runner   │   │ illustrator  │
        │ Step 0–5     │  │ Step 6–7    │   │ Step 8       │
        └──────┬───────┘  └──────┬──────┘   └──────┬───────┘
               │                 │                 │
               │       reads/writes only via       │
               ▼                 ▼                 ▼
        ┌─────────────────────────────────────────────────┐
        │ workspace/ (per-run isolated directory)         │
        │   ├── inputs/                                   │
        │   ├── stage1_env/                               │
        │   ├── stage2_md/                                │
        │   ├── stage3_viz/                               │
        │   └── state.json (canonical pipeline state)     │
        └─────────────────────────────────────────────────┘
                                 ▲
                                 │ import-only shared helpers
                ┌────────────────┴───────────────────┐
                │ lib/ (no SKILL.md — internal)      │
                │   gmx_wrapper · state · validators │
                │   mdp_templates · xvg_parser       │
                │   tutorial_registry                │
                └────────────────────────────────────┘
```

Core principles:

- **Skill boundary == user capability.** Each skill is a single stage the user/agent meaningfully invokes.
- **Single source of truth.** `workspace/state.json` is the canonical state. Step 0–8 keys are preserved so existing tutorial manifests are reusable.
- **File-based contract between skills.** No in-memory handoff. Any skill can be entered independently if `workspace/state.json` and the relevant `stageN_*/` directory satisfy its input schema. Skills are also chainable: completing one skill leaves the workspace in a state the next skill accepts.
- **`lib/` is internal.** It is imported by the three skills and is not a callable skill. No `SKILL.md` in `lib/`.
- **Routing is internal to env-builder.** No separate router/planner skill. `docs/tutorial/LLM_TUTORIAL_GUIDE.md` (refreshed) is the decision document, `docs/tutorial/tutorial_index.json` remains the static index, and `lib/tutorial_registry.py` is the loader.
- **External tools isolated to illustrator.** PyMOL/VMD/ffmpeg dependencies live only in illustrator. env-builder and md-runner depend only on `gmx`.

## 3. Components

### 3.1 `skills/env-builder/` (Step 0–5)

```
skills/env-builder/
├── SKILL.md
├── env_builder.py
└── references/
    ├── charmmgui_workflow.md
    ├── forcefield_guide.md
    └── prerequisite_schema.md
```

Responsibilities:

1. Parse PDB + natural-language prompt → select tutorial and variant via `lib/tutorial_registry`.
2. Step 0: collect hardware profile (GPU, CPU, OpenMP threads).
3. Step 1: `gmx pdb2gmx` for topology + protein `.gro`. Merge ligand/membrane `.itp` from prerequisites when present.
4. Step 2: `gmx editconf` for box definition.
5. Step 3: `gmx solvate` for solvent addition. `topol.top.bak` backup required before invocation.
6. Step 4–5: compose `ions.mdp` → `gmx grompp` → `gmx genion`. Backup required.
7. Write all artifacts to `workspace/stage1_env/`. Update `state.json` Step 0–5 keys and `last_completed_stage="env"`.

Input schema (summary):

```json
{
  "pdb_path": "/abs/path/input.pdb",
  "prompt": "natural-language goal",
  "workspace_dir": "/abs/path/workspace",
  "prerequisites": {
    "ligand_itp": "...",
    "membrane_composition": {"...": "..."},
    "reaction_coordinate": {"...": "..."},
    "lambda_schedule": ["..."]
  },
  "interactive": true
}
```

Output contract:

- Files: `stage1_env/{processed.gro, topol.top, ions.gro, index.ndx, ions.tpr, topol.top.bak}` and any tutorial-specific artifacts.
- `state.json`: Step 0–5 keys populated, `tutorial`, `hardware`, `topology_backups` set, `last_completed_stage="env"`.

### 3.2 `skills/md-runner/` (Step 6–7)

```
skills/md-runner/
├── SKILL.md
├── md_runner.py
└── references/
    ├── phase_protocols.md
    ├── error_recovery.md
    └── hardware_tuning.md
```

Responsibilities:

1. Validate `state.json` and `stage1_env/` against the schema (independent-entry gate).
2. Decide phase sequence by tutorial variant (standard EM→NVT→NPT→Production; umbrella sampling pulling+windows; free-energy lambda states; etc.).
3. For each phase: compose `.mdp` via `lib/mdp_templates` → `gmx grompp` → `gmx mdrun`.
4. After each phase: run `lib/validators` gate. Branch on PASS / WARNING / RETRYABLE / FATAL per Section 5.
5. Write artifacts to `workspace/stage2_md/`. Update Step 6–7 keys and `last_completed_stage="md"`.

Input schema:

```json
{
  "workspace_dir": "/abs/path/workspace",
  "phase_overrides": {"nvt": {"nsteps": 50000, "tau_t": 0.5}},
  "interactive": true,
  "accept_warning_mutation": "uuid-or-null",
  "decline_warning_mutation": "uuid-or-null"
}
```

Output contract:

- Files: `stage2_md/{em,nvt,npt,md}.{tpr,xtc,trr,edr,gro,log,cpt}` (or tutorial-variant analogues such as per-window outputs).
- `state.json`: Step 6–7 keys populated, `retry_history[]` extended, `last_completed_stage="md"`.

### 3.3 `skills/illustrator/` (Step 8)

```
skills/illustrator/
├── SKILL.md
├── illustrator.py
└── references/
    ├── analysis_recipes.md
    ├── render_recipes.md
    └── animation_recipes.md
```

Responsibilities:

1. Validate `state.json` and `stage2_md/` against the schema (independent-entry gate).
2. Run the broad analysis catalog (Section 3.3.1). All analyses default to enabled; tutorial-irrelevant analyses auto-skip.
3. Generate plots (matplotlib).
4. Render structural images (PyMOL primary → VMD fallback → matplotlib-only graceful degradation).
5. Render trajectory animations (`.mp4` via ffmpeg primary, `.gif` optional).
6. Compose `report.md` (and optional `report.html` via plotly when available).
7. Write all artifacts to `workspace/stage3_viz/`. Update Step 8 keys and `last_completed_stage="viz"`.

#### 3.3.1 Analysis and rendering catalog

| Category | Outputs |
|---|---|
| Structural stability | RMSD (backbone / Cα / heavy), RMSF (per residue), radius of gyration, SASA (total / hydrophobic / hydrophilic), end-to-end distance |
| Hydrogen bonding and contacts | `gmx hbond` H-bond count and lifetime, distance maps, residue contact map, salt bridge tracking |
| Secondary structure | `gmx do_dssp` time-resolved secondary structure plot |
| Energy / thermodynamics | `gmx energy`: potential, kinetic, total, temperature, pressure, density, volume, LJ-SR, Coulomb-SR; conservation and drift analysis |
| Dimensionality reduction | `gmx covar` + `gmx anaeig` PCA (PC1–PC2 scatter and free-energy landscape by Boltzmann inversion) |
| Tutorial-specific | Umbrella: PMF via `gmx wham`, window histograms. Free energy: BAR via `gmx bar`, ΔG ladder. Membrane: thickness, area per lipid, order parameters. Protein-ligand: ligand RMSD, binding distance, interaction map |
| Structural rendering | PyMOL primary / VMD fallback: cartoon + surface + key-residue highlight, ligand binding-pocket close-up, membrane cross-section. First / middle / last frames plus user-specified frames |
| Trajectory animation | `.mp4` (h264 via ffmpeg) primary, `.gif` optional. Full trajectory, rotation view, section view |
| Report | `report.md` embedding all images, tables, and conclusions. Optional `report.html` with interactive plotly plots |

Input schema:

```json
{
  "workspace_dir": "/abs/path/workspace",
  "analyses": ["rmsd","rmsf","gyrate","sasa","hbond","dssp","energy","pca","tutorial_specific"],
  "render_frames": [0, "middle", "last"],
  "animation": {"enabled": true, "fps": 30, "stride": 10, "formats": ["mp4"]},
  "report_html": true,
  "interactive": true
}
```

### 3.4 `lib/` (internal)

| File | Responsibility |
|---|---|
| `gmx_wrapper.py` | `gmx <cmd>` subprocess execution, error classification, interactive-prompt bypass, output capture |
| `state.py` | Atomic read/write of `state.json`, schema validation |
| `validators.py` | Step-level PASS / WARNING / RETRYABLE / FATAL judgment (energy drift, neutrality, RMSD stability, density, temperature, pressure, etc.) |
| `mdp_templates/` | Base `.mdp` templates for EM, NVT, NPT, production, ions, umbrella, free energy |
| `xvg_parser.py` | `.xvg` → downsampled JSON (LLM never reads raw `.xvg`) |
| `tutorial_registry.py` | Loader for `tutorial_index.json` and per-tutorial manifests; routing decision function |

### 3.5 Documents

- `docs/tutorial/LLM_TUTORIAL_GUIDE.md` — refreshed routing rules for the 3-skill model. The decision document for tutorial selection inside env-builder.
- `AGENTS.md` — mandatory rules retained. Skill references updated (state-manager → `lib/state`, gmx-executor → `lib/gmx_wrapper`, etc.).
- `ARCHITECTURE.md` — Step 0–8 contract retained. 3-skill mapping added.
- `skills/SKILLS_OVERVIEW.md` — rewritten from 7 skills to 3 skills.

## 4. Data Flow

### 4.1 Full-pipeline (chained)

```
env-builder
  workspace/ created → state.json initialized (current_step=0)
  Step 0–5 sequenced → stage1_env/ populated → last_completed_stage="env"

md-runner (next invocation)
  reads state.json, requires last_completed_stage=="env"
  uses stage1_env/ inputs → Step 6–7 sequenced → stage2_md/ populated
  last_completed_stage="md"

illustrator (next invocation)
  reads state.json, requires last_completed_stage=="md"
  uses stage2_md/ + lib/xvg_parser → analyses → stage3_viz/ populated
  last_completed_stage="viz"
```

### 4.2 Independent-entry scenarios

| Scenario | Entry skill | Validation rule |
|---|---|---|
| Externally prepared environment, run MD only | `md-runner` | User pre-populates `workspace/stage1_env/` with `processed.gro`, `topol.top`, `ions.gro`, `index.ndx`, and a `state.json` containing at minimum the Step 0–5 keys plus `last_completed_stage="env"`. md-runner validates the schema and required files. |
| Analyze and visualize an existing trajectory | `illustrator` | User pre-populates `workspace/stage2_md/` with `md.tpr`, `md.xtc`, `md.edr` and a minimally populated `state.json`. illustrator validates. |
| Build environment only and stop | `env-builder` | Normal operation. The next skill is simply not invoked. |

### 4.3 `state.json` schema

```json
{
  "schema_version": "1.0",
  "workspace_dir": "/abs/path",
  "current_step": 0,
  "last_completed_stage": "env",
  "tutorial": {
    "id": "Lysozyme_in_water",
    "variant": "protein_aqueous_standard",
    "manifest_path": "docs/tutorial/Lysozyme_in_water/tutorial.manifest.json"
  },
  "hardware": {"gpu_ids": [0], "cpu_count": 16, "ntomp": 8},
  "step_outputs": {
    "step_1": {"forcefield": "charmm36", "water_model": "tip3p",
               "top_file": "stage1_env/topol.top",
               "gro_file": "stage1_env/processed.gro"},
    "step_2": {"box_type": "cubic", "box_distance": 1.0,
               "box_gro": "stage1_env/box.gro"},
    "step_3": {"solv_gro": "stage1_env/solv.gro",
               "n_solvent_molecules": 12345},
    "step_5": {"ion_gro": "stage1_env/ions.gro",
               "n_na": 12, "n_cl": 8, "net_charge": 0.0},
    "step_7": {"em_gro": "stage2_md/em.gro",
               "nvt_gro": "stage2_md/nvt.gro",
               "npt_gro": "stage2_md/npt.gro",
               "production_gro": "stage2_md/md.gro"},
    "step_8": {"rmsd_stable": true, "energy_converged": true,
               "final_report_path": "stage3_viz/report.md"}
  },
  "retry_history": [
    {"step": 7, "phase": "npt",
     "tier": "retryable",
     "cause": "pressure_coupling",
     "remediation": "tau_p 2.0 → 5.0",
     "timestamp": "2026-05-14T10:00:00Z"}
  ],
  "pending_warnings": [],
  "topology_backups": ["stage1_env/topol.top.bak"]
}
```

### 4.4 Skill entry validation gates

Each skill validates required state keys and required files on entry. Example for md-runner:

```python
required_keys  = ["step_1", "step_2", "step_3", "step_5"]
required_files = ["processed.gro", "topol.top", "ions.gro", "index.ndx"]
for k in required_keys: fail_if(k not in state["step_outputs"], "missing_key")
for f in required_files: fail_if(not exists(stage1_env/f), "missing_file")
fail_if(state["last_completed_stage"] != "env", "stage_mismatch")
```

### 4.5 Workspace isolation

- Each full-pipeline run creates `runs/<tag>_<timestamp>/` containing an isolated workspace.
- Independent-entry users either point to an existing workspace or create a new one.
- Absolute paths everywhere; concurrent runs are safe.

## 5. Error Handling

### 5.1 Three-tier classification

| Tier | Behavior |
|---|---|
| WARNING | Validator emits a suggested parameter mutation. Skill writes the warning to `state.pending_warnings[]` and returns `status: "warning_pending_decision"`. The LLM agent surfaces the suggestion to the user. On accept, the skill is re-invoked with `accept_warning_mutation: <id>` and applies the mutation, re-running the affected phase. On decline, the skill is re-invoked with `decline_warning_mutation: <id>`, records the decision in `state.json`, and proceeds. |
| RETRYABLE | Mutation-driven retry up to 3 times, no user interaction. Each retry must change parameters or flags. Examples: mdrun OOM, clear pressure-coupling divergence. |
| FATAL | Immediate stop and reported cause. No user override. Examples: PDB parse failure, missing required state key, exhausted retry budget, unsupported variant lacking manual prerequisites. |

### 5.2 WARNING payload

```json
{
  "status": "warning_pending_decision",
  "warning_id": "uuid",
  "step": 7,
  "phase": "npt",
  "metric": "density",
  "observed": 985.2,
  "expected_range": [995, 1005],
  "suggested_mutation": {
    "target": "npt.mdp",
    "changes": {"tau_p": "2.0 → 5.0", "compressibility": "4.5e-5 → 4.5e-5"},
    "rationale": "barostat coupling too tight; relaxing should re-equilibrate density"
  }
}
```

### 5.3 Retry mutation rules (encoded in `lib/validators.py`)

| Cause | Mutation |
|---|---|
| `command_error` | Change CLI flag (`-maxwarn`, `-ntomp`, output filename split) |
| `grompp_warning` | Adjust `.mdp` coupling / constraint values |
| `topology_mismatch` | Roll back topology backup, re-verify include order and molecule counts, regenerate topology |
| `charge_neutralization` | Change `genion` ion concentration, species, or selection group |
| `unstable_energy` | Reduce `nsteps`, soften `dt`, strengthen restraints |
| `temperature_coupling` | Adjust `tau_t`, change coupling group |
| `pressure_coupling` | Adjust `tau_p`, `compressibility`, or barostat type |
| `analysis_not_converged` | Extend production length or re-run equilibration |
| `missing_input` | Surface missing input, re-plan |
| `unsupported_variant` | Halt automation, require manual prerequisites (FATAL) |

Every retry appends to `state.retry_history[]` with `{step, phase, tier, cause, remediation, timestamp}`. Reuse of identical command string and parameter set is blocked by `lib/validators.py`.

### 5.4 Retry budget separation

- WARNING retries do not count against the 3-retry RETRYABLE budget.
- `state.retry_history[]` distinguishes via `tier` field.
- The identical-command-and-parameters block applies to both tiers.

### 5.5 Non-interactive mode

- All skills accept `interactive: false`. When set, WARNINGs are automatically declined and execution proceeds. The auto-decline is recorded in `state.retry_history[]` with `tier: "warning"` and `cause: "auto_decline_noninteractive"`.

### 5.6 Safety contracts

- **Topology backup mandatory.** `topol.top.bak` must exist before Step 3 or Step 5 invocation. Proceeding without backup is FATAL.
- **Hardware profile mandatory.** md-runner refuses to start if `state.hardware` is absent.
- **Large-file protection.** The LLM must not read raw `.xvg`, `.xtc`, `.trr`. All analyses go through `lib/xvg_parser` or illustrator.
- **External-tool graceful degradation.** illustrator attempts PyMOL → VMD → matplotlib-only. Missing renderer triggers WARNING and falls back to plots and report only.

## 6. Testing

### 6.1 Test layers

```
tests/
├── unit/
│   ├── test_state.py
│   ├── test_validators.py
│   ├── test_xvg_parser.py
│   ├── test_tutorial_registry.py
│   ├── test_mdp_templates.py
│   └── test_retry_mutation.py
├── integration/
│   ├── test_env_builder_lysozyme.py
│   ├── test_env_builder_membrane.py
│   ├── test_env_builder_ligand.py
│   ├── test_md_runner_minimal.py
│   ├── test_md_runner_warning_flow.py
│   └── test_illustrator_dryrun.py
├── contract/
│   ├── test_env_builder_io.py
│   ├── test_md_runner_io.py
│   ├── test_illustrator_io.py
│   └── test_state_handoff.py
└── regression/
    ├── regression_lysozyme.sh
    ├── regression_kalp15.sh
    ├── regression_protein_ligand.sh
    ├── regression_umbrella.sh
    ├── regression_biphasic.sh
    ├── regression_fe_methane.sh
    ├── regression_fe_ethanol.sh
    └── regression_virtual_sites.sh
```

### 6.2 Required test cases

| Case | Target |
|---|---|
| `1UBQ.pdb` → env-builder → `stage1_env/` populated | Step 0–5 end-to-end |
| Pre-populated `stage1_env/` → md-runner only | Independent entry |
| External `.xtc` + minimal `state.json` → illustrator only | Independent entry |
| Full pipeline → `state.last_completed_stage` progresses env → md → viz | Chained execution |
| Injected grompp warning → RETRYABLE 3 retries → FATAL | Retry budget |
| Injected density deviation → WARNING `pending_decision` returned | WARNING branch |
| `accept_warning_mutation` re-invocation → parameter applied and phase re-run | WARNING accept |
| `decline_warning_mutation` re-invocation → recorded and next step proceeds | WARNING decline |
| `interactive: false` + WARNING → auto-decline | Non-interactive mode |
| Step 3 entered without `topol.top.bak` → FATAL | Safety contract |
| Identical command and parameters reused → blocked | Mutation rule |
| PyMOL absent → VMD fallback → both absent → matplotlib-only + WARNING | Graceful degradation |

### 6.3 Environment and performance

- **Unit tests** run without GROMACS installed. `gmx_wrapper` is mockable.
- **Integration tests** use small PDBs (e.g., 1UBQ, short peptides) and short `nsteps` (tens to hundreds). CI target: under 5 minutes.
- **Regression tests** run locally or on nightly schedule. Each tutorial runs a minimum-length production and compares metrics only.

### 6.4 TDD implementation order (consumed by writing-plans)

1. `lib/state.py`
2. `lib/validators.py`
3. `lib/tutorial_registry.py`
4. `lib/gmx_wrapper.py` (mock-first)
5. `lib/mdp_templates/` and `lib/xvg_parser.py`
6. `skills/env-builder/`
7. `skills/md-runner/`
8. `skills/illustrator/`
9. Document refresh: `LLM_TUTORIAL_GUIDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, `SKILLS_OVERVIEW.md`
10. Regression scripts rewrite

Tests precede implementation at every step.

## 7. Out of Scope

- CHARMM-GUI web-service integration or downloaded-file ingestion (a future option if the local replication path turns out insufficient).
- New tutorial protocols beyond the eight already present in `docs/tutorial/`.
- Replacement of `docs/tutorial/tutorial_index.json` schema. The redesign refreshes routing guidance and adds optional fields where needed but does not break the existing index format.
- Re-architecting the immutable Step 0–8 contract. The 3-skill split maps onto the existing step numbering.

## 8. Open Items for Implementation Plan

- Final shape of `lib/mdp_templates/` (single Python module vs. template files + renderer).
- Concrete graceful-degradation matrix for illustrator (which subset of analyses remains when PyMOL/VMD/ffmpeg/plotly are individually missing).
- Whether `runs/<tag>_<timestamp>/` should retain prior runs by default or be garbage-collected.

These are deferred to the implementation plan (`writing-plans` step).
