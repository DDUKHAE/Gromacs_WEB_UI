import shutil
from pathlib import Path
from typing import Any
from lib import state
from lib.state import StateContractError
from lib import gmx_wrapper as GW, xvg_parser


def _trajectory_prefix(s: dict[str, Any]) -> str:
    step7 = s.get("step_outputs", {}).get("step_7", {}) if s else {}
    for key in ("production_gro", "production"):
        if key in step7 and str(step7[key]).endswith(".gro"):
            return Path(step7[key]).stem
    return "production"


def assert_ready(workspace_dir: Path) -> dict[str, Any]:
    s = state.read(workspace_dir)
    state.require_last_stage(s, "md")
    state.require_step_keys(s, ["step_7"])
    prefix = _trajectory_prefix(s)
    ws = Path(workspace_dir)
    for ext in ("tpr", "xtc", "edr"):
        if not (ws / "stage2_md" / f"{prefix}.{ext}").exists():
            raise StateContractError(f"missing {prefix}.{ext}")
    return s


def _viz_dir(ws: Path) -> Path:
    out = Path(ws) / "stage3_viz"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _md_dir(ws: Path) -> Path:
    return Path(ws) / "stage2_md"


def _trjconv_nopbc(ws: Path, prefix: str) -> str:
    """Create PBC-corrected trajectory; skip if already present. Returns new prefix."""
    nopbc = _md_dir(ws) / f"{prefix}_noPBC.xtc"
    if nopbc.exists():
        return f"{prefix}_noPBC"
    GW.run(
        ["trjconv", "-s", f"{prefix}.tpr", "-f", f"{prefix}.xtc",
         "-o", str(nopbc), "-pbc", "mol", "-center"],
        cwd=_md_dir(ws), interactive_inputs=["Protein", "System"],
    )
    return f"{prefix}_noPBC"


def _rmsd(ws: Path, prefix: str, xtc: str | None = None) -> Path:
    out = _viz_dir(ws) / "rmsd.xvg"
    GW.run(
        ["rms", "-s", f"{prefix}.tpr", "-f", f"{xtc or prefix}.xtc",
         "-o", str(out), "-tu", "ns"],
        cwd=_md_dir(ws), interactive_inputs=["Backbone", "Backbone"],
    )
    return out


def _rmsf(ws: Path, prefix: str, xtc: str | None = None) -> Path:
    out = _viz_dir(ws) / "rmsf.xvg"
    GW.run(
        ["rmsf", "-s", f"{prefix}.tpr", "-f", f"{xtc or prefix}.xtc",
         "-o", str(out), "-res"],
        cwd=_md_dir(ws), interactive_inputs=["Protein"],
    )
    return out


def _gyrate(ws: Path, prefix: str, xtc: str | None = None) -> Path:
    out = _viz_dir(ws) / "gyrate.xvg"
    GW.run(
        ["gyrate", "-s", f"{prefix}.tpr", "-f", f"{xtc or prefix}.xtc",
         "-o", str(out)],
        cwd=_md_dir(ws), interactive_inputs=["Protein"],
    )
    return out


def _sasa(ws: Path, prefix: str, xtc: str | None = None) -> Path:
    out = _viz_dir(ws) / "sasa.xvg"
    GW.run(
        ["sasa", "-s", f"{prefix}.tpr", "-f", f"{xtc or prefix}.xtc",
         "-o", str(out)],
        cwd=_md_dir(ws), interactive_inputs=["Protein"],
    )
    return out


def _energy_term(ws: Path, prefix: str, term: str, name: str) -> Path:
    out = _viz_dir(ws) / f"energy_{name}.xvg"
    GW.run(
        ["energy", "-f", f"{prefix}.edr", "-o", str(out)],
        cwd=_md_dir(ws), interactive_inputs=[term, ""],
    )
    return out


