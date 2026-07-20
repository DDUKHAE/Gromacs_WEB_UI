#!/usr/bin/env python3
"""FEP convergence figure: cumulative dG vs lambda (barint.xvg) and window overlap (hist.xvg).

Companion to plot_validation.py. Uses lib.xvg_parser so parsing stays consistent with
the rest of the pipeline. plot_validation.py remains the only source for the Figure 2
three-panel composite; illustrator remains the source of truth for raw scientific plots.

Usage:
    python scripts/plot_fep_convergence.py \
        --barint runs/<fep_id>/barint.xvg \
        --hist   runs/<fep_id>/hist.xvg \
        --output docs/figures/fig3_fep.pdf
"""
import argparse
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import xvg_parser
from _pubstyle import apply_style


def _cols(path):
    return xvg_parser.parse_text(Path(path).read_text())["columns"]


def main():
    apply_style()
    ap = argparse.ArgumentParser()
    ap.add_argument("--barint", required=True, help="cumulative dG vs lambda")
    ap.add_argument("--hist", help="per-window dV/dlambda histograms (overlap check)")
    ap.add_argument("--output", default="docs/figures/fig3_fep.pdf")
    args = ap.parse_args()

    ncols = 2 if args.hist else 1
    fig, axes = plt.subplots(1, ncols, figsize=(4 * ncols, 3.3), squeeze=False)

    lam, dg = _cols(args.barint)[0], _cols(args.barint)[1]
    dg_kcal = [val / 4.184 for val in dg]
    axes[0][0].plot(lam, dg_kcal, "o-", color="#1f77b4")
    axes[0][0].axhline(-2.0, ls="--", color="0.5", lw=0.8, label="exp -2.0")
    axes[0][0].set_xlabel(r"$\lambda$")
    axes[0][0].set_ylabel(r"cumulative $\Delta G$ (kcal/mol)")
    axes[0][0].set_title("BAR convergence")
    axes[0][0].legend(fontsize=7)

    if args.hist:
        cols = _cols(args.hist)
        x = cols[0]
        for y in cols[1:]:
            axes[0][1].plot(x, y, lw=0.6)
        axes[0][1].set_xlabel(r"$dV/d\lambda$")
        axes[0][1].set_ylabel("count")
        axes[0][1].set_title("Window overlap")

    plt.tight_layout()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.output, dpi=300)
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
