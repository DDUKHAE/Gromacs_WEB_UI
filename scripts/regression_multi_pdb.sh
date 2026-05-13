#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

declare -a PDBS=("1UBQ.pdb:ubq" "1CRN.pdb:crn" "1AKI.pdb:aki")

for item in "${PDBS[@]}"; do
  pdb="${item%%:*}"
  target="${item##*:}"
  out="/tmp/${target}_regression.json"
  echo "== Running ${pdb} (${target}) =="
  conda run -n GROMACS python3 run_autonomy.py "{\"cwd\":\"$ROOT_DIR\",\"prompt\":\"run standard protein in water MD\",\"pdb_path\":\"$ROOT_DIR/$pdb\",\"target_name\":\"$target\",\"execute\":true}" > "$out" || true
  python3 - <<PY
import json
p="$out"
obj=json.load(open(p))
print("status:", obj.get("status"), obj.get("message"))
if obj.get("status")!="success":
    print("phase:", obj.get("phase") or obj.get("failed_command",{}).get("phase"))
    print("why:", obj.get("validation",{}).get("reason") or obj.get("result",{}).get("summary"))
print("---")
PY
done

python3 scripts/regression_summary.py >/dev/null || true
