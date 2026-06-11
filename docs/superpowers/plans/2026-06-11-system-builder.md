# System Builder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 6-step System Builder wizard to Gromacs Web UI so users can configure MD system parameters before running, save them as reusable presets, and have the LLM follow those parameters exactly.

**Architecture:** A new `lib/system_config.py` module validates config dicts and builds LLM constraint prompts. `POST /api/runs` accepts an optional `system_config` JSON field that gets saved to `runs/{id}/system_config.json`. `llm_runner.py` detects that file and appends a constraint block to the LLM prompt. The frontend replaces the create-run modal with a 6-step wizard that collects the config and sends it along with the existing form data.

**Tech Stack:** Python 3.11, FastAPI, pytest, vanilla JS (no new dependencies)

**Spec:** `docs/superpowers/specs/2026-06-11-system-builder-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `lib/system_config.py` | Config validation + LLM constraint prompt builder + `load_config()` |
| Create | `lib/system_config_validator.py` | Post-run: compare `system_config.json` vs `state.json` step outputs |
| Create | `tests/test_system_config.py` | Unit tests for `lib/system_config.py` |
| Create | `tests/test_system_config_validator.py` | Unit tests for `lib/system_config_validator.py` |
| Create | `tests/test_presets_api.py` | API tests for preset endpoints |
| Modify | `web/server.py` | Add preset API (`/api/presets`), extend `POST /api/runs`, extend audit endpoint |
| Modify | `web/llm_runner.py` | Inject constraint block when `system_config.json` exists |
| Modify | `web/static/index.html` | Replace create-run form with 6-step wizard |

---

## Task 1: `lib/system_config.py` — Core Config Module

**Files:**
- Create: `lib/system_config.py`
- Create: `tests/test_system_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_system_config.py`:

```python
import pytest
from lib.system_config import validate_solution_config, build_constraint_prompt, load_config
from pathlib import Path
import json


# ── validate_solution_config ──────────────────────────────────────────────────

def test_empty_config_is_valid():
    assert validate_solution_config({}) == []


def test_valid_full_config_is_valid():
    config = {
        "forcefield": {"name": "charmm36-jul2022", "water_model": "tip3p"},
        "box": {"type": "dodecahedron", "edge_distance_nm": 1.0},
        "ions": {"salt_type": "NaCl", "concentration_M": 0.15, "neutralize": True},
        "simulation": {
            "_expert_mode": True,
            "temperature_K": 300,
            "pressure_bar": 1.0,
            "sim_time_ns": 1.0,
            "thermostat": "V-rescale",
            "barostat": "Parrinello-Rahman",
        },
    }
    assert validate_solution_config(config) == []


def test_invalid_box_type_returns_error():
    errors = validate_solution_config({"box": {"type": "hexagonal"}})
    assert len(errors) == 1
    assert "box type" in errors[0].lower()


def test_edge_distance_too_small_returns_error():
    errors = validate_solution_config({"box": {"edge_distance_nm": 0.1}})
    assert any("edge_distance_nm" in e for e in errors)


def test_edge_distance_too_large_returns_error():
    errors = validate_solution_config({"box": {"edge_distance_nm": 9.9}})
    assert any("edge_distance_nm" in e for e in errors)


def test_concentration_out_of_range_returns_error():
    errors = validate_solution_config({"ions": {"concentration_M": 5.0}})
    assert any("concentration_M" in e for e in errors)


def test_temperature_too_low_returns_error():
    errors = validate_solution_config({"simulation": {"temperature_K": 50}})
    assert any("temperature_K" in e for e in errors)


def test_temperature_too_high_returns_error():
    errors = validate_solution_config({"simulation": {"temperature_K": 600}})
    assert any("temperature_K" in e for e in errors)


def test_invalid_thermostat_returns_error():
    errors = validate_solution_config({"simulation": {"thermostat": "Langevin"}})
    assert any("thermostat" in e.lower() for e in errors)


def test_invalid_barostat_returns_error():
    errors = validate_solution_config({"simulation": {"barostat": "MonteCarloMembrane"}})
    assert any("barostat" in e.lower() for e in errors)


# ── build_constraint_prompt ──────────────────────────────────────────────────

def test_constraint_prompt_has_header():
    prompt = build_constraint_prompt({})
    assert "SYSTEM BUILDER CONSTRAINTS" in prompt


def test_constraint_prompt_includes_forcefield_name():
    config = {"forcefield": {"name": "charmm36-jul2022"}}
    assert "charmm36-jul2022" in build_constraint_prompt(config)


def test_constraint_prompt_includes_box_info():
    config = {"box": {"type": "dodecahedron", "edge_distance_nm": 1.2}}
    prompt = build_constraint_prompt(config)
    assert "dodecahedron" in prompt
    assert "1.2" in prompt


def test_constraint_prompt_includes_ions():
    config = {"ions": {"salt_type": "KCl", "concentration_M": 0.1, "neutralize": True}}
    prompt = build_constraint_prompt(config)
    assert "KCl" in prompt
    assert "0.1" in prompt


def test_constraint_prompt_excludes_sim_params_when_not_expert():
    config = {"simulation": {"_expert_mode": False, "temperature_K": 400}}
    prompt = build_constraint_prompt(config)
    assert "400" not in prompt


def test_constraint_prompt_includes_sim_params_when_expert():
    config = {"simulation": {"_expert_mode": True, "temperature_K": 350, "sim_time_ns": 2.0}}
    prompt = build_constraint_prompt(config)
    assert "350" in prompt
    assert "2.0" in prompt


# ── load_config ──────────────────────────────────────────────────────────────

def test_load_config_returns_none_when_absent(tmp_path):
    assert load_config(tmp_path) is None


def test_load_config_returns_dict_when_present(tmp_path):
    data = {"version": "1.0", "builder_type": "solution"}
    (tmp_path / "system_config.json").write_text(json.dumps(data))
    result = load_config(tmp_path)
    assert result == data
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_system_config.py -v
```

Expected: `ImportError: cannot import name 'validate_solution_config' from 'lib.system_config'`

- [ ] **Step 3: Implement `lib/system_config.py`**

Create `lib/system_config.py`:

```python
from __future__ import annotations
import json
from pathlib import Path

