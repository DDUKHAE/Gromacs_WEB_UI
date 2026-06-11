from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path

from lib.system_config import load_config


def _status(matched: bool, actual: str) -> str:
    """Determine audit status: "n/a" if not recorded, "pass"/"fail" based on match."""
    if not actual:
        return "n/a"
    return "pass" if matched else "fail"


@dataclass
class ConfigAuditItem:
    key: str
    expected: str
    actual: str
    status: str  # "pass" | "fail" | "n/a"


@dataclass
class ConfigAuditReport:
    has_config: bool
    items: list[ConfigAuditItem] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for i in self.items if i.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for i in self.items if i.status == "fail")

    def to_dict(self) -> dict:
        return {
            "has_config": self.has_config,
            "passed": self.passed,
            "failed": self.failed,
            "items": [
                {"key": i.key, "expected": i.expected, "actual": i.actual, "status": i.status}
                for i in self.items
            ],
        }


def validate_run_against_config(workspace: Path) -> ConfigAuditReport:
    """Compare system_config.json with state.json step outputs."""
    workspace = Path(workspace)
    config = load_config(workspace)
    if config is None:
        return ConfigAuditReport(has_config=False)

    state_path = workspace / "state.json"
    if not state_path.exists():
        return ConfigAuditReport(has_config=True)

    state = json.loads(state_path.read_text())
    step_out = state.get("step_outputs", {})
    step1 = step_out.get("step_1", {})
    step2 = step_out.get("step_2", {})

    items: list[ConfigAuditItem] = []
    ff = config.get("forcefield", {})
    box = config.get("box", {})

    if ff.get("name"):
        # "charmm36-jul2022" → match against "charmm36" prefix in actual
        expected_prefix = ff["name"].lower().split("-")[0]
        actual_ff = str(step1.get("forcefield", "")).lower()
        matched = actual_ff.startswith(expected_prefix)
        items.append(ConfigAuditItem(
            key="forcefield",
            expected=ff["name"],
            actual=actual_ff or "(not recorded)",
            status=_status(matched, actual_ff),
        ))

    if ff.get("water_model"):
        expected_wm = ff["water_model"].lower()
        actual_wm = str(step1.get("water_model", "")).lower()
        matched = actual_wm == expected_wm
        items.append(ConfigAuditItem(
            key="water_model",
            expected=expected_wm,
            actual=actual_wm or "(not recorded)",
            status=_status(matched, actual_wm),
        ))

    if box.get("type"):
        expected_box = box["type"].lower()
        actual_box = str(step2.get("box_type", "")).lower()
        matched = actual_box == expected_box
        items.append(ConfigAuditItem(
            key="box_type",
            expected=expected_box,
            actual=actual_box or "(not recorded)",
            status=_status(matched, actual_box),
        ))

    return ConfigAuditReport(has_config=True, items=items)
