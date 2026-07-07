#!/usr/bin/env python3
"""Run all 72 benchmark experiments via the Web UI API.

Usage:
    python scripts/run_benchmark.py \
        --base-url http://localhost:8000 \
        --llm claude \
        --runs-per-tutorial 3 \
        --output-dir benchmark_results/claude_2026-07-15/
"""
import argparse
import json
import time
import requests
from pathlib import Path

TUTORIALS = [
    "Lysozyme_in_water",
    "KALP15_in_DPPC",
    "Protein_Ligand_Complex",
    "Umbrella_Sampling",
    "Building_Biphasic_Systems",
    "Free_Energy_Calculations_Methane_in_Water",
    "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol",
    "Virtual_Sites",
]

# Terminal states per web/run_reader.py:derive_status()
# "error" 상태는 없음; paused·aborted도 프로세스가 종료된 상태
_TERMINAL_STATES = {"completed", "failed", "aborted", "paused"}

POLL_INTERVAL_S = 30


def run_experiment(base_url: str, tutorial_id: str, llm: str, pdb_path: Path) -> dict:
    start = time.time()

    # 필드명은 pdb_file (server.py:427의 UploadFile = File(...) 파라미터명)
    with open(pdb_path, "rb") as f:
        r = requests.post(
            f"{base_url}/api/runs",
            files={"pdb_file": (pdb_path.name, f, "application/octet-stream")},
            data={
                "tutorial_id": tutorial_id,
                "llm": llm,
                "auto_approve": "true",  # 없으면 승인 게이트에서 무한 대기
            },
        )
    r.raise_for_status()
    run_id = r.json()["run_id"]

    # 완료될 때까지 폴링
    while True:
        status_r = requests.get(f"{base_url}/api/runs/{run_id}")
        status_r.raise_for_status()
        state = status_r.json()
        if state["status"] in _TERMINAL_STATES:
            break
        time.sleep(POLL_INTERVAL_S)

    elapsed_s = time.time() - start
    return {
        "run_id": run_id,
        "status": state["status"],
        "tutorial_id": tutorial_id,
        "llm": llm,
        "last_completed_stage": state.get("last_completed_stage"),
        "last_step": state.get("current_step"),
        "elapsed_s": round(elapsed_s, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--llm", required=True, choices=["claude", "codex", "gemini"])
    ap.add_argument("--runs-per-tutorial", type=int, default=3)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument(
        "--pdb-dir",
        default="tutorial_data",
        help="Directory containing <tutorial_id>/input.pdb files",
    )
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = []

    for tutorial in TUTORIALS:
        pdb = Path(args.pdb_dir) / tutorial / "input.pdb"
        if not pdb.exists():
            print(f"SKIP {tutorial}: no input.pdb at {pdb}")
            continue
        for run_num in range(1, args.runs_per_tutorial + 1):
            print(f"Running {tutorial} / {args.llm} / run {run_num}...")
            try:
                r = run_experiment(args.base_url, tutorial, args.llm, pdb)
            except Exception as exc:
                r = {
                    "run_id": None,
                    "status": "api_error",
                    "tutorial_id": tutorial,
                    "llm": args.llm,
                    "error": str(exc),
                    "elapsed_s": 0,
                }
            r["run_num"] = run_num
            results.append(r)
            safe_name = tutorial.replace("/", "_")
            (out / f"{safe_name}_{args.llm}_run{run_num}.json").write_text(
                json.dumps(r, indent=2)
            )
            print(f"  -> {r['status']} in {r['elapsed_s']}s")

    (out / "summary.json").write_text(json.dumps(results, indent=2))
    completed = sum(1 for r in results if r["status"] == "completed")
    print(f"Done. {completed}/{len(results)} completed. Results in {out}/")


if __name__ == "__main__":
    main()
