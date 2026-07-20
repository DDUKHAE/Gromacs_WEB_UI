# Resolved Run Plan

The browser remains the source of user input: PDB upload, force field, water,
box, ions, expert MD controls, optional tutorial selection, and LLM choice.
Before any direct or LLM execution, the backend compiles these values into
`resolved_run_plan.json`.

## Authority and compatibility

`user_locked_settings` are authoritative execution values. A selected or
auto-detected tutorial supplies a pipeline variant, validation profile,
stage-specific context documents, and recommendations. Tutorial defaults do
not silently replace user settings.

If a user setting differs from a tutorial recommendation, the plan records an
`experimental_override` warning. Missing required inputs are `blocked` and
prevent execution. The plan is SHA-256 protected; the protocol contract binds
to that hash and the runner rejects a changed plan.

## Web flow

```text
POST /api/runs (PDB + settings + tutorial choice)
  -> resolved_run_plan.json
  -> protocol_contract.json + tutorial_context/*.md
  -> LLM or direct skill runner
```

`GET /api/runs/{run_id}/plan` returns the verified plan. The audit endpoint
also includes it, so the UI can display user locks, compatibility warnings,
and the plan hash without changing its existing configuration workflow.