VALID_BOX_TYPES = {"cubic", "dodecahedron", "octahedron"}
VALID_THERMOSTATS = {"V-rescale", "Nosé-Hoover"}
VALID_BAROSTATS = {"Parrinello-Rahman", "Berendsen"}


def validate_solution_config(config: dict) -> list[str]:
    """Validate a solution builder config dict. Returns list of error strings."""
    errors: list[str] = []

    box = config.get("box", {})
    if box.get("type") and box["type"] not in VALID_BOX_TYPES:
        errors.append(
            f"Invalid box type '{box['type']}'. Must be one of: {', '.join(sorted(VALID_BOX_TYPES))}"
        )
    if "edge_distance_nm" in box and not (0.5 <= box["edge_distance_nm"] <= 5.0):
        errors.append("edge_distance_nm must be between 0.5 and 5.0")

    ions = config.get("ions", {})
    if "concentration_M" in ions and not (0.0 <= ions["concentration_M"] <= 2.0):
        errors.append("concentration_M must be between 0.0 and 2.0")

    sim = config.get("simulation", {})
    if sim.get("thermostat") and sim["thermostat"] not in VALID_THERMOSTATS:
        errors.append(
            f"Invalid thermostat '{sim['thermostat']}'. Must be one of: {', '.join(sorted(VALID_THERMOSTATS))}"
        )
    if sim.get("barostat") and sim["barostat"] not in VALID_BAROSTATS:
        errors.append(
            f"Invalid barostat '{sim['barostat']}'. Must be one of: {', '.join(sorted(VALID_BAROSTATS))}"
        )
    if "temperature_K" in sim and not (200 <= sim["temperature_K"] <= 500):
        errors.append("temperature_K must be between 200 and 500")
    if "pressure_bar" in sim and not (0.1 <= sim["pressure_bar"] <= 10.0):
        errors.append("pressure_bar must be between 0.1 and 10.0")
    if "sim_time_ns" in sim and not (0.001 <= sim["sim_time_ns"] <= 1000):
        errors.append("sim_time_ns must be between 0.001 and 1000")

    return errors


def build_constraint_prompt(config: dict) -> str:
    """Build LLM constraint block string from a system_config dict."""
    ff = config.get("forcefield", {})
    box = config.get("box", {})
    ions = config.get("ions", {})
    sim = config.get("simulation", {})

    lines = [
        "",
        "[SYSTEM BUILDER CONSTRAINTS — MUST FOLLOW EXACTLY]",
        "The user has pre-configured this system via the System Builder.",
        "You MUST use these parameters without modification:",
        "",
    ]
    if ff.get("name"):
        lines.append(f"- Force field: {ff['name']}")
    if ff.get("water_model"):
        lines.append(f"- Water model: {ff['water_model']}")
    if box.get("type"):
        lines.append(
            f"- Box type: {box['type']}, edge distance: {box.get('edge_distance_nm', 1.0)} nm"
        )
    if ions.get("salt_type"):
        lines.append(
            f"- Ions: {ions['salt_type']} at {ions.get('concentration_M', 0.15)} M, "
            f"neutralize={str(ions.get('neutralize', True)).lower()}"
        )
    if sim.get("_expert_mode"):
        lines.append(f"- Temperature: {sim.get('temperature_K', 300)} K")
        lines.append(f"- Pressure: {sim.get('pressure_bar', 1.0)} bar")
        lines.append(f"- Simulation time: {sim.get('sim_time_ns', 1.0)} ns")
        if sim.get("thermostat"):
            lines.append(f"- Thermostat: {sim['thermostat']}")
        if sim.get("barostat"):
            lines.append(f"- Barostat: {sim['barostat']}")
    lines += [
        "",
        "Do NOT override these settings based on tutorial defaults.",
        "These represent the user's explicit choices.",
        "",
    ]
    return "\n".join(lines)


def load_config(workspace: Path) -> dict | None:
    """Load system_config.json from workspace. Returns None if absent."""
    path = Path(workspace) / "system_config.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_system_config.py -v
```

Expected: All 18 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/system_config.py tests/test_system_config.py
git commit -m "feat: add system_config module with validation and constraint prompt builder"
```

---

## Task 2: `lib/system_config_validator.py` — Post-run Validator

**Files:**
- Create: `lib/system_config_validator.py`
- Create: `tests/test_system_config_validator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_system_config_validator.py`:

```python
import json
import pytest
from pathlib import Path
from lib.system_config_validator import validate_run_against_config, ConfigAuditReport


@pytest.fixture
def workspace_with_config(tmp_path):
    config = {
        "version": "1.0",
        "builder_type": "solution",
        "forcefield": {"name": "charmm36-jul2022", "water_model": "tip3p"},
        "box": {"type": "dodecahedron", "edge_distance_nm": 1.0},
    }
    (tmp_path / "system_config.json").write_text(json.dumps(config))
    return tmp_path


@pytest.fixture
def workspace_with_state(workspace_with_config):
    state = {
        "schema_version": "1.0",
        "workspace_dir": str(workspace_with_config),
        "step_outputs": {
            "step_1": {"forcefield": "charmm36", "water_model": "tip3p"},
            "step_2": {"box_type": "dodecahedron"},
        },
    }
    (workspace_with_config / "state.json").write_text(json.dumps(state))
    return workspace_with_config


def test_returns_report_object(workspace_with_state):
    report = validate_run_against_config(workspace_with_state)
    assert isinstance(report, ConfigAuditReport)


def test_has_config_true_when_file_present(workspace_with_state):
    report = validate_run_against_config(workspace_with_state)
    assert report.has_config is True


def test_has_config_false_when_no_file(tmp_path):
    report = validate_run_against_config(tmp_path)
    assert report.has_config is False
    assert report.items == []


def test_pass_when_forcefield_matches(workspace_with_state):
    report = validate_run_against_config(workspace_with_state)
    ff_item = next(i for i in report.items if i.key == "forcefield")
    assert ff_item.status == "pass"


def test_fail_when_forcefield_mismatch(workspace_with_config):
    state = {
        "step_outputs": {
            "step_1": {"forcefield": "amber99sb", "water_model": "tip3p"},
            "step_2": {"box_type": "dodecahedron"},
        }
    }
    (workspace_with_config / "state.json").write_text(json.dumps(state))
    report = validate_run_against_config(workspace_with_config)
    ff_item = next(i for i in report.items if i.key == "forcefield")
    assert ff_item.status == "fail"


def test_pass_when_box_type_matches(workspace_with_state):
    report = validate_run_against_config(workspace_with_state)
    box_item = next(i for i in report.items if i.key == "box_type")
    assert box_item.status == "pass"


def test_na_when_state_not_yet_recorded(workspace_with_config):
    # state.json exists but step_outputs are empty (run not yet complete)
    state = {"step_outputs": {}}
    (workspace_with_config / "state.json").write_text(json.dumps(state))
    report = validate_run_against_config(workspace_with_config)
    assert all(i.status == "n/a" for i in report.items)


def test_to_dict_has_expected_keys(workspace_with_state):
    d = validate_run_against_config(workspace_with_state).to_dict()
    assert "has_config" in d
    assert "passed" in d
    assert "failed" in d
    assert "items" in d
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_system_config_validator.py -v
```

