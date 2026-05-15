#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh Umbrella_Sampling \
  inputs/umbrella.pdb "umbrella sampling pmf" \
  '{"reaction_coordinate_definition": {"groups": ["A","B"], "init": 0.0},
    "window_schedule_defined": true}'