def run_core_analyses(workspace_dir: Path) -> dict[str, dict]:
    s = assert_ready(workspace_dir)
    prefix = _trajectory_prefix(s)
    nopbc = _trjconv_nopbc(workspace_dir, prefix)
    out: dict[str, dict] = {}
    out["rmsd"] = xvg_parser.summary(_rmsd(workspace_dir, prefix, xtc=nopbc))
    out["rmsf"] = xvg_parser.summary(_rmsf(workspace_dir, prefix, xtc=nopbc))
    out["gyrate"] = xvg_parser.summary(_gyrate(workspace_dir, prefix, xtc=nopbc))
    try:
        out["sasa"] = xvg_parser.summary(_sasa(workspace_dir, prefix, xtc=nopbc))
    except Exception:
        out["sasa"] = {"count": 0}
    for term, key in (("Potential", "potential"),
                       ("Temperature", "temperature"),
                       ("Density", "density"),
                       ("Pressure", "pressure"),
                       ("Total-Energy", "total")):
        try:
            out[f"energy_{key}"] = xvg_parser.summary(
                _energy_term(workspace_dir, prefix, term, key))
        except Exception:
            out[f"energy_{key}"] = {"count": 0}
    s = state.read(workspace_dir)
    s["step_outputs"].setdefault("step_8", {})["analysis_summaries"] = out
    state.write(workspace_dir, s)
    return out


def _hbond(ws: Path, prefix: str) -> Path:
    out = _viz_dir(ws) / "hbond.xvg"
    GW.run(
        ["hbond", "-s", f"{prefix}.tpr", "-f", f"{prefix}.xtc",
         "-num", str(out)],
        cwd=_md_dir(ws), interactive_inputs=["Protein", "Protein"],
    )
    return out


def _dssp(ws: Path, prefix: str) -> Path:
    out_xpm = _viz_dir(ws) / "dssp.xpm"
    GW.run(
        ["do_dssp", "-s", f"{prefix}.tpr", "-f", f"{prefix}.xtc",
         "-o", str(out_xpm)],
        cwd=_md_dir(ws), interactive_inputs=["Protein"],
    )
    return out_xpm


def _pca(ws: Path, prefix: str) -> tuple[Path, Path]:
    md = _md_dir(ws); viz = _viz_dir(ws)
    GW.run(
        ["covar", "-s", f"{prefix}.tpr", "-f", f"{prefix}.xtc",
         "-o", str(viz / "eigenval.xvg"), "-v", str(viz / "eigenvec.trr")],
        cwd=md, interactive_inputs=["Backbone", "Backbone"],
    )
    GW.run(
        ["anaeig", "-s", f"{prefix}.tpr", "-f", f"{prefix}.xtc",
         "-v", str(viz / "eigenvec.trr"),
         "-2d", str(viz / "pca_proj.xvg"),
         "-first", "1", "-last", "2"],
        cwd=md, interactive_inputs=["Backbone", "Backbone"],
    )
    return viz / "eigenval.xvg", viz / "pca_proj.xvg"


def run_advanced_analyses(workspace_dir: Path) -> dict[str, Any]:
    s = assert_ready(workspace_dir)
    prefix = _trajectory_prefix(s)
    out: dict[str, Any] = {}
    try:
        out["hbond"] = xvg_parser.summary(_hbond(workspace_dir, prefix))
    except Exception as e:
        out["hbond"] = {"status": "skipped", "reason": str(e)[:200]}
    try:
        dssp_xpm = _dssp(workspace_dir, prefix)
        out["dssp"] = {"xpm_path": str(dssp_xpm)}
    except Exception as e:
        out["dssp"] = {"status": "skipped", "reason": str(e)[:200]}
    try:
        eigval, proj = _pca(workspace_dir, prefix)
        out["pca"] = {"eigenval_summary": xvg_parser.summary(eigval),
                      "proj_xvg": str(proj)}
    except Exception as e:
        out["pca"] = {"status": "skipped", "reason": str(e)[:200]}
    s = state.read(workspace_dir)
    s["step_outputs"].setdefault("step_8", {})["advanced_summaries"] = out
    state.write(workspace_dir, s)
    return out


