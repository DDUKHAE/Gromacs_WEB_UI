#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh Virtual_Sites \
  inputs/linear.pdb "virtual sites linear molecule" \
  '{"molecule_topology": "inputs/linear.itp",
    "virtual_site_definition": "inputs/vsite.itp"}'
