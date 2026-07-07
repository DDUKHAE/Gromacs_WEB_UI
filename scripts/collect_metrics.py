#!/usr/bin/env python3
"""Extract ACR, step failures, and timing from benchmark run directories.

Usage:
    python scripts/collect_metrics.py \
        --results-dir benchmark_results/ \
        --output docs/results/table1.csv
"""
import argparse
import csv
import json
from pathlib import Path
from collections import defaultdict

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
# 실제 어댑터 키 (web/llm_adapters/__init__.py)
LLMS = ["claude", "codex", "gemini"]


def acr(results: list[dict]) -> float:
    """Autonomous Completion Rate = fraction with status='completed'."""
    if not results:
        return float("nan")
    return sum(1 for r in results if r["status"] == "completed") / len(results)


def mean_elapsed_min(results: list[dict]) -> str:
    # elapsed_s는 run_benchmark.py에서 클라이언트 측 time.time()으로 기록됨
    vals = [r["elapsed_s"] for r in results if isinstance(r.get("elapsed_s"), (int, float))]
    if not vals:
        return "N/A"
    return f"{sum(vals) / len(vals) / 60:.1f}"


def first_fail_step(results: list[dict]) -> str:
    counts: dict[int, int] = defaultdict(int)
    for r in results:
        if r["status"] != "completed" and r.get("last_step") is not None:
            counts[int(r["last_step"])] += 1
    if not counts:
        return "-"
    return str(dict(sorted(counts.items())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--output", default="docs/results/table1.csv")
    args = ap.parse_args()

    rows = []
    results_dir = Path(args.results_dir)

    for tutorial in TUTORIALS:
        row = {"tutorial": tutorial}
        safe = tutorial.replace("/", "_")
        for llm in LLMS:
            files = sorted(results_dir.glob(f"**/{safe}_{llm}_run*.json"))
            runs = [json.loads(f.read_text()) for f in files]
            row[f"{llm}_acr"] = f"{acr(runs):.2f}" if runs else "N/A"
            row[f"{llm}_n"] = len(runs)
            row[f"{llm}_elapsed_min"] = mean_elapsed_min(runs)
            row[f"{llm}_fail_steps"] = first_fail_step(runs)
        rows.append(row)

    fieldnames = (
        ["tutorial"] +
        [f"{llm}_{m}" for llm in LLMS for m in ["acr", "n", "elapsed_min", "fail_steps"]]
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Table 1 data written to {args.output}")


if __name__ == "__main__":
    main()
