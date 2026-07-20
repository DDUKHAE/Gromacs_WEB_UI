#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh Lysozyme_in_water 1UBQ.pdb \
  "lysozyme in water basic md" "{}"
