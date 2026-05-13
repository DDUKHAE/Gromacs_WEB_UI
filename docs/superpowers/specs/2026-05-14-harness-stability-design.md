# Harness Stability Design (GROMACS Autonomy)

## Goal
Increase autonomous-run reliability by enforcing state-contract consistency, bounded retries, consistent GROMACS binary usage, and deterministic preflight/error reporting.

## Scope
- Runtime: `run_autonomy.py`
- Skills: `gmx-executor`, `system-validator`, `trajectory-analyzer`, `state-manager`
- Docs: `AGENTS.md`, `docs/pipeline_contract.md`, `ARCHITECTURE.md`

## Design Decisions
1. State contract is authoritative at runtime: update `latest_gro` and step-required keys whenever files transition.
2. Retry policy is hard-bounded to 3 attempts total; reporting must never exceed 3.
3. `gmx_bin` flows end-to-end from orchestrator to validator/analyzer.
4. Ionization state uses measured topology-derived counts and computed net ionic charge, not fixed constants.
5. Step start always reloads `simulation_state.json` to honor AGENTS state-tracking rule.

## Error and Health Model
- Preflight uses resolved `gmx_bin` and records hardware tuning metadata into `hardware_specs`.
- Command failures preserve retry history and command fingerprints.
- Final status claims require command-level verification evidence.

## Out of Scope
- Full MD physical validation profile redesign.
- Multi-tutorial manifest schema expansion.
