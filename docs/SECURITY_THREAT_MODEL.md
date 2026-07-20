# LLM Runner Threat Model

The web runner executes an external LLM CLI through a PTY. The CLI is not a
trusted boundary: prompts, uploaded PDB files, generated topology files, and
tool output can all contain attacker-controlled text.

## Current controls

- Run identifiers are format-checked and resolved below the `runs/` directory.
- Uploaded PDB files are size-limited and stored inside the run workspace.
- Permission prompts are surfaced as explicit WebSocket events. The web API
  rejects `auto_approve=true`; adapters never add permission-bypass flags.
- Run logs and artifacts are served only through validated run paths.

## Residual risks

- A malicious prompt can attempt shell injection through the LLM tool layer.
- The current PTY is not a container, namespace, or network isolation boundary.

## Deployment requirements

Production deployments must run the service as a non-privileged account in a
dedicated workspace, deny access to secrets, and place the runner behind a
container or equivalent sandbox before enabling any future unattended mode.
Until then, interactive approval is mandatory. Network egress and resource
limits should be enforced by the deployment environment.

GROMACS execution and sandbox validation are tracked as execution-dependent
work in `docs/plans/tier_c_implementation.md`; this document does not claim
those gates are complete.
