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


def _rmsd(ws: Path, prefix: str) -> Path:
    out = _viz_dir(ws) / "rmsd.xvg"
    GW.run(
        ["rms", "-s", f"{prefix}.tpr", "-f", f"{prefix}.xtc",
         "-o", str(out), "-tu", "ns"],
        cwd=_md_dir(ws), interactive_inputs=["Backbone", "Backbone"],
    )
    return out


def _rmsf(ws: Path, prefix: str) -> Path:
    out = _viz_dir(ws) / "rmsf.xvg"
    GW.run(
        ["rmsf", "-s", f"{prefix}.tpr", "-f", f"{prefix}.xtc",
         "-o", str(out), "-res"],
        cwd=_md_dir(ws), interactive_inputs=["Protein"],
    )
    return out


def _gyrate(ws: Path, prefix: str) -> Path:
    out = _viz_dir(ws) / "gyrate.xvg"
    GW.run(
        ["gyrate", "-s", f"{prefix}.tpr", "-f", f"{prefix}.xtc",
         "-o", str(out)],
        cwd=_md_dir(ws), interactive_inputs=["Protein"],
    )
    return out


def _sasa(ws: Path, prefix: str) -> Path:
    out = _viz_dir(ws) / "sasa.xvg"
    GW.run(
        ["sasa", "-s", f"{prefix}.tpr", "-f", f"{prefix}.xtc",
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
    out: dict[str, dict] = {}
    out["rmsd"] = xvg_parser.summary(_rmsd(workspace_dir, prefix))
    out["rmsf"] = xvg_parser.summary(_rmsf(workspace_dir, prefix))
    out["gyrate"] = xvg_parser.summary(_gyrate(workspace_dir, prefix))
    try:
        out["sasa"] = xvg_parser.summary(_sasa(workspace_dir, prefix))
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
