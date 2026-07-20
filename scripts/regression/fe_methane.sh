#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh \
  Free_Energy_Calculations_Methane_in_Water \
  inputs/methane.pdb "methane hydration free energy" \
  '{"solute_topology": "inputs/methane.itp",
    "lambda_schedule": [0.0,0.25,0.5,0.75,1.0]}'
