#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh Building_Biphasic_Systems \
  inputs/biphasic.pdb "biphasic system at interface" \
  '{"phase_components": ["water","octanol"], "composition_ratio": [1,1]}'
