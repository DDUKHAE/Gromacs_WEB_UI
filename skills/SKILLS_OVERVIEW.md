# Skills Overview — GROMACS Harness

This document lists the three top-level skills the LLM agent invokes
and the internal `lib/` modules they share. The old 7-skill layer was
removed during the 2026-05-14 redesign.

## Skill Directory Layout

```
skills/
├── env_builder/                # Skill 1 — Step 0–5 (environment build)
│   ├── SKILL.md
│   ├── env_builder.py
│   └── references/
├── md_runner/                  # Skill 2 — Step 6–7 (MD execution)
│   ├── SKILL.md
│   ├── md_runner.py
│   └── references/
└── illustrator/                # Skill 3 — Step 8 (analysis + viz)
    ├── SKILL.md
    ├── illustrator.py
    └── references/

lib/                            # Internal helpers (no SKILL.md)
├── state.py
├── validators.py
├── gmx_wrapper.py
├── xvg_parser.py
├── tutorial_registry.py
└── mdp_templates/
```

## Skill Roster

| Skill ID | Folder | Step Range | Trigger |
|---|---|---|---|
| `env-builder` | `skills/env_builder/` | Step 0–5 | A PDB + prompt are available and an MD environment is needed |
| `md-runner` | `skills/md_runner/` | Step 6–7 | Workspace has stage1_env/ artifacts |
| `illustrator` | `skills/illustrator/` | Step 8 | Workspace has stage2_md/ trajectory + .edr |

Each skill is **independently invokable** and the three can be
**chained** in order. The file-based contract is documented in each
skill's `SKILL.md`.

## State Contract

All skills read and write a single `workspace/state.json`. Step 0–8
keys are preserved exactly; the user-facing stage labels
(`env`/`md`/`viz`) are stored in `last_completed_stage`. See
`ARCHITECTURE.md` for the full Step 0–8 contract.

## Internal `lib/`

| Module | Responsibility |
|---|---|
| `state.py` | atomic state.json R/W + entry-gate validators |
| `validators.py` | PASS / WARNING / RETRYABLE / FATAL judgments + retry contract |
| `gmx_wrapper.py` | `gmx` subprocess with error classification + topology backup |
| `xvg_parser.py` | downsampled JSON for `.xvg` files |
| `tutorial_registry.py` | tutorial index/manifest loader + routing decision |
| `mdp_templates/` | base `.mdp` templates for all phases (em/nvt/npt/production/ions/umbrella/free_energy) |

## Versioning

Each `SKILL.md` carries `metadata.version` using semantic versioning.
Breaking input/output schema changes bump the major version.
