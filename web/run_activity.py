"""Truthful, presentation-ready events for real and virtual-like run views."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_STAGES = {
    1: "Topology",
    2: "Box definition",
    3: "Solvation",
    4: "Ion preparation",
    5: "Ionization",
    6: "Equilibration",
    7: "Production MD",
    8: "Analysis",
}


def _production_finished(workspace: Path) -> bool:
    log = workspace / "stage2_md" / "production.log"
    try:
        with log.open("rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 65536))
            return b"Finished mdrun on rank" in handle.read()
    except OSError:
        return False


def build_activity(workspace: Path, status: str) -> list[dict[str, Any]]:
    """Return only facts persisted by the pipeline; never infer MD success."""
    try:
        state = json.loads((workspace / "state.json").read_text())
    except (OSError, json.JSONDecodeError):
        state = {}
    outputs = state.get("step_outputs", {})
    events: list[dict[str, Any]] = []

    def add(step: int, text: str, event_status: str = "completed") -> None:
        events.append({"step": step, "stage": _STAGES[step], "status": event_status, "text": text})

    s1 = outputs.get("step_1", {})
    if s1:
        add(1, f"Topology prepared with {s1.get('forcefield', 'the selected force field')} and "
               f"{s1.get('water_model', 'the selected water model')}.")
    s2 = outputs.get("step_2", {})
    if s2:
        add(2, f"{s2.get('box_type', 'Simulation')} box defined with "
               f"{s2.get('box_distance', 'configured')} nm clearance.")
    s3 = outputs.get("step_3", {})
    if s3:
        add(3, f"Solvation complete: {s3.get('n_solvent_molecules', 'configured')} solvent molecules added.")
    if outputs.get("step_4"):
        add(4, "Ion-preparation input generated.")
    s5 = outputs.get("step_5", {})
    if s5:
        add(5, f"Ionization complete: Na+ {s5.get('n_na', 0)}, Cl− {s5.get('n_cl', 0)}, "
               f"net charge {s5.get('net_charge', 'unknown')}.")
    s7 = outputs.get("step_7", {})
    if s7.get("em_gro"):
        add(6, "Energy minimization and NVT/NPT equilibration output generated.")
    if s7.get("production_gro"):
        if _production_finished(workspace):
            add(7, "Production MD finished. Results await analysis.")
        else:
            add(7, "Production MD output has been created.", "running")
    if state.get("last_completed_stage") == "viz":
        add(8, "Analysis and final report completed.")
    elif status == "analysis_pending":
        add(8, "Analysis has not been run yet.", "pending")
    elif not events:
        add(1, "Run is waiting for environment preparation.", "pending")
    return events
