# Lean Code Cleanup Design

## Scope

Apply the approved over-engineering review without changing the MD pipeline's
observable behavior.

## Changes

- Delete unreachable ACPYPE support, the obsolete tutorial expectation table,
  placeholder HTML reporting, analysis stubs, and unused function arguments.
- Use protocol-contract phase definitions as the one source of truth and keep
  one shared MDP-field mapping.
- Remove duplicate state writes, metadata reads, membrane validation, and
  production-completion detection while retaining their existing owners.

## Verification

Add or update focused tests only where behavior moves between modules, then
run the affected tests and the complete pytest suite.
