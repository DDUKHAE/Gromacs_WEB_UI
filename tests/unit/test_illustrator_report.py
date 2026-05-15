from pathlib import Path
from lib import state


def _seed(ws: Path):
    s = state.initial(ws)
    s["last_completed_stage"] = "md"
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    s["step_outputs"]["step_7"] = {"production_gro": "stage2_md/production.gro"}
    s["step_outputs"]["step_8"] = {
        "analysis_summaries": {
            "rmsd": {"mean": 0.21, "std": 0.03, "count": 100},
            "rmsf": {"mean": 0.15, "std": 0.05, "count": 50},
        }
    }
    state.write(ws, s)


def test_compose_report_writes_markdown(tmp_path: Path):
    from skills.illustrator.illustrator import compose_report
    ws = tmp_path
    (ws / "stage3_viz").mkdir(parents=True)
    (ws / "stage3_viz" / "rmsd.png").write_bytes(b"\x89PNG")
    (ws / "stage3_viz" / "rmsf.png").write_bytes(b"\x89PNG")
    _seed(ws)
    report = compose_report(ws)
    assert report.exists()
    content = report.read_text()
    assert "RMSD" in content
    assert "![" in content   # image markdown
