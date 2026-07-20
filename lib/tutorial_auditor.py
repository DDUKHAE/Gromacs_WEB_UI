from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lib import protocol_contract as PC
from lib import tutorial_registry as TR


# Expected configuration per tutorial_id
_TUTORIAL_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "Lysozyme_in_water": {
        "forcefield": "charmm36",
        "water_model": "tip3p",
        "box_type": "dodecahedron",
        "phase_sequence": ["em", "nvt", "npt", "production"],
    },
    "KALP15_in_DPPC": {
        "forcefield": "charmm36",
        "water_model": "tip3p",
        "box_type": "triclinic",
        "phase_sequence": ["em", "nvt", "npt", "npt", "production"],
    },
    "Protein_Ligand_Complex": {
        "forcefield": "charmm36",
        "water_model": "tip3p",
        "box_type": "dodecahedron",
        "phase_sequence": ["em", "nvt", "npt", "production"],
    },
    "Umbrella_Sampling": {
        "forcefield": "charmm36",
        "water_model": "tip3p",
        "box_type": "dodecahedron",
        "phase_sequence": ["em", "nvt", "npt", "umbrella"],
    },
    "Free_Energy_Calculations_Methane_in_Water": {
        "forcefield": "oplsaa",
        "water_model": "tip4p",
        "box_type": "dodecahedron",
        "phase_sequence": ["em", "nvt", "npt", "free_energy"],
    },
}


@dataclass
class AuditItem:
    key: str
    expected: str
    actual: str
    status: str  # "pass" | "fail" | "warn" | "n/a"
    note: str = ""


@dataclass
class AuditReport:
    tutorial_id: str | None
    items: list[AuditItem] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for i in self.items if i.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for i in self.items if i.status == "fail")

    def to_dict(self) -> dict:
        return {
            "tutorial_id": self.tutorial_id,
            "passed": self.passed,
            "failed": self.failed,
            "items": [
                {
                    "key": i.key,
                    "expected": i.expected,
                    "actual": i.actual,
                    "status": i.status,
                    "note": i.note,
                }
                for i in self.items
            ],
        }


def _load_state(workspace: Path) -> dict[str, Any]:
    p = workspace / "state.json"
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def _load_tutorial_id(workspace: Path, state: dict) -> str | None:
    tid = (state.get("tutorial") or {}).get("id")
    if tid:
        return tid
    meta_p = workspace / "meta.json"
    if meta_p.exists():
        try:
            m = json.loads(meta_p.read_text())
            return m.get("tutorial_id") or None
        except Exception:
            pass
    return None


def audit_run(workspace: Path) -> AuditReport:
    workspace = Path(workspace)
    state = _load_state(workspace)
    tutorial_id = _load_tutorial_id(workspace, state)

    if not tutorial_id:
        na_keys = ["forcefield", "water_model", "box_type", "phase_sequence"]
        return AuditReport(
            tutorial_id=tutorial_id,
            items=[
                AuditItem(key=k, expected="n/a", actual="n/a", status="n/a",
                          note="No tutorial selected or tutorial not in audit registry")
                for k in na_keys
            ],
        )

    # The materialized contract is the authoritative protocol for a run.  For
    # old workspaces without one, derive expectations from the checked-in
    # manifest rather than the stale hand-maintained duplicate table above.
    contract_error = ""
    try:
        contract = PC.assert_valid(workspace)
    except PC.ProtocolContractError as exc:
        contract = None
        contract_error = str(exc)
    manifest = TR.load_manifest(tutorial_id) or {}
    locked = (contract or {}).get("locked_parameters", manifest.get("defaults", {}))
    expected = {
        "forcefield": locked.get("forcefield"),
        "water_model": locked.get("water_model"),
        "box_type": locked.get("box_type"),
        "phase_sequence": (contract or {}).get(
            "phase_sequence",
            PC.PHASE_SEQUENCE_BY_VARIANT.get(manifest.get("pipeline_variant"), []),
        ),
    }
    step_out = state.get("step_outputs", {})
    step1 = step_out.get("step_1", {})
    step2 = step_out.get("step_2", {})
    step7 = step_out.get("step_7", {})

    items: list[AuditItem] = []
    if contract_error:
        items.append(AuditItem("protocol_contract", "valid checksum", "invalid",
                               "fail", contract_error))
    elif contract:
        items.append(AuditItem("protocol_contract", "valid checksum", "valid",
                               "pass", f"sha256={contract['contract_sha256']}"))

    # Forcefield
    actual_ff = str(step1.get("forcefield", "")).lower()
    exp_ff = str(expected["forcefield"] or "").lower()
    items.append(AuditItem(
        key="forcefield",
        expected=exp_ff,
        actual=actual_ff or "(not recorded)",
        status="pass" if actual_ff == exp_ff else ("n/a" if not actual_ff else "fail"),
    ))

    # Water model
    actual_wm = str(step1.get("water_model", "")).lower()
    exp_wm = str(expected["water_model"] or "").lower()
    items.append(AuditItem(
        key="water_model",
        expected=exp_wm,
        actual=actual_wm or "(not recorded)",
        status="pass" if actual_wm == exp_wm else ("n/a" if not actual_wm else "fail"),
    ))

    # Box type
    actual_box = str(step2.get("box_type", "")).lower()
    exp_box = str(expected["box_type"] or "").lower()
    items.append(AuditItem(
        key="box_type",
        expected=exp_box,
        actual=actual_box or "(not recorded)",
        status="pass" if actual_box == exp_box else ("n/a" if not actual_box else "fail"),
    ))

    # Phase sequence
    actual_seq = step7.get("phase_sequence") or []
    exp_seq = expected["phase_sequence"]
    seq_match = actual_seq == exp_seq
    items.append(AuditItem(
        key="phase_sequence",
        expected=" → ".join(exp_seq),
        actual=" → ".join(actual_seq) if actual_seq else "(not recorded)",
        status="pass" if seq_match else ("n/a" if not actual_seq else "fail"),
        note="" if seq_match else f"Skipped or added phases vs expected {exp_seq}",
    ))

    return AuditReport(tutorial_id=tutorial_id, items=items)