Expected: `ImportError: cannot import name 'validate_run_against_config'`

- [ ] **Step 3: Implement `lib/system_config_validator.py`**

Create `lib/system_config_validator.py`:

```python
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path

from lib.system_config import load_config


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
        items.append(ConfigAuditItem(
            key="forcefield",
            expected=ff["name"],
            actual=actual_ff or "(not recorded)",
            status=(
                "pass" if (actual_ff and expected_prefix in actual_ff)
                else ("n/a" if not actual_ff else "fail")
            ),
        ))

    if ff.get("water_model"):
        expected_wm = ff["water_model"].lower()
        actual_wm = str(step1.get("water_model", "")).lower()
        items.append(ConfigAuditItem(
            key="water_model",
            expected=expected_wm,
            actual=actual_wm or "(not recorded)",
            status="pass" if actual_wm == expected_wm else ("n/a" if not actual_wm else "fail"),
        ))

    if box.get("type"):
        expected_box = box["type"].lower()
        actual_box = str(step2.get("box_type", "")).lower()
        items.append(ConfigAuditItem(
            key="box_type",
            expected=expected_box,
            actual=actual_box or "(not recorded)",
            status="pass" if actual_box == expected_box else ("n/a" if not actual_box else "fail"),
        ))

    return ConfigAuditReport(has_config=True, items=items)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_system_config_validator.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/system_config_validator.py tests/test_system_config_validator.py
git commit -m "feat: add system_config_validator to audit LLM compliance with builder settings"
```

---

## Task 3: Preset API Endpoints

**Files:**
- Modify: `web/server.py` (add 3 preset endpoints)
- Create: `tests/test_presets_api.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_presets_api.py`:

```python
import json
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_harness(tmp_path):
    (tmp_path / "runs").mkdir()
    return tmp_path


@pytest.fixture
def client(tmp_harness):
    from web.server import create_app
    app = create_app(harness_dir=tmp_harness)
    return TestClient(app)


_SAMPLE_CONFIG = {
    "version": "1.0",
    "builder_type": "solution",
    "forcefield": {"name": "charmm36-jul2022", "water_model": "tip3p"},
    "box": {"type": "dodecahedron", "edge_distance_nm": 1.0},
}


def test_list_presets_empty(client):
    resp = client.get("/api/presets")
    assert resp.status_code == 200
    assert resp.json() == []


def test_save_preset_returns_201(client):
    resp = client.post("/api/presets", json={"name": "Test Preset", "config": _SAMPLE_CONFIG})
    assert resp.status_code == 201


def test_saved_preset_appears_in_list(client):
    client.post("/api/presets", json={"name": "MyPreset", "config": _SAMPLE_CONFIG})
    resp = client.get("/api/presets")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "MyPreset" in names


def test_saved_preset_config_is_stored(client):
    client.post("/api/presets", json={"name": "ConfigTest", "config": _SAMPLE_CONFIG})
    resp = client.get("/api/presets")
    preset = next(p for p in resp.json() if p["name"] == "ConfigTest")
    assert preset["config"]["builder_type"] == "solution"


def test_delete_preset_returns_200(client):
    client.post("/api/presets", json={"name": "ToDelete", "config": _SAMPLE_CONFIG})
    resp = client.delete("/api/presets/ToDelete")
    assert resp.status_code == 200


def test_deleted_preset_absent_from_list(client):
    client.post("/api/presets", json={"name": "Gone", "config": _SAMPLE_CONFIG})
    client.delete("/api/presets/Gone")
    resp = client.get("/api/presets")
    names = [p["name"] for p in resp.json()]
    assert "Gone" not in names


def test_delete_nonexistent_preset_returns_404(client):
    resp = client.delete("/api/presets/doesnotexist")
    assert resp.status_code == 404


def test_save_preset_without_name_returns_400(client):
    resp = client.post("/api/presets", json={"name": "", "config": _SAMPLE_CONFIG})
    assert resp.status_code == 400


def test_save_preset_without_config_returns_400(client):
    resp = client.post("/api/presets", json={"name": "NoConfig"})
    assert resp.status_code == 400


def test_preset_name_sanitized(client):
    client.post("/api/presets", json={"name": "My Preset!!!", "config": _SAMPLE_CONFIG})
    resp = client.get("/api/presets")
    # Special chars replaced with underscores
    names = [p["name"] for p in resp.json()]
    assert any("My_Preset" in n for n in names)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_presets_api.py -v
```

Expected: `FAILED — 404 Not Found` for all preset routes.

- [ ] **Step 3: Add preset endpoints to `web/server.py`**

In `web/server.py`, add `_PRESETS_DIR = "presets"` constant after `_MAX_PDB_BYTES` (line ~49), then add 3 endpoints inside `create_app()` before the `POST /api/runs` handler:

```python
_PRESETS_DIR = "presets"
```

Then inside `create_app()`, add after the existing `@app.get("/api/forcefields/{ff_name}/watermodels")` block:

