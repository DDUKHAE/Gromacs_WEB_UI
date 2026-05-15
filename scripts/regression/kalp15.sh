#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh KALP15_in_DPPC inputs/kalp15.pdb \
  "membrane protein in DPPC" \
  '{"membrane_composition": {"DPPC": 128}}'
