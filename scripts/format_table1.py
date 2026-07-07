#!/usr/bin/env python3
"""Format table1.csv as Markdown or LaTeX for the paper.

Usage:
    python scripts/format_table1.py --input docs/results/table1.csv
    python scripts/format_table1.py --input docs/results/table1.csv --format latex
"""
import argparse
import csv

TUTORIAL_SHORT = {
    "Lysozyme_in_water":                                          "Lysozyme in water",
    "KALP15_in_DPPC":                                            "KALP15 in DPPC",
    "Protein_Ligand_Complex":                                    "Protein–ligand complex",
    "Umbrella_Sampling":                                         "Umbrella sampling",
    "Building_Biphasic_Systems":                                 "Biphasic system",
    "Free_Energy_Calculations_Methane_in_Water":                 "FEP: methane (water)",
    "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol": "FEP: ethanol (water)",
    "Virtual_Sites":                                             "Virtual sites",
}


def fmt_markdown(rows: list[dict]) -> None:
    print("| Tutorial | Claude ACR | Codex ACR | Gemini ACR |")
    print("|----------|-----------|----------|-----------|")
    for r in rows:
        name = TUTORIAL_SHORT.get(r["tutorial"], r["tutorial"])
        print(f"| {name} | {r['claude_acr']} | {r['codex_acr']} | {r['gemini_acr']} |")


def fmt_latex(rows: list[dict]) -> None:
    print(r"\begin{table}[ht]")
    print(r"\centering")
    print(r"\caption{Autonomous Completion Rate (ACR) per tutorial and LLM.}")
    print(r"\label{tab:acr}")
    print(r"\begin{tabular}{lccc}")
    print(r"\toprule")
    print(r"Tutorial & Claude & Codex & Gemini \\")
    print(r"\midrule")
    for r in rows:
        name = TUTORIAL_SHORT.get(r["tutorial"], r["tutorial"])
        name_tex = name.replace("–", r"\textendash{}")
        print(f"{name_tex} & {r['claude_acr']} & {r['codex_acr']} & {r['gemini_acr']} \\\\")
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print(r"\end{table}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="docs/results/table1.csv")
    ap.add_argument("--format", choices=["markdown", "latex"], default="markdown")
    args = ap.parse_args()

    with open(args.input) as f:
        rows = list(csv.DictReader(f))

    if args.format == "markdown":
        fmt_markdown(rows)
    else:
        fmt_latex(rows)


if __name__ == "__main__":
    main()
