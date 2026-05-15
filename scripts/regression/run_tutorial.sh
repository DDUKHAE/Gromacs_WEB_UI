#!/usr/bin/env bash
# Usage: run_tutorial.sh <tutorial_id> <pdb_path> [prompt] [prereq_json]
set -euo pipefail

TUTORIAL_ID="${1:?tutorial id required}"
PDB="${2:?pdb path required}"
PROMPT="${3:-run a basic protein simulation in water}"
PREREQ_JSON="${4:-{}}"
TAG="${TUTORIAL_ID}_$(date +%Y%m%d_%H%M%S)"
WS="runs/${TAG}"
mkdir -p "${WS}"

python -c "
from pathlib import Path
import json
from skills.env_builder import build_environment
from skills.md_runner import run_simulation
from skills.illustrator import illustrate

ws = Path('${WS}').resolve()
build_environment(pdb_path=Path('${PDB}').resolve(),
                  prompt='${PROMPT}',
                  workspace_dir=ws,
                  prerequisites=json.loads('${PREREQ_JSON}'),
                  interactive=False)
run_simulation(workspace_dir=ws, phase_overrides={}, interactive=False)
illustrate(workspace_dir=ws, animation={'enabled': False})
print(f'OK ${TUTORIAL_ID} -> {ws}/stage3_viz/report.md')
"