def _run_wham(workspace_dir: Path) -> dict[str, Any]:
    # Caller must have produced tpr-files.dat and pullf-files.dat in stage2_md/.
    out = _viz_dir(workspace_dir) / "pmf.xvg"
    GW.run(
        ["wham", "-it", "tpr-files.dat", "-if", "pullf-files.dat",
         "-o", str(out), "-hist", str(_viz_dir(workspace_dir) / "hist.xvg")],
        cwd=_md_dir(workspace_dir),
    )
    return {"pmf_xvg": str(out),
            "summary": xvg_parser.summary(out)}


def _run_bar(workspace_dir: Path) -> dict[str, Any]:
    # Caller must have produced per-lambda md.edr files in stage2_md/.
    out_log = _viz_dir(workspace_dir) / "bar.log"
    md = _md_dir(workspace_dir)
    edrs = sorted(str(p.name) for p in md.glob("md_l*.edr"))
    if not edrs:
        return {"status": "skipped", "reason": "no md_l*.edr files"}
    result = GW.run(["bar", "-f", *edrs, "-o", str(out_log)], cwd=md)
    dG = None
    for line in (result.stdout + result.stderr).splitlines():
        if line.strip().startswith("total"):
            try:
                dG = float(line.split()[1])
            except (IndexError, ValueError):
                pass
    return {"dG_kJ_per_mol": dG, "log": str(out_log)}


def _run_membrane_analysis(workspace_dir: Path) -> dict[str, Any]:
    return {"status": "stub",
            "note": "membrane thickness, area per lipid, order parameters"}


def _run_protein_ligand_analysis(workspace_dir: Path) -> dict[str, Any]:
    return {"status": "stub",
            "note": "ligand RMSD, binding distance, interaction map"}


def compose_report(workspace_dir: Path) -> Path:
    ws = Path(workspace_dir)
    viz = _viz_dir(ws)
    s = state.read(ws)
    step8 = s["step_outputs"].get("step_8", {})
    analyses = step8.get("analysis_summaries", {})
    advanced = step8.get("advanced_summaries", {})
    variant = step8.get("variant_summary", {})
    lines = []
    lines.append(f"# Simulation Report")
    lines.append("")
    lines.append(f"- Tutorial: `{(s.get('tutorial') or {}).get('id')}`")
    lines.append(f"- Variant: `{(s.get('tutorial') or {}).get('variant')}`")
    lines.append("")
    lines.append("## Core Analysis Summary")
    lines.append("")
    lines.append("| Metric | Mean | Std | Count |")
    lines.append("|---|---|---|---|")
    for name, st in sorted(analyses.items()):
        if st.get("count", 0) == 0:
            continue
        lines.append(f"| {name.upper()} | {st.get('mean','-'):.4g} "
                     f"| {st.get('std','-'):.4g} | {st.get('count')} |")
    lines.append("")
    lines.append("## Plots")
    for png in sorted(viz.glob("*.png")):
        lines.append(f"![{png.stem}]({png.name})")
        lines.append("")
    if advanced:
        lines.append("## Advanced Analyses")
        for k, v in advanced.items():
            lines.append(f"- **{k}**: `{v}`")
        lines.append("")
    if variant:
        lines.append("## Tutorial-specific")
        for k, v in variant.items():
            lines.append(f"- **{k}**: `{v}`")
        lines.append("")
    report = viz / "report.md"
    report.write_text("\n".join(lines))
    s = state.read(ws)
    s["step_outputs"].setdefault("step_8", {})["final_report_path"] = \
        str(report)
    state.write(ws, s)
    return report


