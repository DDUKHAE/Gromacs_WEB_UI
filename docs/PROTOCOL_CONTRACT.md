# Executable Tutorial Protocol Contract

`protocol_contract.json` turns a selected tutorial from prompt context into a
versioned, machine-checkable run artifact. It is created when a web run is
created with a tutorial id, or when the environment builder auto-routes a
direct run.

For web runs, `resolved_run_plan.json` is created first. It makes the browser
settings authoritative and records tutorial differences as compatibility
warnings; the protocol contract binds to the plan SHA-256 rather than silently
replacing those settings with tutorial defaults.

The contract records:

- selected tutorial, pipeline variant, validation profile, and required phase sequence;
- tutorial defaults merged with explicit System Builder choices;
- SHA-256 fingerprints for the manifest and referenced tutorial documents;
- a checksum over the entire contract; and
- expert-mode MDP controls that must be propagated into rendered MDP files.

## Stage-specific Markdown context packs

The contract generator also writes three derived Markdown files below
`tutorial_context/`: `environment.md`, `simulation.md`, and `analysis.md`.
Each pack contains only the tutorial documents used by its pipeline stage,
bounded excerpts from the original Markdown, and a source path plus SHA-256
for every excerpt. The LLM runner instructs the agent to read the relevant
pack immediately before each skill entry point. This keeps explanatory,
human-readable protocol context available without placing the entire tutorial
corpus into every model turn.

Packs are not editable user instructions: each pack hash is recorded inside
`protocol_contract.json`, and the builder/runner reject a checksum mismatch.

The environment builder verifies the checksum before setup and uses locked
force field, water, box, and ion choices. The MD runner gives contract MDP
controls precedence over agent-supplied phase overrides and rejects a rendered
MDP that changes a locked value. The run audit exposes the checksum result.

This is intentionally a narrow allow-list, not a claim that arbitrary LLM
shell commands are sandboxed. New systems or exceptions must be added to a
tutorial manifest and validation profile; external literature may inform that
change, but it must not silently modify an existing run contract.