```python
    @app.get("/api/presets")
    def api_list_presets(hd: HarnessDir) -> list[dict]:
        presets_dir = hd / _PRESETS_DIR
        if not presets_dir.exists():
            return []
        result = []
        for p in sorted(presets_dir.glob("*.json")):
            try:
                result.append({"name": p.stem, "config": json.loads(p.read_text())})
            except Exception:
                pass
        return result

    @app.post("/api/presets", status_code=201)
    def api_save_preset(body: dict, hd: HarnessDir) -> dict:
        name = (body.get("name") or "").strip()
        config = body.get("config")
        if not name or not config:
            raise HTTPException(status_code=400, detail="name and config are required")
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)[:64]
        if not safe_name:
            raise HTTPException(status_code=400, detail="invalid preset name")
        presets_dir = hd / _PRESETS_DIR
        presets_dir.mkdir(exist_ok=True)
        (presets_dir / f"{safe_name}.json").write_text(json.dumps(config, indent=2))
        return {"name": safe_name}

    @app.delete("/api/presets/{preset_name}", status_code=200)
    def api_delete_preset(preset_name: str, hd: HarnessDir) -> dict:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", preset_name)[:64]
        preset_path = hd / _PRESETS_DIR / f"{safe_name}.json"
        if not preset_path.exists():
            raise HTTPException(status_code=404, detail="preset not found")
        preset_path.unlink()
        return {"deleted": safe_name}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_presets_api.py -v
```

Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/server.py tests/test_presets_api.py
git commit -m "feat: add /api/presets CRUD endpoints for system builder preset storage"
```

---

## Task 4: Extend `POST /api/runs` to Accept `system_config`

**Files:**
- Modify: `web/server.py` (`api_create_run` function)
- Modify: `tests/test_presets_api.py` (add 2 tests for create_run with system_config)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_presets_api.py`:

```python
# ── POST /api/runs with system_config ────────────────────────────────────────

def test_create_run_with_system_config_saves_file(tmp_harness, client):
    pdb_content = b"ATOM      1  CA  ALA A   1       1.000   1.000   1.000\nEND\n"
    config_json = json.dumps(_SAMPLE_CONFIG)
    resp = client.post(
        "/api/runs",
        data={"system_config": config_json},
        files={"pdb_file": ("test.pdb", pdb_content, "chemical/x-pdb")},
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    config_path = tmp_harness / "runs" / run_id / "system_config.json"
    assert config_path.exists()
    saved = json.loads(config_path.read_text())
    assert saved["builder_type"] == "solution"


def test_create_run_with_invalid_system_config_returns_400(client):
    pdb_content = b"ATOM      1  CA  ALA A   1       1.000   1.000   1.000\nEND\n"
    resp = client.post(
        "/api/runs",
        data={"system_config": '{"box": {"type": "hexagonal"}}'},
        files={"pdb_file": ("test.pdb", pdb_content, "chemical/x-pdb")},
    )
    assert resp.status_code == 400


def test_create_run_without_system_config_succeeds(client):
    pdb_content = b"ATOM      1  CA  ALA A   1       1.000   1.000   1.000\nEND\n"
    resp = client.post(
        "/api/runs",
        files={"pdb_file": ("test.pdb", pdb_content, "chemical/x-pdb")},
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    # No system_config.json created when field is absent
    config_path = tmp_harness / "runs" / run_id / "system_config.json"
    assert not config_path.exists()
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_presets_api.py::test_create_run_with_system_config_saves_file tests/test_presets_api.py::test_create_run_with_invalid_system_config_returns_400 tests/test_presets_api.py::test_create_run_without_system_config_succeeds -v
```

Expected: `FAILED` — system_config field not accepted yet.

- [ ] **Step 3: Modify `api_create_run` in `web/server.py`**

Add import at top of `web/server.py` (with other lib imports):

```python
from lib.system_config import validate_solution_config
```

Modify the `api_create_run` signature to add the new field (after `auto_approve`):

```python
    async def api_create_run(
        hd: HarnessDir,
        pdb_file: UploadFile = File(...),
        forcefield: str = Form("charmm36"),
        water: str = Form("tip3p"),
        box_type: str = Form("dodecahedron"),
        tutorial_id: str = Form(""),
        llm: str = Form(""),
        auto_approve: str = Form("false"),
        system_config: str = Form(""),
    ) -> dict:
```

After the line `(ws / "meta.json").write_text(json.dumps(meta, indent=2))` (around line 343), add:

```python
        if system_config.strip():
            try:
                config_data = json.loads(system_config)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="system_config is not valid JSON")
            errors = validate_solution_config(config_data)
            if errors:
                raise HTTPException(status_code=400, detail="; ".join(errors))
            (ws / "system_config.json").write_text(json.dumps(config_data, indent=2))
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
pytest tests/test_presets_api.py -v
```

Expected: All 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/server.py tests/test_presets_api.py
git commit -m "feat: extend POST /api/runs to accept optional system_config JSON field"
```

---

## Task 5: LLM Constraint Injection in `llm_runner.py`

**Files:**
- Modify: `web/llm_runner.py`
- Create: `tests/test_llm_constraint_injection.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_llm_constraint_injection.py`:

```python
import json
import pytest
from pathlib import Path
from web.llm_runner import _apply_system_config_constraint


def test_returns_empty_string_when_no_config(tmp_path):
    assert _apply_system_config_constraint(tmp_path) == ""


def test_returns_constraint_block_when_config_present(tmp_path):
    config = {
        "forcefield": {"name": "charmm36-jul2022", "water_model": "tip3p"},
        "box": {"type": "dodecahedron", "edge_distance_nm": 1.0},
    }
    (tmp_path / "system_config.json").write_text(json.dumps(config))
    result = _apply_system_config_constraint(tmp_path)
    assert "SYSTEM BUILDER CONSTRAINTS" in result
    assert "charmm36-jul2022" in result


def test_constraint_block_mentions_ion_settings(tmp_path):
    config = {"ions": {"salt_type": "KCl", "concentration_M": 0.2, "neutralize": True}}
    (tmp_path / "system_config.json").write_text(json.dumps(config))
    result = _apply_system_config_constraint(tmp_path)
    assert "KCl" in result
    assert "0.2" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm_constraint_injection.py -v
```

Expected: `ImportError: cannot import name '_apply_system_config_constraint'`

- [ ] **Step 3: Add `_apply_system_config_constraint` and wire it into `run_llm_agent` in `web/llm_runner.py`**

Add import at the top of `web/llm_runner.py` (with existing imports):

```python
from lib.system_config import load_config, build_constraint_prompt
```

Add the helper function after the `strip_ansi` function (around line 41):

```python
def _apply_system_config_constraint(workspace: Path) -> str:
    """Return constraint block if system_config.json exists, else empty string."""
    config = load_config(workspace)
    if config is None:
        return ""
    return build_constraint_prompt(config)
