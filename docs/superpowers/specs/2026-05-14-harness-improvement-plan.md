# Harness Improvement Plan for Autonomous GROMACS Delegation

## Goal
- Make this harness robust enough that repetitive GROMACS pipelines can be delegated to the LLM with minimal manual intervention.
- Success target: same code path should run across multiple protein PDBs without run-to-run contamination and with predictable failure handling.

## Current Blocking Issues (Observed)
1. NVT instability across multiple proteins (`validation_failed` at NVT).
2. Retry logic still hits fingerprint dead-ends in some branches (e.g., `genion`).
3. Physical quality recovery ladder is incomplete (LLM retries runtime flags more than physics knobs).
4. Validation/analyzer availability depended on `numpy` env state (now partially mitigated by stdlib refactor, needs regression proof).

## Definition of Done
- Regression matrix (`1UBQ`, `1CRN`, `1AKI`) runs with:
  - no cross-run contamination,
  - no retry fingerprint dead-end,
  - deterministic failure classification,
  - at least one system reaches `phase_validation` beyond NVT under default conservative protocol.
- Harness emits machine-readable run report per run directory.

## Workstreams

### WS1. Run Isolation and Reproducibility (High)
- Keep per-run workdir (`runs/<target>_<timestamp>`).
- Persist full input snapshot and generated command list into run dir.
- Add explicit `run_id` and `run_dir` to final JSON.

### WS2. Command Argument Safety (High)
- Replace broad state refresh with command-schema mapping only.
- Add preflight assert for illegal flag/value pairs (e.g., boolean flags receiving path strings).
- Add unit-like smoke checks for compiled commands before execution.

### WS3. Topology/GRO Consistency Gates (High)
- After `solvate` and `genion`, run atom/molecule consistency checks.
- On mismatch, auto-rollback topology backup and retry with modified parameters.
- Include check details in `retry_history`.

### WS4. Physics Recovery Ladder (High)
- Add phase-specific fallback ladders:
  - NVT: lower `dt`, simplify `tc-grps`, stronger restraints, short warmup phase.
  - NPT: conservative barostat params and staged continuation.
- Recovery decisions should be triggered by parsed error signatures (LINCS, unsettled water, NaN energy).

### WS5. Retry Engine Hardening (Medium)
- Guarantee unique fingerprint by construction for every retry attempt.
- Separate “physics retry” and “runtime retry” dimensions and track both in state.

### WS6. Validation/Analysis Reliability (Medium)
- Keep validator/analyzer numpy-free (stdlib only).
- Add self-check at startup: validator/analyzer import + capability report.

### WS7. Regression Harness (High)
- Maintain `scripts/regression_multi_pdb.sh` as baseline.
- Add concise summary artifact (`/tmp/harness_regression_summary.json`).
- Add pass/fail gates suitable for CI later.

## Execution Plan (Phased)

### Phase A (Now)
1. Stabilize retry engine uniqueness (`genion`, `mdrun`, `grompp`).
2. Add NVT fallback ladder v1 (physics-first).
3. Add startup capability report in final output.

### Phase B
1. Add warmup micro-phase before NVT (new protocol step).
2. Strengthen topology/gro gate with rollback-aware remediation.
3. Expand regression outputs.

### Phase C
1. Tune default conservative templates based on regression evidence.
2. Add CI-ready non-interactive regression job.

## Metrics to Track
- `nvt_failure_rate` across matrix.
- `fingerprint_deadend_count` per run.
- `topology_mismatch_count` per run.
- `% runs reaching npt/md`.

## Immediate Next Implementation Tasks
1. Implement startup capability report (`validator_loaded`, `analyzer_loaded`, env info) in run result.
2. Patch `genion` retry mutation to always produce distinct executable command signatures.
3. Add NVT fallback profile switch (`tc-grps=System`, `tau_t=0.05`, `dt` downshift, extra restraints flag).

