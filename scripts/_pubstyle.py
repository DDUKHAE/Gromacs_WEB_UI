"""Shared publication matplotlib style. Import for side effect: apply_style()."""
import matplotlib as mpl


def apply_style() -> None:
    mpl.rcParams.update({
        "figure.dpi": 300, "savefig.dpi": 300,
        "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 9,
        "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
        "axes.linewidth": 0.6, "lines.linewidth": 1.0,
        "savefig.bbox": "tight", "pdf.fonttype": 42,  # editable text in Illustrator
    })