def compose_html_report(workspace_dir: Path) -> Path | None:
    try:
        import plotly  # noqa: F401
    except ImportError:
        return None
    # Plotly HTML rendering left as future extension; emit a placeholder.
    viz = _viz_dir(workspace_dir)
    html = viz / "report.html"
    html.write_text("<html><body>See report.md (plotly HTML stub)</body></html>")
    return html


def select_renderer() -> str:
    if shutil.which("pymol"):
        return "pymol"
    if shutil.which("vmd"):
        return "vmd"
    return "none"


_PYMOL_SCRIPT = """
load {gro}, system
load_traj {xtc}, system
frame {frame_index}
hide everything
show cartoon, polymer
show surface, polymer and resi {highlight_resi}
bg_color white
ray 1200, 800
png {out_png}
quit
"""


def render_frame(workspace_dir: Path, frame: str | int,
                 output_path: Path,
                 highlight_resi: str = "1-10") -> Path | None:
    renderer = select_renderer()
    if renderer == "none":
        return None
    ws = Path(workspace_dir)
    s = state.read(ws) if state.path(ws).exists() else {}
    prefix = _trajectory_prefix(s) if s else "production"
    gro = ws / "stage2_md" / f"{prefix}.gro"
    xtc = ws / "stage2_md" / f"{prefix}.xtc"
    if frame == "last":
        frame_idx = -1
    elif frame == "middle":
        frame_idx = 0  # PyMOL doesn't trivially expose count; use 0 as a stub.
    else:
        frame_idx = int(frame)
    if renderer == "pymol":
        script = _PYMOL_SCRIPT.format(
            gro=str(gro), xtc=str(xtc),
            frame_index=frame_idx, highlight_resi=highlight_resi,
            out_png=str(output_path),
        )
        script_path = ws / "stage3_viz" / "render.pml"
        script_path.write_text(script)
        import subprocess
        subprocess.run(["pymol", "-cq", str(script_path)],
                       check=False, capture_output=True)
        return output_path if output_path.exists() else None
    if renderer == "vmd":
        # VMD scripting fallback (minimal).
        script = (f"mol new {gro}\nmol addfile {xtc} waitfor all\n"
                  f"animate goto {frame_idx}\nrender TachyonInternal "
                  f"{output_path}\nquit\n")
        script_path = ws / "stage3_viz" / "render.vmd"
        script_path.write_text(script)
        import subprocess
        subprocess.run(["vmd", "-dispdev", "text", "-e", str(script_path)],
                       check=False, capture_output=True)
        return output_path if output_path.exists() else None
    return None


_PYMOL_ANIM_SCRIPT = """
load {gro}, system
load_traj {xtc}, system
hide everything
show cartoon, polymer
bg_color white
mset 1 x{nframes}
viewport 800,600
movie.produce {out_prefix}, encoder=ffmpeg, mode=ray, quality=80
quit
"""


def animate_trajectory(workspace_dir: Path, output_path: Path,
                       fps: int = 30, stride: int = 10) -> Path | None:
    renderer = select_renderer()
    if renderer == "none":
        return None
    if not shutil.which("ffmpeg"):
        return None
    ws = Path(workspace_dir)
    s = state.read(ws) if state.path(ws).exists() else {}
    prefix = _trajectory_prefix(s) if s else "production"
    gro = ws / "stage2_md" / f"{prefix}.gro"
    xtc = ws / "stage2_md" / f"{prefix}.xtc"
    if renderer == "pymol":
        script_path = ws / "stage3_viz" / "anim.pml"
        script_path.write_text(_PYMOL_ANIM_SCRIPT.format(
            gro=gro, xtc=xtc, nframes=100,
            out_prefix=str(output_path.with_suffix("")),
        ))
        import subprocess
        subprocess.run(["pymol", "-cq", str(script_path)],
                       check=False, capture_output=True)
        return output_path if output_path.exists() else None
    # VMD path omitted for brevity; same pattern with `make movie` plugin.
    return None


