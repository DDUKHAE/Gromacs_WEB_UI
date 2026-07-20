#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh \
  Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol \
  inputs/ethanol.pdb "ethanol hydration free energy" \
  '{"solute_topology": "inputs/ethanol.itp",
    "coulomb_vdw_lambda_schedule": {"coul":[0,0.5,1.0],"vdw":[0,0.5,1.0]}}'
