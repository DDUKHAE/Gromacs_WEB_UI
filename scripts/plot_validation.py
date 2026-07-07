#!/usr/bin/env python3
"""Plot RMSD, Rg, and potential energy from GROMACS .xvg files (Figure 2).

Usage:
    python scripts/plot_validation.py \
        --rmsd   runs/<id>/rmsd_backbone.xvg \
        --rg     runs/<id>/gyrate.xvg \
        --energy runs/<id>/potential.xvg \
        --output docs/figures/fig2_lysozyme_validation.pdf
"""
import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path


def read_xvg(path: str) -> tuple[list[float], list[float]]:
    x, y = [], []
    with open(path) as f:
        for line in f:
            if line.startswith(("#", "@")):
                continue
            parts = line.split()
            if len(parts) >= 2:
                x.append(float(parts[0]))
                y.append(float(parts[1]))
    return x, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rmsd",   required=True)
    ap.add_argument("--rg",     required=True)
    ap.add_argument("--energy", required=True)
    ap.add_argument("--output", default="fig2_lysozyme.pdf")
    ap.add_argument("--title",  default="Lysozyme in Water — MD Validation")
    args = ap.parse_args()

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))
    fig.suptitle(args.title, fontsize=11)

    t_rmsd, rmsd = read_xvg(args.rmsd)
    axes[0].plot(t_rmsd, [v * 10 for v in rmsd], color="steelblue", linewidth=0.8)
    axes[0].set_xlabel("Time (ns)")
    axes[0].set_ylabel("RMSD (Å)")
    axes[0].set_title("Backbone RMSD")

    t_rg, rg = read_xvg(args.rg)
    axes[1].plot(t_rg, rg, color="darkorange", linewidth=0.8)
    axes[1].set_xlabel("Time (ns)")
    axes[1].set_ylabel("Rg (nm)")
    axes[1].set_title("Radius of Gyration")

    t_e, energy = read_xvg(args.energy)
    axes[2].plot(t_e, energy, color="seagreen", linewidth=0.5)
    axes[2].set_xlabel("Time (ps)")
    axes[2].set_ylabel("Potential Energy (kJ/mol)")
    axes[2].set_title("Potential Energy")

    plt.tight_layout()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.output, dpi=300)
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
