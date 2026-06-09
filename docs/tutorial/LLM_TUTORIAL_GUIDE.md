# LLM Tutorial Guide

## Purpose

This guide is the routing decision document consumed by the
`env-builder` skill (via `lib/tutorial_registry.py`) when a new
workspace is initialized. It tells `env-builder` which tutorial to
follow given a PDB file, user prompt, and optional prerequisites.

## Decision Tree

```
1. Apply keyword match on `prompt`
   - umbrella / pmf / pulling / wham         → Umbrella_Sampling
   - methane + free energy                   → Free_Energy_Calculations_Methane_in_Water
   - ethanol + hydration free energy         → Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol
   - biphasic / interface / two-phase        → Building_Biphasic_Systems
   - virtual sites / vsite                   → Virtual_Sites
   - ligand / protein-ligand / binding       → Protein_Ligand_Complex
   - membrane / DPPC / lipid / bilayer       → KALP15_in_DPPC
   - protein in water / aqueous / lysozyme   → Lysozyme_in_water

2. If no keyword match: inspect PDB hints
   - has_membrane  → KALP15_in_DPPC
   - has_ligand    → Protein_Ligand_Complex
   - has_protein   → Lysozyme_in_water (fallback)

3. Look up entry in tutorial_index.json:
   - required_inputs − {protein_pdb} must be present in prerequisites
     (ligand_itp satisfies ligand_structure)
   - if unsupported_autonomy_level != "none" AND any prerequisites
     are missing → raise UnsupportedTutorialError
```

## Confidence

- `high` — keyword match AND prerequisites complete.
- `medium` — keyword match BUT prerequisites are not strict.
- `low` — fell through to fallback (no keyword match).

## Prerequisite Schemas

See `skills/env_builder/references/prerequisite_schema.md` for the
exact key set each tutorial requires.

## Source Priority

1. Per-tutorial `tutorial.manifest.json` is runtime truth.
2. `tutorial_index.json` is routing/index truth.
3. Tutorial markdown parts are rationale/reference.

## Stop Conditions

`env-builder` raises `UnsupportedTutorialError` and refuses to proceed
when:

- Prerequisites for a derived tutorial are missing.
- The selected tutorial has `unsupported_autonomy_level: research_only`
  (currently Virtual_Sites).

## Mandatory Rules Binding

Whatever tutorial is selected, the safety contracts in `AGENTS.md`
still apply: state.json keys at each step, `topol.top.bak` before
Steps 3 and 5, hardware profile before Step 6+, no identical retry,
no raw `.xvg`/trajectory reads by the LLM.