```

In `run_llm_agent`, modify the prompt line (around line 87) from:

```python
    prompt = adapter.build_prompt(harness_dir, workspace, pdb_path)
```

to:

```python
    prompt = adapter.build_prompt(harness_dir, workspace, pdb_path)
    prompt += _apply_system_config_constraint(workspace)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_llm_constraint_injection.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add web/llm_runner.py tests/test_llm_constraint_injection.py
git commit -m "feat: inject system_config constraints into LLM prompt when builder config is present"
```

---

## Task 6: Wire Config Validator into Audit Endpoint

**Files:**
- Modify: `web/server.py` (`api_audit_run` function only)

- [ ] **Step 1: Write failing test**

Append to `tests/test_system_config_validator.py`:

```python
# ── Audit endpoint integration ────────────────────────────────────────────────

def test_audit_endpoint_includes_config_audit(tmp_path):
    from web.server import create_app
    from fastapi.testclient import TestClient

    runs_dir = tmp_path / "runs"
    run_id = "protein_20260101_120000"
    ws = runs_dir / run_id
    ws.mkdir(parents=True)

    config = {
        "forcefield": {"name": "charmm36-jul2022", "water_model": "tip3p"},
        "box": {"type": "dodecahedron"},
    }
    (ws / "system_config.json").write_text(json.dumps(config))
    state = {
        "step_outputs": {
            "step_1": {"forcefield": "charmm36", "water_model": "tip3p"},
            "step_2": {"box_type": "dodecahedron"},
        }
    }
    (ws / "state.json").write_text(json.dumps(state))
    (ws / "meta.json").write_text("{}")

    app = create_app(harness_dir=tmp_path)
    client = TestClient(app)

    resp = client.get(f"/api/runs/{run_id}/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert "config_audit" in data
    assert data["config_audit"]["has_config"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_system_config_validator.py::test_audit_endpoint_includes_config_audit -v
```

Expected: `AssertionError: 'config_audit' not in {...}`

- [ ] **Step 3: Modify `api_audit_run` in `web/server.py`**

Replace the existing `api_audit_run` function (around lines 269-276):

```python
    @app.get("/api/runs/{run_id}/audit")
    def api_audit_run(run_id: str, hd: HarnessDir) -> dict:
        workspace = _check_run_id(run_id, hd / "runs")
        if not workspace.is_dir():
            raise HTTPException(status_code=404, detail="run not found")
        from lib.tutorial_auditor import audit_run
        from lib.system_config_validator import validate_run_against_config
        report = audit_run(workspace)
        config_report = validate_run_against_config(workspace)
        result = report.to_dict()
        result["config_audit"] = config_report.to_dict()
        return result
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/server.py tests/test_system_config_validator.py
git commit -m "feat: include system_config compliance in /api/runs/{id}/audit response"
```

---

## Task 7: Frontend — 6-Step Wizard UI

**Files:**
- Modify: `web/static/index.html`

Note: Frontend cannot be TDD'd with pytest. Verify manually using the dev server.

- [ ] **Step 1: Add CSS for wizard navigation**

In `web/static/index.html`, locate the comment `/* New Run */` (around line 839) and add the following CSS block immediately before `#new-run-view,`:

```css
/* System Builder Wizard */
#wizard-nav {
  display: flex;
  overflow-x: auto;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 18px;
  gap: 0;
}
.wiz-tab {
  padding: 7px 13px;
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  border-bottom: 2px solid transparent;
  cursor: default;
  transition: color 0.15s;
}
.wiz-tab.active { color: var(--accent-primary); border-bottom-color: var(--accent-primary); }
.wiz-tab.done   { color: var(--accent-green);   border-bottom-color: var(--accent-green); }
.wiz-section    { display: none; }
.wiz-section.active { display: block; }
#wiz-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.expert-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0 4px;
  font-size: 12px;
  color: var(--text-secondary);
  border-top: 1px solid var(--border-color);
  margin-top: 8px;
}
```

- [ ] **Step 2: Replace `#new-run-form` contents with wizard structure**

Locate `<form id="new-run-form"` (line 1593) and replace everything from `<h2>Simulation Run</h2>` down to (but not including) `</form>` with the following wizard structure:

```html
          <h2>System Builder</h2>

          <!-- Wizard nav tabs -->
          <div id="wizard-nav">
            <div class="wiz-tab active" id="wiz-tab-1">1. Structure</div>
            <div class="wiz-tab" id="wiz-tab-2">2. Force Field</div>
            <div class="wiz-tab" id="wiz-tab-3">3. Box</div>
            <div class="wiz-tab" id="wiz-tab-4">4. Ions</div>
            <div class="wiz-tab" id="wiz-tab-5" style="display:none">5. Simulation</div>
            <div class="wiz-tab" id="wiz-tab-6">6. Start</div>
          </div>

          <!-- Step 1: PDB Upload -->
          <div class="wiz-section active" id="wiz-section-1">
            <div id="drop-zone"
              onclick="document.getElementById('pdb-input').click()"
              ondragover="event.preventDefault(); this.style.borderColor='var(--accent-primary)'"
              ondragleave="this.style.borderColor=''"
              ondrop="event.preventDefault(); this.style.borderColor=''; handleFileSelect(event.dataTransfer.files[0])">
              <div class="upload-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
              </div>
              <p>Drop PDB file here</p>
              <small>or click to browse from files</small>
              <div id="selected-file"></div>
            </div>
            <input type="file" id="pdb-input" accept=".pdb" onchange="handleFileSelect(this.files[0])">
            <div class="expert-row">
              <input type="checkbox" id="expert-toggle" onchange="wizardToggleExpert(this.checked)">
              <label for="expert-toggle">Expert Mode — configure simulation parameters (Step 5)</label>
            </div>
          </div>

          <!-- Step 2: Force Field & Water Model -->
          <div class="wiz-section" id="wiz-section-2">
            <div class="param-grid">
              <div class="param-field">
                <label>Force Field
                  <button type="button" id="ff-manager-btn" title="Force Field 추가"
                    style="margin-left:6px;padding:2px;font-size:16px;line-height:1;border:none;background:transparent;color:var(--text-secondary);cursor:pointer;vertical-align:middle;">+</button>
                </label>
                <select name="forcefield" id="forcefield-select">
                  <option value="">Loading...</option>
                </select>
              </div>
              <div class="param-field">
                <label>Water Model</label>
                <select name="water" id="water-select">
                  <option value="">Select forcefield first</option>
                </select>
              </div>
              <div class="param-field">
                <label>Tutorial</label>
                <select name="tutorial_id" id="tutorial-select">
                  <option value="">Auto-detect</option>
                </select>
              </div>
            </div>
          </div>

          <!-- Step 3: Box Settings -->
          <div class="wiz-section" id="wiz-section-3">
            <div class="param-grid">
              <div class="param-field">
                <label>Box Type</label>
                <select name="box_type" id="box-type-select">
                  <option value="dodecahedron">Dodecahedron (recommended)</option>
                  <option value="cubic">Cubic</option>
                  <option value="octahedron">Octahedron</option>
                </select>
              </div>
              <div class="param-field">
                <label>Edge Distance (nm)
                  <span style="font-size:11px;color:var(--text-secondary);font-weight:400;"> — min gap from molecule to box wall</span>
                </label>
                <input type="number" id="edge-distance" name="edge_distance_nm" value="1.0" min="0.5" max="5.0" step="0.1" style="background:var(--bg-input);border:1px solid var(--border-color);color:var(--text-primary);padding:6px 8px;border-radius:4px;width:100%;box-sizing:border-box;">
              </div>
            </div>
          </div>

          <!-- Step 4: Ion Settings -->
          <div class="wiz-section" id="wiz-section-4">
            <div class="param-grid">
              <div class="param-field">
                <label>Salt Type</label>
                <select id="ion-salt-type" name="salt_type">
                  <option value="NaCl">NaCl (physiological)</option>
                  <option value="KCl">KCl</option>
                  <option value="MgCl2">MgCl₂</option>
                  <option value="CaCl2">CaCl₂</option>
                </select>
              </div>
              <div class="param-field">
                <label>Concentration (M)</label>
                <input type="number" id="ion-concentration" name="concentration_M" value="0.15" min="0" max="2" step="0.01" style="background:var(--bg-input);border:1px solid var(--border-color);color:var(--text-primary);padding:6px 8px;border-radius:4px;width:100%;box-sizing:border-box;">
              </div>
            </div>
            <div class="expert-row" style="border-top:none;padding-top:0;">
              <input type="checkbox" id="ion-neutralize" checked>
              <label for="ion-neutralize">Neutralize system charge (add/remove ions to reach net charge 0)</label>
            </div>
          </div>

          <!-- Step 5: Simulation Parameters (Expert only) -->
          <div class="wiz-section" id="wiz-section-5">
            <div class="param-grid">
              <div class="param-field">
                <label>Temperature (K)</label>
                <input type="number" id="sim-temperature" name="temperature_K" value="300" min="200" max="500" style="background:var(--bg-input);border:1px solid var(--border-color);color:var(--text-primary);padding:6px 8px;border-radius:4px;width:100%;box-sizing:border-box;">
              </div>
              <div class="param-field">
                <label>Pressure (bar)</label>
                <input type="number" id="sim-pressure" name="pressure_bar" value="1.0" min="0.1" max="10" step="0.1" style="background:var(--bg-input);border:1px solid var(--border-color);color:var(--text-primary);padding:6px 8px;border-radius:4px;width:100%;box-sizing:border-box;">
              </div>
              <div class="param-field">
                <label>Simulation Time (ns)</label>
                <input type="number" id="sim-time" name="sim_time_ns" value="1.0" min="0.001" max="1000" step="0.1" style="background:var(--bg-input);border:1px solid var(--border-color);color:var(--text-primary);padding:6px 8px;border-radius:4px;width:100%;box-sizing:border-box;">
              </div>
              <div class="param-field">
                <label>Thermostat</label>
                <select id="sim-thermostat" name="thermostat">
                  <option value="V-rescale">V-rescale (recommended)</option>
                  <option value="Nosé-Hoover">Nosé-Hoover</option>
                </select>
              </div>
              <div class="param-field">
                <label>Barostat</label>
                <select id="sim-barostat" name="barostat">
                  <option value="Parrinello-Rahman">Parrinello-Rahman (recommended)</option>
                  <option value="Berendsen">Berendsen</option>
                </select>
              </div>
            </div>
          </div>

          <!-- Step 6: Summary + Preset + LLM + Start -->
          <div class="wiz-section" id="wiz-section-6">
            <div id="wiz-summary" style="background:var(--bg-secondary);border-radius:6px;padding:12px 14px;font-size:12px;margin-bottom:14px;line-height:1.8;"></div>

            <div class="param-grid" style="margin-bottom:10px;">
              <div class="param-field">
                <label>Save as Preset (optional)</label>
                <div style="display:flex;gap:6px;">
                  <input type="text" id="preset-name-input" placeholder="e.g. Lysozyme Standard" style="flex:1;background:var(--bg-input);border:1px solid var(--border-color);color:var(--text-primary);padding:6px 8px;border-radius:4px;">
                  <button type="button" onclick="wizardSavePreset()" style="padding:6px 12px;background:var(--accent-secondary);color:var(--text-primary);border:none;border-radius:4px;cursor:pointer;font-size:12px;">Save</button>
                </div>
              </div>
              <div class="param-field">
                <label>Load Preset</label>
                <select id="preset-load-select" onchange="wizardLoadPreset(this.value)">
                  <option value="">— select preset —</option>
                </select>
              </div>
            </div>

            <div class="llm-section">
              <div class="llm-section-title">LLM AI Copilot Agent</div>
              <div class="param-grid">
                <div class="param-field">
                  <label>Select Agent Model</label>
                  <select name="llm" id="llm-select">
                    <option value="">None (direct pipeline)</option>
                    <option value="gemini">Gemini 3.5 Flash</option>
                    <option value="claude">Claude 3.5 Sonnet</option>
                  </select>
                </div>
                <div class="param-field">
                  <label>Permission Mode</label>
                  <select name="auto_approve">
                    <option value="false">Interactive approvals</option>
                    <option value="true">Auto-approve actions</option>
                  </select>
                </div>
              </div>
            </div>

            <button type="submit" id="btn-start" disabled>Start Simulation Run</button>
          </div>

          <!-- Wizard footer navigation -->
          <div id="wiz-footer">
            <button type="button" id="wiz-back-btn" onclick="wizardBack()" style="display:none;padding:7px 16px;background:var(--bg-secondary);color:var(--text-primary);border:1px solid var(--border-color);border-radius:4px;cursor:pointer;font-size:13px;">← Back</button>
            <button type="button" id="wiz-next-btn" onclick="wizardNext()" style="padding:7px 16px;background:var(--accent-primary);color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px;">Next →</button>
          </div>
```

- [ ] **Step 3: Add wizard JavaScript functions**

Locate the `startRun` function (around line 2061) and add these functions immediately before it:

```javascript
// ── System Builder Wizard ─────────────────────────────────────────────────────

let _wizardStep = 1;
let _wizardExpert = false;
const _WIZ_TOTAL_STEPS_NORMAL = 6;  // step 5 is skipped unless expert

function _wizardMaxStep() {
  return _wizardExpert ? 6 : 6;  // always 6, but step 5 is only reachable in expert mode
}

function _wizardVisibleSteps() {
  return _wizardExpert ? [1,2,3,4,5,6] : [1,2,3,4,6];
}

function _wizardNextStep(current) {
  const steps = _wizardVisibleSteps();
  const idx = steps.indexOf(current);
  return idx < steps.length - 1 ? steps[idx + 1] : current;
}

function _wizardPrevStep(current) {
  const steps = _wizardVisibleSteps();
  const idx = steps.indexOf(current);
  return idx > 0 ? steps[idx - 1] : current;
}

function wizardToggleExpert(on) {
  _wizardExpert = on;
  document.getElementById('wiz-tab-5').style.display = on ? '' : 'none';
}

function _wizardShowStep(step) {
  _wizardStep = step;
  // sections
  for (let i = 1; i <= 6; i++) {
    const sec = document.getElementById(`wiz-section-${i}`);
    if (sec) sec.classList.toggle('active', i === step);
  }
  // tabs
  const visible = _wizardVisibleSteps();
  for (let i = 1; i <= 6; i++) {
    const tab = document.getElementById(`wiz-tab-${i}`);
    if (!tab) continue;
    tab.classList.remove('active', 'done');
    if (i === step) tab.classList.add('active');
    else if (visible.indexOf(i) !== -1 && visible.indexOf(i) < visible.indexOf(step)) tab.classList.add('done');
  }
  // navigation buttons
  const backBtn = document.getElementById('wiz-back-btn');
  const nextBtn = document.getElementById('wiz-next-btn');
  const isFirst = visible.indexOf(step) === 0;
  const isLast  = step === 6;
  backBtn.style.display = isFirst ? 'none' : '';
  nextBtn.style.display = isLast ? 'none' : '';
  // on final step, populate summary
  if (step === 6) { _wizardBuildSummary(); wizardLoadPresets(); }
}

function wizardNext() {
  if (_wizardStep === 1 && !selectedPdb) {
    showToast('Please upload a PDB file first', 'error');
    return;
  }
  const next = _wizardNextStep(_wizardStep);
  if (next !== _wizardStep) _wizardShowStep(next);
}

function wizardBack() {
  const prev = _wizardPrevStep(_wizardStep);
  if (prev !== _wizardStep) _wizardShowStep(prev);
}

function _wizardCollectConfig() {
  const ff    = document.getElementById('forcefield-select')?.value || '';
  const water = document.getElementById('water-select')?.value || '';
  const boxType = document.getElementById('box-type-select')?.value || 'dodecahedron';
  const edgeDist = parseFloat(document.getElementById('edge-distance')?.value || '1.0');
  const saltType = document.getElementById('ion-salt-type')?.value || 'NaCl';
  const conc = parseFloat(document.getElementById('ion-concentration')?.value || '0.15');
  const neutralize = document.getElementById('ion-neutralize')?.checked ?? true;

  const config = {
    version: '1.0',
    builder_type: 'solution',
    structure: { pdb_filename: selectedPdb?.name || '' },
    forcefield: { name: ff, water_model: water, terminal_patches: 'auto' },
    box: { type: boxType, edge_distance_nm: edgeDist },
    ions: { salt_type: saltType, concentration_M: conc, neutralize },
    simulation: { _expert_mode: _wizardExpert },
    meta: { created_at: new Date().toISOString(), builder_version: '1.0' },
  };

  if (_wizardExpert) {
    config.simulation.temperature_K = parseFloat(document.getElementById('sim-temperature')?.value || '300');
    config.simulation.pressure_bar  = parseFloat(document.getElementById('sim-pressure')?.value || '1.0');
    config.simulation.sim_time_ns   = parseFloat(document.getElementById('sim-time')?.value || '1.0');
    config.simulation.thermostat    = document.getElementById('sim-thermostat')?.value || 'V-rescale';
    config.simulation.barostat      = document.getElementById('sim-barostat')?.value || 'Parrinello-Rahman';
  }
  return config;
}

function _wizardBuildSummary() {
  const config = _wizardCollectConfig();
  const ff = config.forcefield;
  const box = config.box;
  const ions = config.ions;
  const sim = config.simulation;
  let html = `
    <strong>Force field:</strong> ${ff.name || '(not set)'} &nbsp;|&nbsp; <strong>Water:</strong> ${ff.water_model || '(not set)'}<br>
    <strong>Box:</strong> ${box.type}, edge ${box.edge_distance_nm} nm<br>
    <strong>Ions:</strong> ${ions.salt_type} ${ions.concentration_M} M, neutralize=${ions.neutralize}
  `;
  if (sim._expert_mode) {
    html += `<br><strong>Temperature:</strong> ${sim.temperature_K} K &nbsp;|&nbsp; <strong>Pressure:</strong> ${sim.pressure_bar} bar &nbsp;|&nbsp; <strong>Time:</strong> ${sim.sim_time_ns} ns`;
  }
  document.getElementById('wiz-summary').innerHTML = html;
}

async function wizardLoadPresets() {
  try {
    const resp = await fetch('/api/presets');
    if (!resp.ok) return;
    const presets = await resp.json();
    const sel = document.getElementById('preset-load-select');
    sel.innerHTML = '<option value="">— select preset —</option>';
    presets.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.name;
      opt.textContent = p.name;
      sel.appendChild(opt);
    });
  } catch (_) {}
}

function wizardLoadPreset(name) {
  if (!name) return;
  fetch('/api/presets')
    .then(r => r.json())
    .then(presets => {
      const preset = presets.find(p => p.name === name);
      if (!preset) return;
      const c = preset.config;
      if (c.forcefield?.name) document.getElementById('forcefield-select').value = c.forcefield.name;
      if (c.forcefield?.water_model) document.getElementById('water-select').value = c.forcefield.water_model;
      if (c.box?.type) document.getElementById('box-type-select').value = c.box.type;
      if (c.box?.edge_distance_nm != null) document.getElementById('edge-distance').value = c.box.edge_distance_nm;
      if (c.ions?.salt_type) document.getElementById('ion-salt-type').value = c.ions.salt_type;
      if (c.ions?.concentration_M != null) document.getElementById('ion-concentration').value = c.ions.concentration_M;
      if (c.ions?.neutralize != null) document.getElementById('ion-neutralize').checked = c.ions.neutralize;
      if (c.simulation?._expert_mode) {
        document.getElementById('expert-toggle').checked = true;
        wizardToggleExpert(true);
        if (c.simulation.temperature_K) document.getElementById('sim-temperature').value = c.simulation.temperature_K;
        if (c.simulation.pressure_bar)  document.getElementById('sim-pressure').value  = c.simulation.pressure_bar;
        if (c.simulation.sim_time_ns)   document.getElementById('sim-time').value       = c.simulation.sim_time_ns;
        if (c.simulation.thermostat)    document.getElementById('sim-thermostat').value = c.simulation.thermostat;
        if (c.simulation.barostat)      document.getElementById('sim-barostat').value   = c.simulation.barostat;
      }
      _wizardBuildSummary();
      showToast(`Preset "${name}" loaded`, 'info');
    })
    .catch(() => showToast('Failed to load preset', 'error'));
}

async function wizardSavePreset() {
  const name = document.getElementById('preset-name-input').value.trim();
  if (!name) { showToast('Enter a preset name first', 'error'); return; }
  const config = _wizardCollectConfig();
  try {
    const resp = await fetch('/api/presets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, config }),
    });
    if (resp.ok) {
      showToast(`Preset "${name}" saved`, 'info');
      wizardLoadPresets();
    } else {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || 'Failed to save preset', 'error');
    }
  } catch (_) { showToast('Server error', 'error'); }
}
```

- [ ] **Step 4: Modify `startRun()` to include `system_config` in FormData**

Replace the existing `startRun` function with:

```javascript
async function startRun() {
  if (!selectedPdb) return;

  const form = document.getElementById('new-run-form');
  const config = _wizardCollectConfig();
  const data = new FormData();
  data.append('pdb_file', selectedPdb);
  data.append('forcefield', form.querySelector('[name="forcefield"]').value);
  data.append('water', form.querySelector('[name="water"]').value);
  data.append('box_type', form.querySelector('[name="box_type"]')?.value || config.box.type);
  data.append('tutorial_id', form.querySelector('[name="tutorial_id"]').value);
  data.append('llm', form.querySelector('[name="llm"]').value);
  data.append('auto_approve', form.querySelector('[name="auto_approve"]').value);
  data.append('system_config', JSON.stringify(config));

  const btnStart = document.getElementById('btn-start');
  btnStart.disabled = true;
  btnStart.textContent = 'Starting...';

  try {
    const resp = await fetch('/api/runs', { method: 'POST', body: data });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || '런 시작에 실패했습니다.', 'error');
      btnStart.disabled = false;
      btnStart.textContent = 'Start Simulation Run';
      return;
    }
    const { run_id } = await resp.json();
    selectedPdb = null;
    document.getElementById('selected-file').textContent = '';
    btnStart.disabled = false;
    btnStart.textContent = 'Start Simulation Run';
    _wizardShowStep(1);
    await loadRuns();
    selectRun(run_id);
  } catch (e) {
    showToast('서버 연결 오류', 'error');
    btnStart.disabled = false;
    btnStart.textContent = 'Start Simulation Run';
  }
}
```

- [ ] **Step 5: Start the dev server and manually verify**

```bash
python main.py
```

Open http://localhost:7860 (or whichever port is configured). Verify:

1. Click "New Run" → Select "Simulation" → Wizard opens at Step 1 (PDB upload area visible, wizard nav tabs visible)
2. Upload a PDB file → "Next →" button becomes active → click Next → Step 2 shows (Force Field & Water dropdowns)
3. Click through Steps 3 (box settings) and 4 (ion settings) → fields are populated with defaults
4. On Step 6: summary section shows correct values, preset save input is visible, LLM section is visible, "Start Simulation Run" button is visible
5. Toggle "Expert Mode" on Step 1 → Step 5 tab appears in nav → clicking through steps includes Step 5
6. Save a preset on Step 6 → reload page → load preset from dropdown → fields are populated
7. Submit a run → run appears in the run list → `runs/{id}/system_config.json` exists

- [ ] **Step 6: Commit**

```bash
git add web/static/index.html
git commit -m "feat: replace create-run modal with 6-step System Builder wizard"
```

---

## Task 8: Final Integration Smoke Test

- [ ] **Step 1: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass (no regressions).

- [ ] **Step 2: Verify audit endpoint includes config_audit**

Start the server and create a run with `system_config`. After run completes, hit:

```
GET /api/runs/{run_id}/audit
```

Expected response shape:
```json
{
  "tutorial_id": "...",
  "passed": 2,
  "failed": 0,
  "items": [...],
  "config_audit": {
    "has_config": true,
    "passed": 3,
    "failed": 0,
    "items": [
      {"key": "forcefield", "expected": "charmm36-jul2022", "actual": "charmm36", "status": "pass"},
      {"key": "water_model", "expected": "tip3p", "actual": "tip3p", "status": "pass"},
      {"key": "box_type", "expected": "dodecahedron", "actual": "dodecahedron", "status": "pass"}
    ]
  }
}
```

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: system builder implementation complete — all tests passing"
```
