#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh Protein_Ligand_Complex \
  inputs/protein_ligand.pdb \
  "protein-ligand binding simulation" \
  '{"ligand_itp": "inputs/lig.itp"}'