import sys as _sys


def plot_xvg(xvg_path: Path, output_path: Path, title: str = "") -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import sys as _sys_path
    _sys_path.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    try:
        from _pubstyle import apply_style
        apply_style()
    except ImportError:
        matplotlib.rcParams.update({"figure.dpi": 300, "savefig.dpi": 300})
    import matplotlib.pyplot as plt
    data = xvg_parser.parse(xvg_path, max_points=2000)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    cols = data["columns"]
    legends = data.get("column_labels") or []
    if len(cols) >= 2:
        x = cols[0]
        series = cols[1:]
        for i, y in enumerate(series):
            label = legends[i] if i < len(legends) and legends[i] else (f"series {i + 1}" if len(series) > 1 else None)
            ax.plot(x, y, linewidth=1.0, label=label)
        if len(series) > 1:
            ax.legend(loc="best", frameon=False)
    ax.set_xlabel(data["xaxis_label"] or "x")
    ax.set_ylabel(data["yaxis_label"] or "y")
    ax.set_title(title or data["title"] or xvg_path.stem)
    ax.grid(True, linewidth=0.4, alpha=0.4)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_all(workspace_dir: Path) -> list[Path]:
    viz = _viz_dir(workspace_dir)
    pngs = []
    for xvg in sorted(viz.glob("*.xvg")):
        png = viz / (xvg.stem + ".png")
        try:
            plot_xvg(xvg, png, title=xvg.stem)
            pngs.append(png)
        except Exception:
            continue
    return pngs

def illustrate(workspace_dir: Path,
               analyses: list[str] | None = None,
               render_frames: list = None,
               animation: dict | None = None,
               report_html: bool = True,
               interactive: bool = True) -> dict[str, Any]:
    assert_ready(workspace_dir)
    run_core_analyses(workspace_dir)
    run_advanced_analyses(workspace_dir)
    run_variant_analyses(workspace_dir)
    plot_all(workspace_dir)
    viz = _viz_dir(workspace_dir)
    rendered: list[str] = []
    for f in (render_frames or [0, "middle", "last"]):
        out = viz / f"frame_{f}.png"
        r = render_frame(workspace_dir, f, out)
        if r:
            rendered.append(str(r))
    anim_cfg = animation or {"enabled": True, "fps": 30, "stride": 10}
    anim_path = None
    if anim_cfg.get("enabled", True):
        anim_path = animate_trajectory(
            workspace_dir, viz / "trajectory.mp4",
            fps=anim_cfg.get("fps", 30),
            stride=anim_cfg.get("stride", 10),
        )
    report = compose_report(workspace_dir)
    html = compose_html_report(workspace_dir) if report_html else None
    s = state.read(workspace_dir)
    s["last_completed_stage"] = "viz"
    state.write(workspace_dir, s)
    return {
        "report_path": str(report),
        "report_html_path": str(html) if html else None,
        "rendered_frames": rendered,
        "animation_path": str(anim_path) if anim_path else None,
    }


VARIANT_DISPATCH = {
    "umbrella_sampling": "_run_wham",
    "free_energy_alchemical": "_run_bar",
    "membrane_md_standard": "_run_membrane_analysis",
    "protein_ligand_complex": "_run_protein_ligand_analysis",
}


def run_variant_analyses(workspace_dir: Path) -> dict[str, Any]:
    s = state.read(workspace_dir)
    variant = (s.get("tutorial") or {}).get("variant", "")
    fn_name = VARIANT_DISPATCH.get(variant)
    if not fn_name:
        return {}
    # Look up via module so patches applied at module level take effect.
    module = _sys.modules[__name__]
    fn = getattr(module, fn_name)
    result = fn(workspace_dir)
    s = state.read(workspace_dir)
    s["step_outputs"].setdefault("step_8", {})["variant_summary"] = result
    state.write(workspace_dir, s)
    return result
