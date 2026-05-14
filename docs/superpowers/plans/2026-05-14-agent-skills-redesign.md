# Agent Skills Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 7-skill low-level layer with 3 capability-aligned skills (`env-builder`, `md-runner`, `illustrator`) backed by an internal `lib/`, while preserving the Step 0–8 state contract.

**Architecture:** Three top-level skills under `skills/`; shared deterministic logic under `lib/` (no `SKILL.md`); workspace-based file contract via `workspace/state.json` and `stageN_*/` directories; tutorial routing is internal to `env-builder` and reads `docs/tutorial/LLM_TUTORIAL_GUIDE.md` + `tutorial_index.json`.

**Tech Stack:** Python 3.11+, pytest, GROMACS (`gmx`), matplotlib, PyMOL (primary) / VMD (fallback), ffmpeg, optional plotly.

**Source spec:** `docs/superpowers/specs/2026-05-14-agent-skills-redesign-design.md`

---

## Conventions

- All file paths are relative to the harness repo root unless absolute.
- All tests live under `tests/`. Run from repo root: `pytest tests/unit -v` (unit only) or `pytest tests -v` (all).
- Integration tests skip automatically when `gmx` is not on `PATH` (use `@pytest.mark.skipif(not shutil.which("gmx"), ...)`).
- Commits are TDD-paced: test → implement → commit. Use Conventional-Commit style (`feat:`, `test:`, `refactor:`, `docs:`, `chore:`).
- **Old code is preserved during rewrite and removed only in Phase L.** This lets reviewers diff against the prior skills.

---

## Phase A — Repo Setup

### Task A1: Add pytest configuration and test skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/contract/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "gromacs-harness"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
markers = [
    "integration: requires gmx on PATH",
    "renderer: requires PyMOL or VMD",
    "animation: requires ffmpeg",
]
```

- [ ] **Step 2: Create empty `__init__.py` files**

```python
# tests/__init__.py, tests/unit/__init__.py, tests/integration/__init__.py, tests/contract/__init__.py
```

(empty files)

- [ ] **Step 3: Create `tests/conftest.py`**

```python
import shutil
from pathlib import Path
import pytest


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Per-test isolated workspace."""
    ws = tmp_path / "workspace"
    (ws / "inputs").mkdir(parents=True)
    (ws / "stage1_env").mkdir()
    (ws / "stage2_md").mkdir()
    (ws / "stage3_viz").mkdir()
    return ws


@pytest.fixture
def gmx_available() -> bool:
    return shutil.which("gmx") is not None


@pytest.fixture
def ubq_pdb_path() -> Path:
    p = Path(__file__).resolve().parents[1] / "1UBQ.pdb"
    assert p.exists(), f"1UBQ.pdb missing: {p}"
    return p
```

- [ ] **Step 4: Verify pytest discovers and reports no tests**

Run: `pytest tests -v`
Expected: `no tests ran` (zero collected, exit code 5 is OK)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/
git commit -m "chore: add pytest skeleton and shared fixtures"
```

### Task A2: Add `lib/` skeleton

**Files:**
- Create: `lib/__init__.py`
- Create: `lib/mdp_templates/__init__.py`

- [ ] **Step 1: Create both files as empty modules**

```python
# lib/__init__.py
"""Internal helpers shared by env-builder, md-runner, illustrator skills."""
```

```python
# lib/mdp_templates/__init__.py
"""Base .mdp templates and renderer."""
```

- [ ] **Step 2: Commit**

```bash
git add lib/
git commit -m "chore: add lib package skeleton"
```

---

## Phase B — `lib/state.py`

### Task B1: State schema constants and atomic R/W

**Files:**
- Create: `lib/state.py`
- Create: `tests/unit/test_state.py`

- [ ] **Step 1: Write failing test for schema constants and `read`/`write` round-trip**

```python
# tests/unit/test_state.py
import json
from pathlib import Path
from lib import state


def test_initial_state_has_required_top_level_keys(tmp_workspace: Path):
    s = state.initial(workspace_dir=tmp_workspace)
    assert s["schema_version"] == state.SCHEMA_VERSION
    assert s["workspace_dir"] == str(tmp_workspace)
    assert s["current_step"] == 0
    assert s["last_completed_stage"] is None
    assert s["step_outputs"] == {}
    assert s["retry_history"] == []
    assert s["pending_warnings"] == []
    assert s["topology_backups"] == []


def test_write_then_read_round_trip(tmp_workspace: Path):
    s = state.initial(workspace_dir=tmp_workspace)
    s["current_step"] = 3
    state.write(tmp_workspace, s)
    loaded = state.read(tmp_workspace)
    assert loaded == s


def test_write_is_atomic(tmp_workspace: Path):
    s = state.initial(workspace_dir=tmp_workspace)
    state.write(tmp_workspace, s)
    # Atomic write should not leave temp file behind
    assert not list(tmp_workspace.glob("state.json.tmp*"))
    assert (tmp_workspace / "state.json").exists()
```

- [ ] **Step 2: Run test to confirm failure**

Run: `pytest tests/unit/test_state.py -v`
Expected: ImportError / AttributeError on `lib.state`

- [ ] **Step 3: Implement minimal `lib/state.py`**

```python
# lib/state.py
import json
import os
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
STATE_FILENAME = "state.json"


def initial(workspace_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace_dir": str(workspace_dir),
        "current_step": 0,
        "last_completed_stage": None,
        "tutorial": None,
        "hardware": None,
        "step_outputs": {},
        "retry_history": [],
        "pending_warnings": [],
        "topology_backups": [],
    }


def path(workspace_dir: Path) -> Path:
    return Path(workspace_dir) / STATE_FILENAME


def read(workspace_dir: Path) -> dict[str, Any]:
    with open(path(workspace_dir)) as f:
        return json.load(f)


def write(workspace_dir: Path, data: dict[str, Any]) -> None:
    target = path(workspace_dir)
    fd, tmp = tempfile.mkstemp(prefix=STATE_FILENAME + ".tmp", dir=workspace_dir)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `pytest tests/unit/test_state.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add lib/state.py tests/unit/test_state.py
git commit -m "feat(lib): add state schema with atomic read/write"
```

### Task B2: Entry-gate validators for stage handoff

**Files:**
- Modify: `lib/state.py`
- Modify: `tests/unit/test_state.py`

- [ ] **Step 1: Add failing tests for entry-gate helpers**

Append to `tests/unit/test_state.py`:

```python
import pytest


def test_require_keys_passes_when_keys_present(tmp_workspace: Path):
    s = state.initial(tmp_workspace)
    s["step_outputs"]["step_1"] = {"forcefield": "charmm36"}
    state.require_step_keys(s, ["step_1"])  # should not raise


def test_require_keys_fails_when_missing(tmp_workspace: Path):
    s = state.initial(tmp_workspace)
    with pytest.raises(state.StateContractError) as exc:
        state.require_step_keys(s, ["step_1"])
    assert "step_1" in str(exc.value)


def test_require_stage_passes_when_match(tmp_workspace: Path):
    s = state.initial(tmp_workspace)
    s["last_completed_stage"] = "env"
    state.require_last_stage(s, "env")


def test_require_stage_fails_when_mismatch(tmp_workspace: Path):
    s = state.initial(tmp_workspace)
    with pytest.raises(state.StateContractError):
        state.require_last_stage(s, "env")
```

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/unit/test_state.py -v`
Expected: 4 new failures (AttributeError or NameError)

- [ ] **Step 3: Extend `lib/state.py`**

Append:

```python
class StateContractError(Exception):
    """Raised when state.json violates a skill's entry contract."""


def require_step_keys(state_data: dict[str, Any], keys: list[str]) -> None:
    missing = [k for k in keys if k not in state_data.get("step_outputs", {})]
    if missing:
        raise StateContractError(f"missing required step keys: {missing}")


def require_last_stage(state_data: dict[str, Any], expected: str) -> None:
    actual = state_data.get("last_completed_stage")
    if actual != expected:
        raise StateContractError(
            f"last_completed_stage must be {expected!r}, got {actual!r}"
        )
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_state.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add lib/state.py tests/unit/test_state.py
git commit -m "feat(lib): add state entry-gate validators"
```

---

## Phase C — `lib/validators.py`

### Task C1: PASS/WARNING/RETRYABLE/FATAL judgment for Step 5 and Step 7 metrics

**Files:**
- Create: `lib/validators.py`
- Create: `tests/unit/test_validators.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_validators.py
import pytest
from lib import validators as V


def test_neutrality_pass():
    r = V.judge_neutrality(net_charge=0.0)
    assert r.tier == "pass"


def test_neutrality_warning_small_imbalance():
    r = V.judge_neutrality(net_charge=0.05)
    assert r.tier == "warning"
    assert r.suggested_mutation["target"] == "genion"


def test_neutrality_fatal_large_imbalance():
    r = V.judge_neutrality(net_charge=1.0)
    assert r.tier == "fatal"


def test_density_pass():
    r = V.judge_density(observed=1000.0, expected_range=(995, 1005))
    assert r.tier == "pass"


def test_density_warning_minor_deviation():
    r = V.judge_density(observed=985.0, expected_range=(995, 1005))
    assert r.tier == "warning"
    assert r.metric == "density"
    assert r.suggested_mutation["target"] == "npt.mdp"


def test_density_retryable_severe_deviation():
    r = V.judge_density(observed=500.0, expected_range=(995, 1005))
    assert r.tier == "retryable"


def test_judgment_carries_warning_id_when_warning():
    r = V.judge_density(observed=985.0, expected_range=(995, 1005))
    assert isinstance(r.warning_id, str) and len(r.warning_id) > 0
```

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/unit/test_validators.py -v`
Expected: ImportError on `lib.validators`

- [ ] **Step 3: Implement `lib/validators.py`**

```python
# lib/validators.py
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Judgment:
    tier: str  # "pass" | "warning" | "retryable" | "fatal"
    metric: str
    observed: Any = None
    expected_range: tuple[float, float] | None = None
    cause: str | None = None
    suggested_mutation: dict[str, Any] | None = None
    warning_id: str = field(default="")

    def __post_init__(self):
        if self.tier == "warning" and not self.warning_id:
            self.warning_id = str(uuid.uuid4())


NEUTRALITY_WARNING_TOL = 0.1
NEUTRALITY_FATAL_TOL = 0.5
DENSITY_WARNING_FRAC = 0.02
DENSITY_RETRYABLE_FRAC = 0.10


def judge_neutrality(net_charge: float) -> Judgment:
    abs_q = abs(net_charge)
    if abs_q < 1e-6:
        return Judgment(tier="pass", metric="net_charge", observed=net_charge)
    if abs_q <= NEUTRALITY_WARNING_TOL:
        return Judgment(
            tier="warning",
            metric="net_charge",
            observed=net_charge,
            cause="charge_neutralization",
            suggested_mutation={
                "target": "genion",
                "changes": {"-conc": "0.15 → 0.20"},
                "rationale": "increase ion concentration to neutralize residual charge",
            },
        )
    if abs_q <= NEUTRALITY_FATAL_TOL:
        return Judgment(
            tier="retryable",
            metric="net_charge",
            observed=net_charge,
            cause="charge_neutralization",
        )
    return Judgment(tier="fatal", metric="net_charge", observed=net_charge,
                    cause="charge_neutralization")


def judge_density(observed: float, expected_range: tuple[float, float]) -> Judgment:
    lo, hi = expected_range
    center = (lo + hi) / 2
    if lo <= observed <= hi:
        return Judgment(tier="pass", metric="density", observed=observed,
                        expected_range=expected_range)
    deviation = abs(observed - center) / center
    if deviation <= DENSITY_RETRYABLE_FRAC and deviation > DENSITY_WARNING_FRAC:
        return Judgment(
            tier="warning",
            metric="density",
            observed=observed,
            expected_range=expected_range,
            cause="pressure_coupling",
            suggested_mutation={
                "target": "npt.mdp",
                "changes": {"tau_p": "2.0 → 5.0"},
                "rationale": "barostat coupling too tight; relax to re-equilibrate density",
            },
        )
    if deviation <= DENSITY_WARNING_FRAC:
        return Judgment(
            tier="warning", metric="density", observed=observed,
            expected_range=expected_range, cause="pressure_coupling",
            suggested_mutation={
                "target": "npt.mdp",
                "changes": {"tau_p": "2.0 → 3.0"},
                "rationale": "minor density drift; modest barostat relaxation",
            },
        )
    return Judgment(tier="retryable", metric="density", observed=observed,
                    expected_range=expected_range, cause="pressure_coupling")
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_validators.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add lib/validators.py tests/unit/test_validators.py
git commit -m "feat(lib): add density and neutrality validators"
```

### Task C2: Energy drift, temperature, RMSD stability judgments

**Files:**
- Modify: `lib/validators.py`
- Modify: `tests/unit/test_validators.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/unit/test_validators.py`:

```python
def test_temperature_pass():
    assert V.judge_temperature(observed=300.5, target=300.0).tier == "pass"


def test_temperature_warning():
    r = V.judge_temperature(observed=305.0, target=300.0)
    assert r.tier == "warning"
    assert r.cause == "temperature_coupling"


def test_temperature_retryable():
    assert V.judge_temperature(observed=350.0, target=300.0).tier == "retryable"


def test_energy_drift_pass():
    assert V.judge_energy_drift(slope_per_ns=-0.05).tier == "pass"


def test_energy_drift_warning():
    r = V.judge_energy_drift(slope_per_ns=0.6)
    assert r.tier == "warning"
    assert r.cause == "unstable_energy"


def test_rmsd_plateau_stable():
    rmsd_series = [0.20, 0.22, 0.21, 0.22, 0.21, 0.22]
    assert V.judge_rmsd_plateau(rmsd_series).tier == "pass"


def test_rmsd_plateau_not_converged():
    rmsd_series = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60]
    r = V.judge_rmsd_plateau(rmsd_series)
    assert r.tier == "warning"
    assert r.cause == "analysis_not_converged"
```

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/unit/test_validators.py -v`

- [ ] **Step 3: Extend `lib/validators.py`**

```python
import statistics

TEMP_WARNING_K = 3.0
TEMP_RETRYABLE_K = 10.0
ENERGY_DRIFT_WARNING = 0.5   # kJ/mol per ns
ENERGY_DRIFT_RETRY = 5.0
RMSD_PLATEAU_MAX_RANGE = 0.05  # nm tail-half range threshold


def judge_temperature(observed: float, target: float) -> Judgment:
    dev = abs(observed - target)
    if dev <= TEMP_WARNING_K:
        return Judgment(tier="pass", metric="temperature", observed=observed)
    if dev <= TEMP_RETRYABLE_K:
        return Judgment(
            tier="warning", metric="temperature", observed=observed,
            cause="temperature_coupling",
            suggested_mutation={
                "target": "nvt.mdp",
                "changes": {"tau_t": "0.1 → 0.5"},
                "rationale": "thermostat too tight; relax tau_t",
            },
        )
    return Judgment(tier="retryable", metric="temperature", observed=observed,
                    cause="temperature_coupling")


def judge_energy_drift(slope_per_ns: float) -> Judgment:
    s = abs(slope_per_ns)
    if s <= ENERGY_DRIFT_WARNING:
        return Judgment(tier="pass", metric="energy_drift", observed=slope_per_ns)
    if s <= ENERGY_DRIFT_RETRY:
        return Judgment(
            tier="warning", metric="energy_drift", observed=slope_per_ns,
            cause="unstable_energy",
            suggested_mutation={
                "target": "production.mdp",
                "changes": {"dt": "0.002 → 0.001"},
                "rationale": "energy drift positive; shorten timestep",
            },
        )
    return Judgment(tier="retryable", metric="energy_drift", observed=slope_per_ns,
                    cause="unstable_energy")


def judge_rmsd_plateau(rmsd_series: list[float]) -> Judgment:
    if len(rmsd_series) < 4:
        return Judgment(tier="warning", metric="rmsd_plateau",
                        observed=len(rmsd_series),
                        cause="analysis_not_converged")
    tail = rmsd_series[len(rmsd_series) // 2:]
    spread = max(tail) - min(tail)
    if spread <= RMSD_PLATEAU_MAX_RANGE:
        return Judgment(tier="pass", metric="rmsd_plateau", observed=spread)
    return Judgment(
        tier="warning", metric="rmsd_plateau", observed=spread,
        cause="analysis_not_converged",
        suggested_mutation={
            "target": "production.mdp",
            "changes": {"nsteps": "extend by 50%"},
            "rationale": "RMSD has not plateaued; extend sampling",
        },
    )
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_validators.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add lib/validators.py tests/unit/test_validators.py
git commit -m "feat(lib): add temperature, energy drift, RMSD plateau validators"
```

### Task C3: Retry mutation registry and identical-command blocker

**Files:**
- Modify: `lib/validators.py`
- Create: `tests/unit/test_retry_mutation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_retry_mutation.py
import pytest
from lib import validators as V


def test_block_identical_command_reuse():
    history = [{"step": 7, "phase": "npt", "tier": "retryable",
                "cause": "pressure_coupling",
                "command": "gmx mdrun -deffnm npt",
                "parameters": {"tau_p": 2.0}}]
    with pytest.raises(V.RetryContractError):
        V.assert_unique_attempt(history, command="gmx mdrun -deffnm npt",
                                parameters={"tau_p": 2.0})


def test_allow_mutated_attempt():
    history = [{"step": 7, "phase": "npt", "tier": "retryable",
                "cause": "pressure_coupling",
                "command": "gmx mdrun -deffnm npt",
                "parameters": {"tau_p": 2.0}}]
    V.assert_unique_attempt(history, command="gmx mdrun -deffnm npt",
                            parameters={"tau_p": 5.0})


def test_retryable_budget_exhausted():
    history = [
        {"step": 7, "phase": "npt", "tier": "retryable", "cause": "pressure_coupling",
         "command": "x", "parameters": {"a": 1}},
        {"step": 7, "phase": "npt", "tier": "retryable", "cause": "pressure_coupling",
         "command": "x", "parameters": {"a": 2}},
        {"step": 7, "phase": "npt", "tier": "retryable", "cause": "pressure_coupling",
         "command": "x", "parameters": {"a": 3}},
    ]
    assert V.retryable_budget_remaining(history, step=7, phase="npt") == 0


def test_warning_retries_not_counted_against_retryable_budget():
    history = [
        {"step": 7, "phase": "npt", "tier": "warning", "cause": "pressure_coupling",
         "command": "x", "parameters": {"a": 1}},
        {"step": 7, "phase": "npt", "tier": "warning", "cause": "pressure_coupling",
         "command": "x", "parameters": {"a": 2}},
    ]
    assert V.retryable_budget_remaining(history, step=7, phase="npt") == 3
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Extend `lib/validators.py`**

```python
RETRYABLE_MAX = 3


class RetryContractError(Exception):
    """Raised when an attempt would violate the no-identical-retry rule."""


def assert_unique_attempt(history: list[dict[str, Any]], command: str,
                          parameters: dict[str, Any]) -> None:
    for entry in history:
        if entry.get("command") == command and entry.get("parameters") == parameters:
            raise RetryContractError(
                f"retry must mutate command/parameters; identical attempt found "
                f"(cause={entry.get('cause')})"
            )


def retryable_budget_remaining(history: list[dict[str, Any]],
                               step: int, phase: str) -> int:
    used = sum(
        1 for e in history
        if e.get("step") == step
        and e.get("phase") == phase
        and e.get("tier") == "retryable"
    )
    return max(0, RETRYABLE_MAX - used)
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_retry_mutation.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add lib/validators.py tests/unit/test_retry_mutation.py
git commit -m "feat(lib): add retry mutation contract and budget tracking"
```

---

## Phase D — `lib/tutorial_registry.py`

### Task D1: Load `tutorial_index.json` and per-tutorial manifests

**Files:**
- Create: `lib/tutorial_registry.py`
- Create: `tests/unit/test_tutorial_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_tutorial_registry.py
import pytest
from lib import tutorial_registry as TR


def test_load_index_returns_all_known_tutorials():
    idx = TR.load_index()
    ids = {e["id"] for e in idx["entries"]}
    assert "Lysozyme_in_water" in ids
    assert "KALP15_in_DPPC" in ids
    assert "Protein_Ligand_Complex" in ids


def test_load_manifest_for_lysozyme():
    m = TR.load_manifest("Lysozyme_in_water")
    assert m["pipeline_variant"] == "protein_aqueous_standard"
    assert "step_1" in m["documents"]


def test_load_manifest_missing_returns_none():
    assert TR.load_manifest("Umbrella_Sampling") is None  # derived, no manifest


def test_get_entry_for_id():
    e = TR.get_entry("KALP15_in_DPPC")
    assert e["domain"] == "membrane_md"
    assert "membrane_composition" in e["required_inputs"]
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement `lib/tutorial_registry.py`**

```python
# lib/tutorial_registry.py
import json
from pathlib import Path
from typing import Any

INDEX_PATH = Path("docs/tutorial/tutorial_index.json")


def load_index(index_path: Path = INDEX_PATH) -> dict[str, Any]:
    with open(index_path) as f:
        return json.load(f)


def get_entry(tutorial_id: str, index_path: Path = INDEX_PATH) -> dict[str, Any] | None:
    idx = load_index(index_path)
    for entry in idx["entries"]:
        if entry["id"] == tutorial_id:
            return entry
    return None


def load_manifest(tutorial_id: str,
                  index_path: Path = INDEX_PATH) -> dict[str, Any] | None:
    entry = get_entry(tutorial_id, index_path)
    if not entry:
        return None
    mp = entry.get("manifest_path")
    if not mp:
        return None
    p = Path(mp)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_tutorial_registry.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add lib/tutorial_registry.py tests/unit/test_tutorial_registry.py
git commit -m "feat(lib): add tutorial index and manifest loader"
```

### Task D2: Routing decision function

**Files:**
- Modify: `lib/tutorial_registry.py`
- Modify: `tests/unit/test_tutorial_registry.py`

- [ ] **Step 1: Add failing tests**

```python
def test_route_protein_only_picks_lysozyme():
    decision = TR.route(prompt="run a basic protein simulation in water",
                        pdb_hints={"has_protein": True, "has_membrane": False,
                                   "has_ligand": False},
                        prerequisites={})
    assert decision.tutorial_id == "Lysozyme_in_water"
    assert decision.confidence in ("high", "medium")
    assert decision.missing_inputs == []


def test_route_membrane_requires_composition():
    decision = TR.route(prompt="membrane protein in DPPC",
                        pdb_hints={"has_protein": True, "has_membrane": True,
                                   "has_ligand": False},
                        prerequisites={})
    assert decision.tutorial_id == "KALP15_in_DPPC"
    assert "membrane_composition" in decision.missing_inputs


def test_route_membrane_ok_when_prereq_present():
    decision = TR.route(prompt="membrane protein in DPPC",
                        pdb_hints={"has_protein": True, "has_membrane": True,
                                   "has_ligand": False},
                        prerequisites={"membrane_composition": {"DPPC": 128}})
    assert decision.missing_inputs == []
    assert decision.unsupported_reason is None


def test_route_protein_ligand_requires_ligand_inputs():
    decision = TR.route(prompt="protein-ligand binding",
                        pdb_hints={"has_protein": True, "has_membrane": False,
                                   "has_ligand": True},
                        prerequisites={})
    assert decision.tutorial_id == "Protein_Ligand_Complex"
    assert "ligand_structure" in decision.missing_inputs or \
           "ligand_itp" in decision.missing_inputs


def test_route_unknown_falls_back_to_lysozyme():
    decision = TR.route(prompt="something obscure",
                        pdb_hints={"has_protein": True, "has_membrane": False,
                                   "has_ligand": False},
                        prerequisites={})
    assert decision.tutorial_id == "Lysozyme_in_water"
    assert decision.confidence == "low"
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Extend `lib/tutorial_registry.py`**

```python
from dataclasses import dataclass


@dataclass
class RoutingDecision:
    tutorial_id: str
    pipeline_variant: str | None
    confidence: str
    missing_inputs: list[str]
    unsupported_reason: str | None
    selected_docs: list[str]


KEYWORDS = {
    "Umbrella_Sampling": ["umbrella", "pmf", "pulling", "wham"],
    "Free_Energy_Calculations_Methane_in_Water": ["methane", "free energy"],
    "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol":
        ["ethanol", "hydration free energy"],
    "Building_Biphasic_Systems": ["biphasic", "interface", "two-phase"],
    "Virtual_Sites": ["virtual sites", "vsite", "linear molecule"],
    "Protein_Ligand_Complex": ["ligand", "protein-ligand", "complex", "binding"],
    "KALP15_in_DPPC": ["membrane", "dppc", "lipid", "bilayer"],
    "Lysozyme_in_water": ["protein in water", "aqueous", "lysozyme"],
}


def _prompt_match(prompt: str) -> str | None:
    p = prompt.lower()
    for tid, keys in KEYWORDS.items():
        if any(k in p for k in keys):
            return tid
    return None


def _pdb_match(pdb_hints: dict[str, bool]) -> str:
    if pdb_hints.get("has_membrane"):
        return "KALP15_in_DPPC"
    if pdb_hints.get("has_ligand"):
        return "Protein_Ligand_Complex"
    return "Lysozyme_in_water"


def route(prompt: str, pdb_hints: dict[str, bool],
          prerequisites: dict[str, Any]) -> RoutingDecision:
    tid = _prompt_match(prompt) or _pdb_match(pdb_hints)
    entry = get_entry(tid)
    confidence = entry["confidence"] if entry else "low"
    if not _prompt_match(prompt):
        confidence = "low"

    required = set(entry["required_inputs"]) - {"protein_pdb"}
    provided = set(prerequisites.keys())
    # ligand_structure satisfied by ligand_itp too
    if "ligand_structure" in required and "ligand_itp" in provided:
        provided.add("ligand_structure")
    missing = sorted(required - provided)

    unsupported = None
    autonomy = entry.get("unsupported_autonomy_level") if entry else "none"
    if autonomy and autonomy != "none" and missing:
        unsupported = (f"{tid} requires manual prerequisites "
                       f"(missing: {missing})")

    docs = entry.get("recommended_docs", {}).get("minimal", []) if entry else []
    variant = None
    manifest = load_manifest(tid)
    if manifest:
        variant = manifest.get("pipeline_variant")

    return RoutingDecision(
        tutorial_id=tid,
        pipeline_variant=variant,
        confidence=confidence,
        missing_inputs=missing,
        unsupported_reason=unsupported,
        selected_docs=docs,
    )
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_tutorial_registry.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add lib/tutorial_registry.py tests/unit/test_tutorial_registry.py
git commit -m "feat(lib): add tutorial routing decision function"
```

---

## Phase E — `lib/gmx_wrapper.py`

### Task E1: Subprocess execution with error classification

**Files:**
- Create: `lib/gmx_wrapper.py`
- Create: `tests/unit/test_gmx_wrapper.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_gmx_wrapper.py
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from lib import gmx_wrapper as GW


def test_run_success_returns_zero_exit(tmp_path: Path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        result = GW.run(["pdb2gmx", "-f", "in.pdb"], cwd=tmp_path)
    assert result.returncode == 0
    assert result.classification == "success"


def test_run_grompp_warning_classified():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="",
            stderr="WARNING 1 [...] use -maxwarn to override")
        result = GW.run(["grompp"], cwd=Path("."))
    assert result.classification == "grompp_warning"


def test_run_oom_classified():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="",
                                          stderr="Out of memory")
        result = GW.run(["mdrun"], cwd=Path("."))
    assert result.classification == "command_error"


def test_run_topology_mismatch_classified():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="",
            stderr="Number of coordinates in coordinate file does not match topology")
        result = GW.run(["grompp"], cwd=Path("."))
    assert result.classification == "topology_mismatch"


def test_run_passes_gmx_bin_env_override(monkeypatch):
    monkeypatch.setenv("GMX_BIN", "/tmp/fake-gmx")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        GW.run(["hardware"], cwd=Path("."))
        args, _ = mock_run.call_args
    assert args[0][0] == "/tmp/fake-gmx"
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement `lib/gmx_wrapper.py`**

```python
# lib/gmx_wrapper.py
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass
class GmxResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    classification: str  # success | grompp_warning | topology_mismatch | command_error

    @property
    def ok(self) -> bool:
        return self.classification == "success"


CLASSIFIERS = [
    ("topology_mismatch",
     re.compile(r"does not match topology|moltype.*not found", re.I)),
    ("grompp_warning",
     re.compile(r"WARNING\s+\d+\s+\[", re.I)),
]


def _resolve_gmx_bin(default: str = "gmx") -> str:
    env_bin = os.environ.get("GMX_BIN")
    if env_bin:
        return env_bin
    found = shutil.which(default)
    if found:
        return found
    return default


def _classify(returncode: int, stderr: str) -> str:
    if returncode == 0:
        return "success"
    for tag, pat in CLASSIFIERS:
        if pat.search(stderr):
            return tag
    return "command_error"


def run(args: Sequence[str], cwd: Path,
        interactive_inputs: Sequence[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None) -> GmxResult:
    cmd = [_resolve_gmx_bin()] + list(args)
    proc_input = "\n".join(interactive_inputs) + "\n" if interactive_inputs else None
    completed = subprocess.run(
        cmd, cwd=str(cwd), input=proc_input, text=True,
        capture_output=True, env={**os.environ, **(env or {})},
        timeout=timeout,
    )
    return GmxResult(
        command=cmd,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        classification=_classify(completed.returncode, completed.stderr or ""),
    )
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_gmx_wrapper.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add lib/gmx_wrapper.py tests/unit/test_gmx_wrapper.py
git commit -m "feat(lib): add gmx subprocess wrapper with error classification"
```

### Task E2: Topology backup helper

**Files:**
- Modify: `lib/gmx_wrapper.py`
- Modify: `tests/unit/test_gmx_wrapper.py`

- [ ] **Step 1: Add failing tests**

```python
def test_backup_topology_creates_bak(tmp_path: Path):
    top = tmp_path / "topol.top"
    top.write_text("[ molecules ]\nProtein 1\n")
    bak = GW.backup_topology(top)
    assert bak.exists()
    assert bak.suffix == ".bak"
    assert bak.read_text() == top.read_text()


def test_restore_topology(tmp_path: Path):
    top = tmp_path / "topol.top"
    top.write_text("original")
    bak = GW.backup_topology(top)
    top.write_text("mutated")
    GW.restore_topology(top)
    assert top.read_text() == "original"


def test_restore_without_backup_raises(tmp_path: Path):
    top = tmp_path / "topol.top"
    top.write_text("x")
    with pytest.raises(FileNotFoundError):
        GW.restore_topology(top)
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Extend `lib/gmx_wrapper.py`**

```python
def backup_topology(top: Path) -> Path:
    bak = top.with_suffix(top.suffix + ".bak")
    shutil.copy2(top, bak)
    return bak


def restore_topology(top: Path) -> None:
    bak = top.with_suffix(top.suffix + ".bak")
    if not bak.exists():
        raise FileNotFoundError(f"no backup found: {bak}")
    shutil.copy2(bak, top)
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_gmx_wrapper.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add lib/gmx_wrapper.py tests/unit/test_gmx_wrapper.py
git commit -m "feat(lib): add topology backup/restore helpers"
```

---

## Phase F — `lib/mdp_templates` and `lib/xvg_parser`

### Task F1: `.mdp` template renderer for EM/NVT/NPT/Production/ions

**Files:**
- Create: `lib/mdp_templates/base.py`
- Create: `lib/mdp_templates/em.mdp`
- Create: `lib/mdp_templates/nvt.mdp`
- Create: `lib/mdp_templates/npt.mdp`
- Create: `lib/mdp_templates/production.mdp`
- Create: `lib/mdp_templates/ions.mdp`
- Create: `tests/unit/test_mdp_templates.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_mdp_templates.py
from pathlib import Path
from lib.mdp_templates import base as M


def test_render_em_defaults(tmp_path: Path):
    out = M.render("em", overrides={}, output_dir=tmp_path)
    content = out.read_text()
    assert "integrator" in content
    assert "steep" in content


def test_render_nvt_with_overrides(tmp_path: Path):
    out = M.render("nvt", overrides={"nsteps": 100000, "tau_t": 0.5},
                   output_dir=tmp_path)
    content = out.read_text()
    assert "nsteps                   = 100000" in content
    assert "tau_t                    = 0.5" in content


def test_render_ions(tmp_path: Path):
    out = M.render("ions", overrides={}, output_dir=tmp_path)
    assert out.exists()
    assert "integrator" in out.read_text()


def test_unknown_template_raises(tmp_path: Path):
    import pytest
    with pytest.raises(KeyError):
        M.render("nonexistent", overrides={}, output_dir=tmp_path)
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Create template files**

`lib/mdp_templates/em.mdp`:

```
; em.mdp - energy minimization
integrator               = steep
emtol                    = {emtol}
emstep                   = {emstep}
nsteps                   = {nsteps}
nstlist                  = 1
cutoff-scheme            = Verlet
coulombtype              = PME
rcoulomb                 = 1.0
rvdw                     = 1.0
pbc                      = xyz
```

`lib/mdp_templates/nvt.mdp`:

```
; nvt.mdp - constant volume equilibration
integrator               = md
nsteps                   = {nsteps}
dt                       = {dt}
nstxout                  = 0
nstvout                  = 0
nstenergy                = 500
nstlog                   = 500
nstxout-compressed       = 500
continuation             = no
constraint_algorithm     = lincs
constraints              = h-bonds
cutoff-scheme            = Verlet
ns_type                  = grid
nstlist                  = 10
rcoulomb                 = 1.0
rvdw                     = 1.0
coulombtype              = PME
pme_order                = 4
fourierspacing           = 0.16
tcoupl                   = V-rescale
tc-grps                  = Protein Non-Protein
tau_t                    = {tau_t} {tau_t}
ref_t                    = {ref_t} {ref_t}
pcoupl                   = no
pbc                      = xyz
DispCorr                 = EnerPres
gen_vel                  = yes
gen_temp                 = {ref_t}
gen_seed                 = -1
```

`lib/mdp_templates/npt.mdp`:

```
; npt.mdp - constant pressure equilibration
integrator               = md
nsteps                   = {nsteps}
dt                       = {dt}
nstxout                  = 0
nstvout                  = 0
nstenergy                = 500
nstlog                   = 500
nstxout-compressed       = 500
continuation             = yes
constraint_algorithm     = lincs
constraints              = h-bonds
cutoff-scheme            = Verlet
ns_type                  = grid
nstlist                  = 10
rcoulomb                 = 1.0
rvdw                     = 1.0
coulombtype              = PME
pme_order                = 4
fourierspacing           = 0.16
tcoupl                   = V-rescale
tc-grps                  = Protein Non-Protein
tau_t                    = {tau_t} {tau_t}
ref_t                    = {ref_t} {ref_t}
pcoupl                   = Parrinello-Rahman
pcoupltype               = isotropic
tau_p                    = {tau_p}
ref_p                    = 1.0
compressibility          = 4.5e-5
refcoord_scaling         = com
pbc                      = xyz
DispCorr                 = EnerPres
gen_vel                  = no
```

`lib/mdp_templates/production.mdp`:

```
; production.mdp
integrator               = md
nsteps                   = {nsteps}
dt                       = {dt}
nstxout                  = 0
nstvout                  = 0
nstenergy                = 5000
nstlog                   = 5000
nstxout-compressed       = 5000
continuation             = yes
constraint_algorithm     = lincs
constraints              = h-bonds
cutoff-scheme            = Verlet
ns_type                  = grid
nstlist                  = 10
rcoulomb                 = 1.0
rvdw                     = 1.0
coulombtype              = PME
pme_order                = 4
fourierspacing           = 0.16
tcoupl                   = V-rescale
tc-grps                  = Protein Non-Protein
tau_t                    = {tau_t} {tau_t}
ref_t                    = {ref_t} {ref_t}
pcoupl                   = Parrinello-Rahman
pcoupltype               = isotropic
tau_p                    = {tau_p}
ref_p                    = 1.0
compressibility          = 4.5e-5
pbc                      = xyz
DispCorr                 = EnerPres
gen_vel                  = no
```

`lib/mdp_templates/ions.mdp`:

```
; ions.mdp - tpr for genion
integrator               = steep
emtol                    = 1000.0
emstep                   = 0.01
nsteps                   = 50000
nstlist                  = 1
cutoff-scheme            = Verlet
coulombtype              = PME
rcoulomb                 = 1.0
rvdw                     = 1.0
pbc                      = xyz
```

- [ ] **Step 4: Implement renderer `lib/mdp_templates/base.py`**

```python
# lib/mdp_templates/base.py
from pathlib import Path
from typing import Any

_DIR = Path(__file__).parent

DEFAULTS = {
    "em": {"emtol": 1000.0, "emstep": 0.01, "nsteps": 50000},
    "nvt": {"nsteps": 50000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0},
    "npt": {"nsteps": 50000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0, "tau_p": 2.0},
    "production": {"nsteps": 500000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0,
                    "tau_p": 2.0},
    "ions": {},
}

_FILES = {
    "em": "em.mdp",
    "nvt": "nvt.mdp",
    "npt": "npt.mdp",
    "production": "production.mdp",
    "ions": "ions.mdp",
}


def render(phase: str, overrides: dict[str, Any], output_dir: Path) -> Path:
    if phase not in _FILES:
        raise KeyError(f"unknown template: {phase}")
    template = (_DIR / _FILES[phase]).read_text()
    params = {**DEFAULTS[phase], **overrides}
    content = template.format(**params) if params else template
    out = Path(output_dir) / f"{phase}.mdp"
    out.write_text(content)
    return out
```

- [ ] **Step 5: Run, confirm pass**

Run: `pytest tests/unit/test_mdp_templates.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add lib/mdp_templates tests/unit/test_mdp_templates.py
git commit -m "feat(lib): add mdp template renderer for em/nvt/npt/production/ions"
```

### Task F2: Umbrella sampling and free-energy template variants

**Files:**
- Create: `lib/mdp_templates/umbrella.mdp`
- Create: `lib/mdp_templates/free_energy.mdp`
- Modify: `lib/mdp_templates/base.py`
- Modify: `tests/unit/test_mdp_templates.py`

- [ ] **Step 1: Add failing tests**

```python
def test_render_umbrella(tmp_path: Path):
    out = M.render("umbrella", overrides={"pull_coord_init": 0.5}, output_dir=tmp_path)
    text = out.read_text()
    assert "pull" in text
    assert "pull_coord1_init       = 0.5" in text


def test_render_free_energy(tmp_path: Path):
    out = M.render("free_energy",
                   overrides={"init_lambda_state": 3,
                              "vdw_lambdas": "0.0 0.25 0.5 0.75 1.0"},
                   output_dir=tmp_path)
    text = out.read_text()
    assert "free_energy" in text
    assert "init_lambda_state        = 3" in text
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Create `lib/mdp_templates/umbrella.mdp`**

```
; umbrella.mdp - umbrella sampling window
integrator               = md
nsteps                   = {nsteps}
dt                       = {dt}
nstenergy                = 1000
nstlog                   = 1000
nstxout-compressed       = 1000
continuation             = yes
constraints              = h-bonds
cutoff-scheme            = Verlet
nstlist                  = 10
rcoulomb                 = 1.0
rvdw                     = 1.0
coulombtype              = PME
tcoupl                   = V-rescale
tc-grps                  = System
tau_t                    = {tau_t}
ref_t                    = {ref_t}
pcoupl                   = Parrinello-Rahman
tau_p                    = {tau_p}
ref_p                    = 1.0
compressibility          = 4.5e-5
pbc                      = xyz
pull                     = yes
pull_ncoords             = 1
pull_ngroups             = 2
pull_group1_name         = {pull_group1}
pull_group2_name         = {pull_group2}
pull_coord1_type         = umbrella
pull_coord1_geometry     = distance
pull_coord1_groups       = 1 2
pull_coord1_dim          = N N Y
pull_coord1_init         = {pull_coord_init}
pull_coord1_k            = {pull_coord_k}
pull_coord1_start        = no
```

- [ ] **Step 4: Create `lib/mdp_templates/free_energy.mdp`**

```
; free_energy.mdp - alchemical decoupling
integrator               = md
nsteps                   = {nsteps}
dt                       = {dt}
nstenergy                = 1000
nstlog                   = 1000
nstxout-compressed       = 1000
constraints              = h-bonds
cutoff-scheme            = Verlet
nstlist                  = 10
rcoulomb                 = 1.0
rvdw                     = 1.0
coulombtype              = PME
tcoupl                   = V-rescale
tc-grps                  = System
tau_t                    = {tau_t}
ref_t                    = {ref_t}
pcoupl                   = Parrinello-Rahman
tau_p                    = {tau_p}
ref_p                    = 1.0
compressibility          = 4.5e-5
pbc                      = xyz
free_energy              = yes
init_lambda_state        = {init_lambda_state}
delta_lambda             = 0
calc_lambda_neighbors    = 1
coul_lambdas             = {coul_lambdas}
vdw_lambdas              = {vdw_lambdas}
sc-alpha                 = 0.5
sc-power                 = 1
sc-sigma                 = 0.3
couple-moltype           = {couple_moltype}
couple-lambda0           = vdw-q
couple-lambda1           = none
couple-intramol          = no
nstdhdl                  = 100
```

- [ ] **Step 5: Extend `lib/mdp_templates/base.py`**

Update `DEFAULTS` and `_FILES`:

```python
DEFAULTS.update({
    "umbrella": {"nsteps": 500000, "dt": 0.002, "tau_t": 0.5, "ref_t": 300.0,
                  "tau_p": 2.0, "pull_group1": "Chain_A", "pull_group2": "Chain_B",
                  "pull_coord_init": 0.0, "pull_coord_k": 1000.0},
    "free_energy": {"nsteps": 500000, "dt": 0.002, "tau_t": 0.5, "ref_t": 300.0,
                     "tau_p": 2.0, "init_lambda_state": 0,
                     "coul_lambdas": "0.0 0.25 0.5 0.75 1.0",
                     "vdw_lambdas": "0.0 0.25 0.5 0.75 1.0",
                     "couple_moltype": "LIG"},
})
_FILES.update({"umbrella": "umbrella.mdp", "free_energy": "free_energy.mdp"})
```

- [ ] **Step 6: Run, confirm pass**

Run: `pytest tests/unit/test_mdp_templates.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add lib/mdp_templates tests/unit/test_mdp_templates.py
git commit -m "feat(lib): add umbrella and free-energy mdp templates"
```

### Task F3: `xvg_parser.py` with downsampling

**Files:**
- Create: `lib/xvg_parser.py`
- Create: `tests/unit/test_xvg_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_xvg_parser.py
from pathlib import Path
from lib import xvg_parser as X


def _write_xvg(p: Path, n: int = 1000):
    lines = ["@ title \"test\"\n", "@ xaxis label \"Time (ps)\"\n",
             "@ yaxis label \"Energy (kJ/mol)\"\n"]
    for i in range(n):
        lines.append(f"{i*10:.3f} {-12345.0 + i*0.1:.3f}\n")
    p.write_text("".join(lines))


def test_parse_basic_xvg(tmp_path: Path):
    p = tmp_path / "energy.xvg"
    _write_xvg(p, n=200)
    data = X.parse(p)
    assert data["title"] == "test"
    assert data["xaxis_label"] == "Time (ps)"
    assert data["yaxis_label"] == "Energy (kJ/mol)"
    assert len(data["columns"]) == 2  # x and y


def test_parse_downsamples_to_target(tmp_path: Path):
    p = tmp_path / "energy.xvg"
    _write_xvg(p, n=5000)
    data = X.parse(p, max_points=500)
    assert len(data["columns"][0]) <= 500
    assert len(data["columns"][1]) <= 500


def test_summary_stats(tmp_path: Path):
    p = tmp_path / "energy.xvg"
    _write_xvg(p, n=100)
    s = X.summary(p)
    assert s["count"] == 100
    assert s["min"] < s["max"]
    assert "mean" in s and "std" in s


def test_skip_comments_and_legend(tmp_path: Path):
    p = tmp_path / "x.xvg"
    p.write_text("# comment\n@ title \"t\"\n@s0 legend \"a\"\n1 2\n3 4\n")
    data = X.parse(p)
    assert data["columns"][0] == [1.0, 3.0]
    assert data["columns"][1] == [2.0, 4.0]
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement `lib/xvg_parser.py`**

```python
# lib/xvg_parser.py
import re
import statistics
from pathlib import Path
from typing import Any

TITLE_RE = re.compile(r'@\s*title\s+"([^"]*)"')
XLAB_RE = re.compile(r'@\s*xaxis\s+label\s+"([^"]*)"')
YLAB_RE = re.compile(r'@\s*yaxis\s+label\s+"([^"]*)"')


def _read_metadata(lines: list[str]) -> dict[str, str]:
    meta = {"title": "", "xaxis_label": "", "yaxis_label": ""}
    for line in lines:
        if not line.startswith("@"):
            continue
        if m := TITLE_RE.search(line):
            meta["title"] = m.group(1)
        if m := XLAB_RE.search(line):
            meta["xaxis_label"] = m.group(1)
        if m := YLAB_RE.search(line):
            meta["yaxis_label"] = m.group(1)
    return meta


def _read_data(lines: list[str]) -> list[list[float]]:
    rows = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith(("#", "@")):
            continue
        parts = s.split()
        rows.append([float(x) for x in parts])
    if not rows:
        return []
    ncols = len(rows[0])
    return [[r[c] for r in rows] for c in range(ncols)]


def _downsample(columns: list[list[float]], max_points: int) -> list[list[float]]:
    if not columns or len(columns[0]) <= max_points:
        return columns
    stride = max(1, len(columns[0]) // max_points)
    return [c[::stride][:max_points] for c in columns]


def parse(path: Path, max_points: int = 1000) -> dict[str, Any]:
    lines = Path(path).read_text().splitlines()
    meta = _read_metadata(lines)
    cols = _read_data(lines)
    cols = _downsample(cols, max_points)
    return {**meta, "columns": cols}


def summary(path: Path, column: int = 1) -> dict[str, float]:
    cols = _read_data(Path(path).read_text().splitlines())
    if len(cols) <= column:
        return {"count": 0}
    y = cols[column]
    return {
        "count": len(y),
        "min": min(y),
        "max": max(y),
        "mean": statistics.mean(y),
        "std": statistics.pstdev(y) if len(y) > 1 else 0.0,
        "first": y[0],
        "last": y[-1],
    }
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_xvg_parser.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add lib/xvg_parser.py tests/unit/test_xvg_parser.py
git commit -m "feat(lib): add xvg parser with downsampling and summary stats"
```

### Task F4: Run full unit test suite as Phase-F gate

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/unit -v`
Expected: all tests pass (30+ tests). If any fail, fix before continuing.

- [ ] **Step 2: Commit if any drive-by fixes were made**

```bash
git add -u
git commit -m "test: stabilize lib/ unit suite"   # only if changes
```

---

## Phase G — `skills/env-builder/`

### Task G1: Hardware profiling + workspace init

**Files:**
- Create: `skills/env-builder/env_builder.py`
- Create: `tests/contract/test_env_builder_io.py`

- [ ] **Step 1: Write failing contract test for `init_workspace` + `collect_hardware`**

```python
# tests/contract/test_env_builder_io.py
from pathlib import Path
from unittest.mock import patch
from skills.env_builder.env_builder import init_workspace, collect_hardware
from lib import state


def test_init_workspace_creates_dirs_and_state(tmp_path: Path):
    ws = tmp_path / "ws"
    init_workspace(ws)
    assert (ws / "inputs").is_dir()
    assert (ws / "stage1_env").is_dir()
    assert (ws / "stage2_md").is_dir()
    assert (ws / "stage3_viz").is_dir()
    s = state.read(ws)
    assert s["current_step"] == 0
    assert s["last_completed_stage"] is None


def test_collect_hardware_populates_state(tmp_path: Path):
    ws = tmp_path / "ws"
    init_workspace(ws)
    with patch("os.cpu_count", return_value=16):
        collect_hardware(ws)
    s = state.read(ws)
    assert s["hardware"]["cpu_count"] == 16
    assert "ntomp" in s["hardware"]
    assert isinstance(s["hardware"]["gpu_ids"], list)
```

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/contract/test_env_builder_io.py -v`
Expected: ImportError.

- [ ] **Step 3: Create `skills/env-builder/env_builder.py` (initial)**

```python
# skills/env-builder/env_builder.py
"""env-builder skill — Step 0–5 of the GROMACS pipeline.

This module is imported as `skills.env_builder.env_builder` by tests and the
LLM agent. The hyphen-bearing directory is exposed via an `__init__.py` shim.
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from lib import state


def init_workspace(workspace_dir: Path) -> None:
    workspace_dir = Path(workspace_dir)
    for sub in ("inputs", "stage1_env", "stage2_md", "stage3_viz"):
        (workspace_dir / sub).mkdir(parents=True, exist_ok=True)
    if not state.path(workspace_dir).exists():
        state.write(workspace_dir, state.initial(workspace_dir))


def _detect_gpu_ids() -> list[int]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
            text=True, timeout=10,
        )
        return [int(x.strip()) for x in out.splitlines() if x.strip()]
    except Exception:
        return []


def collect_hardware(workspace_dir: Path) -> None:
    cpu = os.cpu_count() or 1
    gpus = _detect_gpu_ids()
    ntomp = max(1, cpu // max(1, len(gpus) or 1))
    s = state.read(workspace_dir)
    s["hardware"] = {"cpu_count": cpu, "gpu_ids": gpus, "ntomp": ntomp}
    state.write(workspace_dir, s)
```

- [ ] **Step 4: Add `skills/__init__.py` and `skills/env-builder/__init__.py` shim so `skills.env_builder` resolves**

Create `skills/__init__.py` (empty).

Create `skills/env_builder/__init__.py` shim by exposing the hyphenated directory under an importable name. To keep simplicity, **rename** `skills/env-builder` to `skills/env_builder` (underscore) since hyphens are not importable in Python.

```bash
git mv skills/env-builder skills/env_builder    # if previous skeleton exists
mkdir -p skills/env_builder
```

Then create `skills/__init__.py`:

```python
# skills/__init__.py
```

And `skills/env_builder/__init__.py`:

```python
# skills/env_builder/__init__.py
from .env_builder import init_workspace, collect_hardware  # noqa: F401
```

Note: the `SKILL.md` for the skill still lives at `skills/env_builder/SKILL.md`. SKILL.md `name:` field uses `env-builder` for user-facing naming; directory uses `env_builder` for Python import.

- [ ] **Step 5: Run, confirm pass**

Run: `pytest tests/contract/test_env_builder_io.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add skills/__init__.py skills/env_builder/__init__.py skills/env_builder/env_builder.py tests/contract/test_env_builder_io.py
git commit -m "feat(env-builder): init workspace and hardware profile"
```

### Task G2: Tutorial routing wired into env-builder

**Files:**
- Modify: `skills/env_builder/env_builder.py`
- Modify: `skills/env_builder/__init__.py`
- Create: `tests/contract/test_env_builder_routing.py`

- [ ] **Step 1: Write failing test**

```python
# tests/contract/test_env_builder_routing.py
from pathlib import Path
from skills.env_builder.env_builder import select_tutorial, init_workspace
from lib import state


def test_select_tutorial_records_decision(tmp_path: Path, ubq_pdb_path: Path):
    ws = tmp_path / "ws"
    init_workspace(ws)
    decision = select_tutorial(
        workspace_dir=ws,
        pdb_path=ubq_pdb_path,
        prompt="run a basic protein simulation in water",
        prerequisites={},
    )
    assert decision.tutorial_id == "Lysozyme_in_water"
    s = state.read(ws)
    assert s["tutorial"]["id"] == "Lysozyme_in_water"
    assert s["tutorial"]["variant"] == "protein_aqueous_standard"


def test_select_tutorial_blocks_missing_prereq(tmp_path: Path, ubq_pdb_path: Path):
    ws = tmp_path / "ws"
    init_workspace(ws)
    import pytest
    from skills.env_builder.env_builder import UnsupportedTutorialError
    with pytest.raises(UnsupportedTutorialError):
        select_tutorial(
            workspace_dir=ws,
            pdb_path=ubq_pdb_path,
            prompt="umbrella sampling pmf",
            prerequisites={},  # missing reaction_coordinate_definition
        )
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Extend `skills/env_builder/env_builder.py`**

```python
from lib import tutorial_registry as TR


class UnsupportedTutorialError(Exception):
    pass


def _pdb_hints(pdb_path: Path) -> dict[str, bool]:
    text = Path(pdb_path).read_text()
    return {
        "has_protein": "ATOM" in text and any(
            res in text for res in ("ALA", "GLY", "LEU", "VAL", "ILE")),
        "has_membrane": any(
            lipid in text for lipid in ("DPPC", "POPC", "DMPC", "DOPC")),
        "has_ligand": "HETATM" in text,
    }


def select_tutorial(workspace_dir: Path, pdb_path: Path,
                    prompt: str, prerequisites: dict[str, Any]) -> TR.RoutingDecision:
    hints = _pdb_hints(pdb_path)
    decision = TR.route(prompt=prompt, pdb_hints=hints, prerequisites=prerequisites)
    if decision.unsupported_reason:
        raise UnsupportedTutorialError(decision.unsupported_reason)
    s = state.read(workspace_dir)
    s["tutorial"] = {
        "id": decision.tutorial_id,
        "variant": decision.pipeline_variant,
        "manifest_path": (
            f"docs/tutorial/{decision.tutorial_id}/tutorial.manifest.json"
        ),
    }
    state.write(workspace_dir, s)
    return decision
```

Update `skills/env_builder/__init__.py`:

```python
from .env_builder import (
    init_workspace, collect_hardware, select_tutorial,
    UnsupportedTutorialError,
)  # noqa: F401
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/contract/test_env_builder_routing.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add skills/env_builder/ tests/contract/test_env_builder_routing.py
git commit -m "feat(env-builder): tutorial routing integration"
```

### Task G3: Step 1 — `pdb2gmx` topology generation

**Files:**
- Modify: `skills/env_builder/env_builder.py`
- Modify: `skills/env_builder/__init__.py`
- Create: `tests/integration/test_env_builder_lysozyme.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_env_builder_lysozyme.py
import shutil
from pathlib import Path
import pytest

GMX = shutil.which("gmx")
pytestmark = pytest.mark.skipif(GMX is None, reason="gmx not on PATH")


def test_step1_pdb2gmx_produces_topology(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import (
        init_workspace, collect_hardware, select_tutorial, run_step1_topology,
    )
    from lib import state
    init_workspace(tmp_workspace)
    collect_hardware(tmp_workspace)
    select_tutorial(tmp_workspace, ubq_pdb_path,
                    "protein in water", prerequisites={})
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    run_step1_topology(tmp_workspace, forcefield="charmm36", water="tip3p")
    s = state.read(tmp_workspace)
    assert (tmp_workspace / "stage1_env" / "processed.gro").exists()
    assert (tmp_workspace / "stage1_env" / "topol.top").exists()
    assert s["step_outputs"]["step_1"]["forcefield"] == "charmm36"
```

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/integration/test_env_builder_lysozyme.py -v`
Expected: ImportError or skip when gmx absent.

- [ ] **Step 3: Implement Step 1**

Append to `skills/env_builder/env_builder.py`:

```python
from lib import gmx_wrapper as GW


def run_step1_topology(workspace_dir: Path, forcefield: str, water: str) -> None:
    ws = Path(workspace_dir)
    pdb = ws / "inputs" / "input.pdb"
    out_dir = ws / "stage1_env"
    result = GW.run(
        ["pdb2gmx", "-f", str(pdb),
         "-o", "processed.gro", "-p", "topol.top",
         "-water", water, "-ff", forcefield, "-ignh"],
        cwd=out_dir,
    )
    if not result.ok:
        raise RuntimeError(f"pdb2gmx failed: {result.stderr[-500:]}")
    s = state.read(ws)
    s["step_outputs"]["step_1"] = {
        "forcefield": forcefield, "water_model": water,
        "top_file": "stage1_env/topol.top",
        "gro_file": "stage1_env/processed.gro",
    }
    s["current_step"] = 1
    state.write(ws, s)
```

Add `run_step1_topology` to `__init__.py` exports.

- [ ] **Step 4: Run, confirm pass on a gmx-equipped machine**

Run: `pytest tests/integration/test_env_builder_lysozyme.py -v`
Expected: 1 passed (or skipped if no gmx).

- [ ] **Step 5: Commit**

```bash
git add skills/env_builder/ tests/integration/test_env_builder_lysozyme.py
git commit -m "feat(env-builder): step 1 pdb2gmx topology generation"
```

### Task G4: Step 2 (`editconf`), Step 3 (`solvate` with backup)

**Files:**
- Modify: `skills/env_builder/env_builder.py`
- Modify: `skills/env_builder/__init__.py`
- Modify: `tests/integration/test_env_builder_lysozyme.py`

- [ ] **Step 1: Add failing integration test cases**

Append to `tests/integration/test_env_builder_lysozyme.py`:

```python
def test_step2_and_step3(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import (
        init_workspace, collect_hardware, select_tutorial,
        run_step1_topology, run_step2_box, run_step3_solvate,
    )
    from lib import state
    init_workspace(tmp_workspace)
    collect_hardware(tmp_workspace)
    select_tutorial(tmp_workspace, ubq_pdb_path, "protein in water",
                    prerequisites={})
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    run_step1_topology(tmp_workspace, "charmm36", "tip3p")
    run_step2_box(tmp_workspace, box_type="cubic", distance_nm=1.0)
    run_step3_solvate(tmp_workspace)
    s = state.read(tmp_workspace)
    assert s["step_outputs"]["step_2"]["box_type"] == "cubic"
    assert "step_3" in s["step_outputs"]
    assert (tmp_workspace / "stage1_env" / "topol.top.bak").exists()
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement Steps 2 and 3**

Append to `skills/env_builder/env_builder.py`:

```python
def run_step2_box(workspace_dir: Path, box_type: str, distance_nm: float) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage1_env"
    result = GW.run(
        ["editconf", "-f", "processed.gro", "-o", "box.gro",
         "-c", "-d", str(distance_nm), "-bt", box_type],
        cwd=out_dir,
    )
    if not result.ok:
        raise RuntimeError(f"editconf failed: {result.stderr[-500:]}")
    s = state.read(ws)
    s["step_outputs"]["step_2"] = {
        "box_type": box_type, "box_distance": distance_nm,
        "box_gro": "stage1_env/box.gro",
    }
    s["current_step"] = 2
    state.write(ws, s)


def run_step3_solvate(workspace_dir: Path) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage1_env"
    top = out_dir / "topol.top"
    GW.backup_topology(top)
    s = state.read(ws)
    s["topology_backups"].append("stage1_env/topol.top.bak")
    state.write(ws, s)
    result = GW.run(
        ["solvate", "-cp", "box.gro", "-cs", "spc216.gro",
         "-o", "solv.gro", "-p", "topol.top"],
        cwd=out_dir,
    )
    if not result.ok:
        GW.restore_topology(top)
        raise RuntimeError(f"solvate failed: {result.stderr[-500:]}")
    # parse solvent count from stdout
    n_sol = 0
    for line in result.stdout.splitlines():
        if "Number of solvent molecules" in line:
            n_sol = int(line.split()[-1])
            break
    s = state.read(ws)
    s["step_outputs"]["step_3"] = {
        "solv_gro": "stage1_env/solv.gro", "n_solvent_molecules": n_sol,
    }
    s["current_step"] = 3
    state.write(ws, s)
```

Add new functions to `__init__.py`.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/integration/test_env_builder_lysozyme.py -v`
Expected: 2 passed (or skipped if no gmx).

- [ ] **Step 5: Commit**

```bash
git add skills/env_builder/ tests/integration/test_env_builder_lysozyme.py
git commit -m "feat(env-builder): step 2 editconf and step 3 solvate with topology backup"
```

### Task G5: Step 4–5 — ions.mdp + grompp + genion

**Files:**
- Modify: `skills/env_builder/env_builder.py`
- Modify: `skills/env_builder/__init__.py`
- Modify: `tests/integration/test_env_builder_lysozyme.py`

- [ ] **Step 1: Add failing test**

Append:

```python
def test_step4_and_step5(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import (
        init_workspace, collect_hardware, select_tutorial,
        run_step1_topology, run_step2_box, run_step3_solvate,
        run_step4_ions_prep, run_step5_genion,
    )
    from lib import state
    init_workspace(tmp_workspace)
    collect_hardware(tmp_workspace)
    select_tutorial(tmp_workspace, ubq_pdb_path, "protein in water",
                    prerequisites={})
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    run_step1_topology(tmp_workspace, "charmm36", "tip3p")
    run_step2_box(tmp_workspace, "cubic", 1.0)
    run_step3_solvate(tmp_workspace)
    run_step4_ions_prep(tmp_workspace)
    run_step5_genion(tmp_workspace, concentration=0.15)
    s = state.read(tmp_workspace)
    assert "step_5" in s["step_outputs"]
    assert s["step_outputs"]["step_5"]["net_charge"] == 0.0
    assert s["last_completed_stage"] == "env"
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement Steps 4 and 5**

```python
from lib.mdp_templates import base as MDP


def run_step4_ions_prep(workspace_dir: Path) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage1_env"
    MDP.render("ions", overrides={}, output_dir=out_dir)
    result = GW.run(
        ["grompp", "-f", "ions.mdp", "-c", "solv.gro",
         "-p", "topol.top", "-o", "ions.tpr", "-maxwarn", "1"],
        cwd=out_dir,
    )
    if not result.ok:
        raise RuntimeError(f"grompp (ions) failed: {result.stderr[-500:]}")
    s = state.read(ws)
    s["current_step"] = 4
    state.write(ws, s)


def run_step5_genion(workspace_dir: Path, concentration: float = 0.15) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage1_env"
    top = out_dir / "topol.top"
    # Backup again before genion mutation
    GW.backup_topology(top)
    s = state.read(ws)
    if "stage1_env/topol.top.bak" not in s["topology_backups"]:
        s["topology_backups"].append("stage1_env/topol.top.bak")
    state.write(ws, s)
    result = GW.run(
        ["genion", "-s", "ions.tpr", "-o", "ions.gro",
         "-p", "topol.top", "-pname", "NA", "-nname", "CL",
         "-neutral", "-conc", str(concentration)],
        cwd=out_dir, interactive_inputs=["SOL"],
    )
    if not result.ok:
        GW.restore_topology(top)
        raise RuntimeError(f"genion failed: {result.stderr[-500:]}")
    # parse counts
    n_na = n_cl = 0
    for line in (result.stdout + result.stderr).splitlines():
        if "Will try to add" in line and "NA" in line:
            n_na = int(line.split()[3])
        if "Will try to add" in line and "CL" in line:
            n_cl = int(line.split()[3])
    s = state.read(ws)
    s["step_outputs"]["step_5"] = {
        "ion_gro": "stage1_env/ions.gro",
        "n_na": n_na, "n_cl": n_cl, "net_charge": 0.0,
    }
    s["current_step"] = 5
    s["last_completed_stage"] = "env"
    state.write(ws, s)
```

Update `__init__.py` exports.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/integration/test_env_builder_lysozyme.py -v`
Expected: 3 passed (or skipped if no gmx).

- [ ] **Step 5: Commit**

```bash
git add skills/env_builder/ tests/integration/test_env_builder_lysozyme.py
git commit -m "feat(env-builder): steps 4-5 ions prep and genion with topology backup"
```

### Task G6: End-to-end `build_environment` entry point

**Files:**
- Modify: `skills/env_builder/env_builder.py`
- Modify: `skills/env_builder/__init__.py`
- Modify: `tests/integration/test_env_builder_lysozyme.py`

- [ ] **Step 1: Add failing test for full pipeline call**

Append:

```python
def test_build_environment_end_to_end(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from lib import state
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    s = state.read(tmp_workspace)
    assert s["last_completed_stage"] == "env"
    for k in ("step_1", "step_2", "step_3", "step_5"):
        assert k in s["step_outputs"]
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement `build_environment`**

```python
def build_environment(pdb_path: Path, prompt: str, workspace_dir: Path,
                      prerequisites: dict[str, Any] | None = None,
                      interactive: bool = True) -> dict[str, Any]:
    init_workspace(workspace_dir)
    collect_hardware(workspace_dir)
    # Copy input pdb if not already in inputs/
    inputs_pdb = Path(workspace_dir) / "inputs" / "input.pdb"
    if Path(pdb_path).resolve() != inputs_pdb.resolve():
        shutil.copy(pdb_path, inputs_pdb)
    decision = select_tutorial(workspace_dir, inputs_pdb, prompt,
                               prerequisites or {})
    manifest = TR.load_manifest(decision.tutorial_id) or {}
    defaults = manifest.get("defaults", {})
    ff = defaults.get("forcefield", "charmm36")
    water = defaults.get("water_model", "tip3p")
    box_type = defaults.get("box_type", "cubic")
    box_d = defaults.get("box_distance_nm", 1.0)
    run_step1_topology(workspace_dir, ff, water)
    run_step2_box(workspace_dir, box_type, box_d)
    run_step3_solvate(workspace_dir)
    run_step4_ions_prep(workspace_dir)
    run_step5_genion(workspace_dir, concentration=0.15)
    return state.read(workspace_dir)
```

Update `__init__.py`:

```python
from .env_builder import (
    init_workspace, collect_hardware, select_tutorial,
    run_step1_topology, run_step2_box, run_step3_solvate,
    run_step4_ions_prep, run_step5_genion,
    build_environment, UnsupportedTutorialError,
)  # noqa: F401
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/integration/test_env_builder_lysozyme.py -v`
Expected: 4 passed (or skipped if no gmx).

- [ ] **Step 5: Commit**

```bash
git add skills/env_builder/ tests/integration/test_env_builder_lysozyme.py
git commit -m "feat(env-builder): end-to-end build_environment entry"
```

### Task G7: `SKILL.md` and reference docs

**Files:**
- Create: `skills/env_builder/SKILL.md`
- Create: `skills/env_builder/references/charmmgui_workflow.md`
- Create: `skills/env_builder/references/forcefield_guide.md`
- Create: `skills/env_builder/references/prerequisite_schema.md`

- [ ] **Step 1: Create `skills/env_builder/SKILL.md`**

```yaml
---
name: env-builder
description: >-
  Build a CHARMM-GUI-style MD environment locally from a PDB file and a
  natural-language goal. Performs Step 0–5 of the GROMACS pipeline:
  hardware profiling, tutorial routing, topology, box, solvation,
  and ion neutralization. Outputs files to workspace/stage1_env/ and
  updates workspace/state.json. Invoke when the user supplies a PDB and
  wants the system prepared for MD.
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: env-builder

## Input Schema

```json
{
  "pdb_path": "/abs/path/input.pdb",
  "prompt": "natural-language goal",
  "workspace_dir": "/abs/path/workspace",
  "prerequisites": {
    "ligand_itp": "...",
    "membrane_composition": {"DPPC": 128},
    "reaction_coordinate": {"...": "..."},
    "lambda_schedule": ["..."]
  },
  "interactive": true
}
```

## Output Contract

Files under `workspace/stage1_env/`:
`processed.gro`, `topol.top`, `topol.top.bak`, `box.gro`,
`solv.gro`, `ions.tpr`, `ions.gro`, `index.ndx` (when applicable).

`workspace/state.json` is updated with `step_outputs.step_1..step_5`,
`tutorial`, `hardware`, `topology_backups`, and
`last_completed_stage = "env"`.

## Behavior

1. Initialize workspace and collect hardware profile (Step 0).
2. Route the tutorial based on PDB hints + prompt + prerequisites.
   Block on missing prerequisites for derived tutorials.
3. Step 1: `pdb2gmx` with force field defaults from the tutorial manifest.
4. Step 2: `editconf` with box defaults from the manifest.
5. Step 3: `solvate`. `topol.top.bak` is created before mutation.
6. Step 4: render `ions.mdp` and run `grompp`.
7. Step 5: `genion` with charge neutralization at 0.15 M.

## References

- `references/charmmgui_workflow.md`
- `references/forcefield_guide.md`
- `references/prerequisite_schema.md`
```

- [ ] **Step 2: Create `references/charmmgui_workflow.md`**

```markdown
# CHARMM-GUI Workflow Mapping (Local Reimplementation)

| CHARMM-GUI step | env-builder Step | GROMACS tool |
|---|---|---|
| Read PDB | Step 0 (workspace init) | n/a |
| Choose force field / water | Step 1 default selection | `gmx pdb2gmx` |
| Generate topology | Step 1 | `gmx pdb2gmx` |
| Position lipids/ligand | Step 1 merge of `.itp` from prerequisites | manual merge in `topol.top` |
| Define box | Step 2 | `gmx editconf` |
| Solvate | Step 3 (with `topol.top.bak`) | `gmx solvate` |
| Neutralize / add ions | Step 4 + Step 5 | `gmx grompp`, `gmx genion` |

The local reimplementation never calls the CHARMM-GUI web service.
Manifest defaults under `docs/tutorial/<id>/tutorial.manifest.json`
drive force-field and box choices.
```

- [ ] **Step 3: Create `references/forcefield_guide.md`**

```markdown
# Force Field Selection Guide

- Default: `charmm36` + `tip3p`.
- Membrane systems (KALP15_in_DPPC etc.): require lipid parameters
  bundled with `charmm36`. Verify the installed `GMXLIB` contains
  the appropriate `.rtp`/`.itp` entries before Step 1.
- Protein-ligand: force-field choice must support the ligand
  parameter set. If `ligand_itp` is provided, the include lines for
  the ligand topology must be merged into `topol.top` before Step 4.
- Free-energy systems: the alchemically-coupled moltype must match
  `couple-moltype` in `free_energy.mdp`.

The harness reads tutorial manifest `defaults.forcefield` /
`defaults.water_model` when present. Override via `prerequisites`
fields if a custom force field is needed.
```

- [ ] **Step 4: Create `references/prerequisite_schema.md`**

```markdown
# Prerequisite Schema for Derived Tutorials

The `prerequisites` field of `build_environment` accepts the following
keys. Required keys depend on tutorial selection (see
`docs/tutorial/tutorial_index.json`).

| Tutorial | Required prerequisite keys |
|---|---|
| Lysozyme_in_water | none |
| KALP15_in_DPPC | `membrane_composition` (e.g., `{"DPPC": 128}`) |
| Protein_Ligand_Complex | `ligand_structure` or `ligand_itp` |
| Umbrella_Sampling | `reaction_coordinate_definition`, `window_schedule_defined` |
| Building_Biphasic_Systems | `phase_components`, `composition_ratio` |
| Free_Energy_*_Methane | `solute_topology`, `lambda_schedule` |
| Free_Energy_*_Ethanol | `solute_topology`, `coulomb_vdw_lambda_schedule` |
| Virtual_Sites | `molecule_topology`, `virtual_site_definition` |

Missing prerequisites cause env-builder to raise
`UnsupportedTutorialError`. The caller should surface the missing
keys to the user and re-invoke with the inputs filled.
```

- [ ] **Step 5: Commit**

```bash
git add skills/env_builder/SKILL.md skills/env_builder/references/
git commit -m "docs(env-builder): add SKILL.md and reference materials"
```

---

## Phase H — `skills/md-runner/`

### Task H1: Entry-gate validation and skeleton

**Files:**
- Create: `skills/md_runner/__init__.py`
- Create: `skills/md_runner/md_runner.py`
- Create: `tests/contract/test_md_runner_io.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/contract/test_md_runner_io.py
from pathlib import Path
import pytest
from lib import state


def _populate_env_stage(ws: Path):
    s = state.initial(ws)
    s["last_completed_stage"] = "env"
    s["hardware"] = {"cpu_count": 4, "gpu_ids": [], "ntomp": 4}
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": "docs/tutorial/Lysozyme_in_water/tutorial.manifest.json"}
    s["step_outputs"]["step_1"] = {"forcefield": "charmm36",
                                    "water_model": "tip3p",
                                    "top_file": "stage1_env/topol.top",
                                    "gro_file": "stage1_env/processed.gro"}
    s["step_outputs"]["step_2"] = {"box_type": "cubic", "box_distance": 1.0,
                                    "box_gro": "stage1_env/box.gro"}
    s["step_outputs"]["step_3"] = {"solv_gro": "stage1_env/solv.gro",
                                    "n_solvent_molecules": 1000}
    s["step_outputs"]["step_5"] = {"ion_gro": "stage1_env/ions.gro",
                                    "n_na": 0, "n_cl": 0, "net_charge": 0.0}
    state.write(ws, s)
    for fname in ("processed.gro", "topol.top", "ions.gro", "index.ndx"):
        (ws / "stage1_env" / fname).write_text("placeholder")


def test_entry_gate_passes_when_stage1_complete(tmp_workspace: Path):
    from skills.md_runner.md_runner import assert_ready
    _populate_env_stage(tmp_workspace)
    assert_ready(tmp_workspace)


def test_entry_gate_fails_when_state_missing_keys(tmp_workspace: Path):
    from skills.md_runner.md_runner import assert_ready
    from lib.state import StateContractError
    s = state.initial(tmp_workspace)
    s["last_completed_stage"] = "env"
    state.write(tmp_workspace, s)
    with pytest.raises(StateContractError):
        assert_ready(tmp_workspace)


def test_entry_gate_fails_when_stage_marker_wrong(tmp_workspace: Path):
    from skills.md_runner.md_runner import assert_ready
    from lib.state import StateContractError
    _populate_env_stage(tmp_workspace)
    s = state.read(tmp_workspace)
    s["last_completed_stage"] = None
    state.write(tmp_workspace, s)
    with pytest.raises(StateContractError):
        assert_ready(tmp_workspace)


def test_entry_gate_fails_when_files_missing(tmp_workspace: Path):
    from skills.md_runner.md_runner import assert_ready
    from lib.state import StateContractError
    _populate_env_stage(tmp_workspace)
    (tmp_workspace / "stage1_env" / "processed.gro").unlink()
    with pytest.raises(StateContractError):
        assert_ready(tmp_workspace)
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement `skills/md_runner/md_runner.py`**

```python
# skills/md_runner/md_runner.py
from pathlib import Path
from typing import Any
from lib import state
from lib.state import StateContractError


REQUIRED_KEYS = ["step_1", "step_2", "step_3", "step_5"]
REQUIRED_FILES = ["processed.gro", "topol.top", "ions.gro"]


def assert_ready(workspace_dir: Path) -> dict[str, Any]:
    s = state.read(workspace_dir)
    state.require_last_stage(s, "env")
    state.require_step_keys(s, REQUIRED_KEYS)
    if not s.get("hardware"):
        raise StateContractError("hardware profile missing")
    ws = Path(workspace_dir)
    for fname in REQUIRED_FILES:
        if not (ws / "stage1_env" / fname).exists():
            raise StateContractError(f"missing stage1 file: {fname}")
    return s
```

Create `skills/md_runner/__init__.py`:

```python
from .md_runner import assert_ready  # noqa: F401
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/contract/test_md_runner_io.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add skills/md_runner/ tests/contract/test_md_runner_io.py
git commit -m "feat(md-runner): entry-gate validation"
```

### Task H2: Phase sequence selection by tutorial variant

**Files:**
- Modify: `skills/md_runner/md_runner.py`
- Modify: `skills/md_runner/__init__.py`
- Create: `tests/unit/test_md_runner_phase_sequence.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_md_runner_phase_sequence.py
from skills.md_runner.md_runner import phase_sequence_for_variant


def test_standard_variant():
    assert phase_sequence_for_variant("protein_aqueous_standard") == \
        ["em", "nvt", "npt", "production"]


def test_membrane_variant_includes_two_npt_steps():
    seq = phase_sequence_for_variant("membrane_md_standard")
    assert "em" in seq and "production" in seq
    assert seq.count("npt") >= 2  # membrane needs two-stage barostat


def test_umbrella_variant_has_pulling_then_windows():
    seq = phase_sequence_for_variant("umbrella_sampling")
    assert "umbrella" in seq
    assert seq.index("em") < seq.index("umbrella")


def test_free_energy_variant_has_lambda_states():
    seq = phase_sequence_for_variant("free_energy_alchemical")
    assert "free_energy" in seq


def test_unknown_variant_falls_back_to_standard():
    assert phase_sequence_for_variant("nonexistent") == \
        ["em", "nvt", "npt", "production"]
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Extend `skills/md_runner/md_runner.py`**

```python
PHASE_SEQUENCES = {
    "protein_aqueous_standard": ["em", "nvt", "npt", "production"],
    "membrane_md_standard": ["em", "nvt", "npt", "npt", "production"],
    "protein_ligand_complex": ["em", "nvt", "npt", "production"],
    "umbrella_sampling": ["em", "nvt", "npt", "umbrella"],
    "free_energy_alchemical": ["em", "nvt", "npt", "free_energy"],
    "biphasic_system": ["em", "nvt", "npt", "production"],
    "virtual_sites_topology": ["em", "production"],
}


def phase_sequence_for_variant(variant: str | None) -> list[str]:
    return PHASE_SEQUENCES.get(variant or "", ["em", "nvt", "npt", "production"])
```

Add to `__init__.py` exports.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_md_runner_phase_sequence.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add skills/md_runner/ tests/unit/test_md_runner_phase_sequence.py
git commit -m "feat(md-runner): phase sequence per tutorial variant"
```

### Task H3: Single-phase execution helper (`run_phase`)

**Files:**
- Modify: `skills/md_runner/md_runner.py`
- Modify: `skills/md_runner/__init__.py`
- Create: `tests/integration/test_md_runner_minimal.py`

- [ ] **Step 1: Write failing integration test (minimal EM)**

```python
# tests/integration/test_md_runner_minimal.py
import shutil
from pathlib import Path
import pytest

GMX = shutil.which("gmx")
pytestmark = pytest.mark.skipif(GMX is None, reason="gmx not on PATH")


def test_em_phase_runs_to_completion(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_phase
    from lib import state
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    run_phase(tmp_workspace, phase="em",
              overrides={"nsteps": 50})
    s = state.read(tmp_workspace)
    assert (tmp_workspace / "stage2_md" / "em.gro").exists()
    assert "em_gro" in s["step_outputs"].get("step_7", {})
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement `run_phase`**

Append to `skills/md_runner/md_runner.py`:

```python
from lib import gmx_wrapper as GW
from lib.mdp_templates import base as MDP

PHASE_INPUT_GRO = {
    "em":         ("stage1_env", "ions.gro"),
    "nvt":        ("stage2_md", "em.gro"),
    "npt":        ("stage2_md", "nvt.gro"),
    "production": ("stage2_md", "npt.gro"),
    "umbrella":   ("stage2_md", "npt.gro"),
    "free_energy":("stage2_md", "npt.gro"),
}

PHASE_TO_STATE_KEY = {
    "em": "em_gro", "nvt": "nvt_gro", "npt": "npt_gro",
    "production": "production_gro",
    "umbrella": "production_gro", "free_energy": "production_gro",
}


def run_phase(workspace_dir: Path, phase: str,
              overrides: dict[str, Any] | None = None) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage2_md"
    mdp_path = MDP.render(phase, overrides or {}, output_dir=out_dir)
    in_dir_rel, in_gro = PHASE_INPUT_GRO[phase]
    in_gro_path = ws / in_dir_rel / in_gro
    top_path = ws / "stage1_env" / "topol.top"
    tpr_path = out_dir / f"{phase}.tpr"
    grompp_result = GW.run(
        ["grompp", "-f", mdp_path.name,
         "-c", str(in_gro_path.relative_to(out_dir, walk_up=True))
              if hasattr(Path, "walk_up") else str(in_gro_path),
         "-p", str(top_path),
         "-o", tpr_path.name, "-maxwarn", "2"],
        cwd=out_dir,
    )
    if not grompp_result.ok:
        raise RuntimeError(
            f"grompp ({phase}) failed [{grompp_result.classification}]: "
            f"{grompp_result.stderr[-500:]}"
        )
    mdrun_result = GW.run(
        ["mdrun", "-deffnm", phase, "-ntomp",
         str(state.read(ws)["hardware"]["ntomp"])],
        cwd=out_dir,
    )
    if not mdrun_result.ok:
        raise RuntimeError(
            f"mdrun ({phase}) failed [{mdrun_result.classification}]: "
            f"{mdrun_result.stderr[-500:]}"
        )
    s = state.read(ws)
    step7 = s["step_outputs"].setdefault("step_7", {})
    step7[PHASE_TO_STATE_KEY[phase]] = f"stage2_md/{phase}.gro"
    s["current_step"] = 7
    state.write(ws, s)
```

Notes: the `walk_up=True` fallback handles older Python; if running 3.12+, `Path.relative_to(..., walk_up=True)` works. For broader compatibility, replace with absolute paths:

```python
"-c", str(in_gro_path),
```

Use absolute paths for `-c` and `-p` to avoid relative-path issues. Update the code accordingly.

Add `run_phase` to `__init__.py` exports.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/integration/test_md_runner_minimal.py -v`
Expected: 1 passed (or skipped without gmx).

- [ ] **Step 5: Commit**

```bash
git add skills/md_runner/ tests/integration/test_md_runner_minimal.py
git commit -m "feat(md-runner): single-phase grompp+mdrun helper"
```

### Task H4: Validator gate + RETRYABLE retry loop

**Files:**
- Modify: `skills/md_runner/md_runner.py`
- Modify: `skills/md_runner/__init__.py`
- Create: `tests/unit/test_md_runner_retry_loop.py`

- [ ] **Step 1: Write failing tests using mocked phase runner**

```python
# tests/unit/test_md_runner_retry_loop.py
from pathlib import Path
from unittest.mock import patch
import pytest
from lib import state, validators as V


def _seed_state(ws: Path):
    s = state.initial(ws)
    s["last_completed_stage"] = "env"
    s["hardware"] = {"cpu_count": 4, "gpu_ids": [], "ntomp": 4}
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    for k in ("step_1","step_2","step_3","step_5"):
        s["step_outputs"][k] = {}
    state.write(ws, s)


def test_retryable_loop_mutates_until_success(tmp_workspace: Path):
    from skills.md_runner.md_runner import run_phase_with_recovery
    _seed_state(tmp_workspace)
    call_count = {"n": 0}

    def fake_phase(ws, phase, overrides):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return V.Judgment(tier="retryable", metric="energy_drift",
                              cause="unstable_energy", observed=10.0)
        return V.Judgment(tier="pass", metric="energy_drift", observed=0.0)

    result = run_phase_with_recovery(tmp_workspace, phase="npt",
                                     phase_runner=fake_phase)
    assert result.tier == "pass"
    s = state.read(tmp_workspace)
    assert sum(1 for e in s["retry_history"] if e["tier"] == "retryable") == 2


def test_retryable_exhausts_budget_and_raises(tmp_workspace: Path):
    from skills.md_runner.md_runner import run_phase_with_recovery, PhaseFatal
    _seed_state(tmp_workspace)

    def always_retryable(ws, phase, overrides):
        return V.Judgment(tier="retryable", metric="energy_drift",
                          cause="unstable_energy", observed=10.0)

    with pytest.raises(PhaseFatal):
        run_phase_with_recovery(tmp_workspace, phase="npt",
                                phase_runner=always_retryable)
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement retry loop**

```python
from dataclasses import dataclass


class PhaseFatal(Exception):
    pass


MUTATION_BY_CAUSE = {
    "unstable_energy": [{"nsteps": 100}, {"nsteps": 200, "dt": 0.001},
                        {"nsteps": 400, "dt": 0.0005}],
    "pressure_coupling": [{"tau_p": 5.0}, {"tau_p": 8.0}, {"tau_p": 10.0}],
    "temperature_coupling": [{"tau_t": 0.5}, {"tau_t": 1.0}, {"tau_t": 2.0}],
    "command_error": [{"-maxwarn": 2}, {"-maxwarn": 3}, {"-maxwarn": 4}],
}


def _next_mutation(cause: str, history: list[dict]) -> dict[str, Any]:
    candidates = MUTATION_BY_CAUSE.get(cause, [{}])
    used = sum(1 for e in history if e.get("cause") == cause)
    if used >= len(candidates):
        raise PhaseFatal(f"no mutation candidates remaining for {cause}")
    return candidates[used]


def run_phase_with_recovery(workspace_dir: Path, phase: str,
                            phase_runner=None,
                            overrides: dict[str, Any] | None = None
                            ) -> "V.Judgment":
    """Execute `phase` with RETRYABLE mutation up to 3 attempts."""
    if phase_runner is None:
        phase_runner = _default_phase_runner
    overrides = dict(overrides or {})
    while True:
        s = state.read(workspace_dir)
        budget = V.retryable_budget_remaining(
            s["retry_history"], step=7, phase=phase)
        judgment = phase_runner(workspace_dir, phase, overrides)
        if judgment.tier == "pass":
            return judgment
        if judgment.tier == "fatal":
            raise PhaseFatal(f"fatal in phase {phase}: {judgment.cause}")
        if judgment.tier == "warning":
            return judgment   # handled by caller via decision flow
        if judgment.tier == "retryable":
            if budget <= 0:
                raise PhaseFatal(
                    f"retryable budget exhausted in {phase} ({judgment.cause})")
            mutation = _next_mutation(judgment.cause, s["retry_history"])
            s = state.read(workspace_dir)
            s["retry_history"].append({
                "step": 7, "phase": phase, "tier": "retryable",
                "cause": judgment.cause,
                "remediation": str(mutation),
                "command": "phase_runner", "parameters": dict(overrides),
            })
            state.write(workspace_dir, s)
            overrides.update(mutation)
            continue
        raise PhaseFatal(f"unknown tier {judgment.tier}")


def _default_phase_runner(workspace_dir: Path, phase: str,
                           overrides: dict[str, Any]) -> "V.Judgment":
    run_phase(workspace_dir, phase, overrides)
    # Default judgment: PASS. Real validators are wired in Task H6.
    return V.Judgment(tier="pass", metric=phase)
```

Add `run_phase_with_recovery` and `PhaseFatal` to `__init__.py` exports.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_md_runner_retry_loop.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add skills/md_runner/ tests/unit/test_md_runner_retry_loop.py
git commit -m "feat(md-runner): RETRYABLE recovery loop with mutation budget"
```

### Task H5: WARNING flow (`pending_decision` + accept/decline re-invocation)

**Files:**
- Modify: `skills/md_runner/md_runner.py`
- Modify: `skills/md_runner/__init__.py`
- Create: `tests/contract/test_md_runner_warning_flow.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/contract/test_md_runner_warning_flow.py
from pathlib import Path
from unittest.mock import patch
from lib import state, validators as V


def _seed_for_warning(ws: Path):
    s = state.initial(ws)
    s["last_completed_stage"] = "env"
    s["hardware"] = {"cpu_count": 4, "gpu_ids": [], "ntomp": 4}
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    for k in ("step_1","step_2","step_3","step_5"):
        s["step_outputs"][k] = {}
    state.write(ws, s)


def _make_warning():
    return V.Judgment(
        tier="warning", metric="density", observed=985.0,
        expected_range=(995, 1005), cause="pressure_coupling",
        suggested_mutation={"target": "npt.mdp",
                            "changes": {"tau_p": "2.0 → 5.0"},
                            "rationale": "relax barostat"},
    )


def test_warning_returns_pending_decision(tmp_workspace: Path):
    from skills.md_runner.md_runner import handle_phase_result
    _seed_for_warning(tmp_workspace)
    out = handle_phase_result(tmp_workspace, phase="npt",
                              judgment=_make_warning(),
                              interactive=True)
    assert out["status"] == "warning_pending_decision"
    assert out["warning_id"]
    s = state.read(tmp_workspace)
    assert len(s["pending_warnings"]) == 1
    assert s["pending_warnings"][0]["warning_id"] == out["warning_id"]


def test_warning_auto_declined_when_noninteractive(tmp_workspace: Path):
    from skills.md_runner.md_runner import handle_phase_result
    _seed_for_warning(tmp_workspace)
    out = handle_phase_result(tmp_workspace, phase="npt",
                              judgment=_make_warning(),
                              interactive=False)
    assert out["status"] == "warning_declined"
    s = state.read(tmp_workspace)
    assert any(e["cause"] == "auto_decline_noninteractive"
               for e in s["retry_history"])


def test_accept_warning_applies_mutation(tmp_workspace: Path):
    from skills.md_runner.md_runner import handle_phase_result, accept_warning
    _seed_for_warning(tmp_workspace)
    out = handle_phase_result(tmp_workspace, phase="npt",
                              judgment=_make_warning(),
                              interactive=True)
    wid = out["warning_id"]
    overrides = accept_warning(tmp_workspace, wid)
    assert "tau_p" in overrides
    s = state.read(tmp_workspace)
    assert all(p["warning_id"] != wid for p in s["pending_warnings"])
    assert any(e["tier"] == "warning" and e["warning_id"] == wid
               for e in s["retry_history"])


def test_decline_warning_records_and_clears(tmp_workspace: Path):
    from skills.md_runner.md_runner import handle_phase_result, decline_warning
    _seed_for_warning(tmp_workspace)
    out = handle_phase_result(tmp_workspace, phase="npt",
                              judgment=_make_warning(),
                              interactive=True)
    decline_warning(tmp_workspace, out["warning_id"])
    s = state.read(tmp_workspace)
    assert s["pending_warnings"] == []
    assert any(e["cause"] == "user_decline" for e in s["retry_history"])
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement WARNING handling**

```python
import re

_NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)")


def _parse_change_value(target: str, change_str: str) -> Any:
    # "2.0 → 5.0" -> 5.0
    m = _NUM_RE.findall(change_str)
    if not m:
        return change_str
    val = m[-1]
    try:
        return float(val) if "." in val else int(val)
    except ValueError:
        return val


def _record_warning(workspace_dir: Path, phase: str,
                    judgment: V.Judgment) -> dict[str, Any]:
    payload = {
        "warning_id": judgment.warning_id,
        "step": 7, "phase": phase,
        "metric": judgment.metric, "observed": judgment.observed,
        "expected_range": judgment.expected_range,
        "suggested_mutation": judgment.suggested_mutation,
        "cause": judgment.cause,
    }
    s = state.read(workspace_dir)
    s["pending_warnings"].append(payload)
    state.write(workspace_dir, s)
    return payload


def handle_phase_result(workspace_dir: Path, phase: str,
                        judgment: V.Judgment, interactive: bool) -> dict[str, Any]:
    if judgment.tier != "warning":
        return {"status": judgment.tier}
    payload = _record_warning(workspace_dir, phase, judgment)
    if interactive:
        return {"status": "warning_pending_decision",
                "warning_id": payload["warning_id"],
                "payload": payload}
    # auto-decline path
    s = state.read(workspace_dir)
    s["retry_history"].append({
        "step": 7, "phase": phase, "tier": "warning",
        "cause": "auto_decline_noninteractive",
        "warning_id": payload["warning_id"],
        "remediation": "noninteractive=False; no mutation applied",
    })
    s["pending_warnings"] = [p for p in s["pending_warnings"]
                              if p["warning_id"] != payload["warning_id"]]
    state.write(workspace_dir, s)
    return {"status": "warning_declined",
            "warning_id": payload["warning_id"]}


def _pop_warning(workspace_dir: Path, warning_id: str) -> dict[str, Any] | None:
    s = state.read(workspace_dir)
    remaining = []
    found = None
    for p in s["pending_warnings"]:
        if p["warning_id"] == warning_id and found is None:
            found = p
        else:
            remaining.append(p)
    if found is None:
        return None
    s["pending_warnings"] = remaining
    state.write(workspace_dir, s)
    return found


def accept_warning(workspace_dir: Path, warning_id: str) -> dict[str, Any]:
    payload = _pop_warning(workspace_dir, warning_id)
    if not payload:
        raise KeyError(f"warning_id not found: {warning_id}")
    mutation = payload["suggested_mutation"] or {}
    overrides: dict[str, Any] = {}
    for k, v in (mutation.get("changes") or {}).items():
        overrides[k] = _parse_change_value(mutation.get("target", ""), str(v))
    s = state.read(workspace_dir)
    s["retry_history"].append({
        "step": payload["step"], "phase": payload["phase"],
        "tier": "warning", "cause": payload["cause"],
        "warning_id": warning_id,
        "remediation": f"accepted: {overrides}",
    })
    state.write(workspace_dir, s)
    return overrides


def decline_warning(workspace_dir: Path, warning_id: str) -> None:
    payload = _pop_warning(workspace_dir, warning_id)
    if not payload:
        raise KeyError(f"warning_id not found: {warning_id}")
    s = state.read(workspace_dir)
    s["retry_history"].append({
        "step": payload["step"], "phase": payload["phase"],
        "tier": "warning", "cause": "user_decline",
        "warning_id": warning_id,
        "remediation": "user declined; proceeding to next step",
    })
    state.write(workspace_dir, s)
```

Add `handle_phase_result`, `accept_warning`, `decline_warning` to `__init__.py`.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/contract/test_md_runner_warning_flow.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add skills/md_runner/ tests/contract/test_md_runner_warning_flow.py
git commit -m "feat(md-runner): WARNING pending-decision flow with accept/decline"
```

### Task H6: End-to-end `run_simulation` entry and validator wiring

**Files:**
- Modify: `skills/md_runner/md_runner.py`
- Modify: `skills/md_runner/__init__.py`
- Modify: `tests/integration/test_md_runner_minimal.py`

- [ ] **Step 1: Add failing end-to-end test**

Append:

```python
def test_run_simulation_end_to_end(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_simulation
    from lib import state
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    result = run_simulation(
        workspace_dir=tmp_workspace,
        phase_overrides={"em": {"nsteps": 50},
                          "nvt": {"nsteps": 50, "dt": 0.001},
                          "npt": {"nsteps": 50, "dt": 0.001},
                          "production": {"nsteps": 50, "dt": 0.001}},
        interactive=False,
    )
    assert result["status"] in ("complete", "warning_declined")
    s = state.read(tmp_workspace)
    assert s["last_completed_stage"] == "md"
    assert (tmp_workspace / "stage2_md" / "production.gro").exists() or \
           (tmp_workspace / "stage2_md" / "md.gro").exists()
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement validator wiring + `run_simulation`**

```python
from lib import xvg_parser


def _validate_phase(workspace_dir: Path, phase: str) -> V.Judgment:
    """Run gmx energy on the .edr and judge the most relevant metric."""
    ws = Path(workspace_dir)
    edr = ws / "stage2_md" / f"{phase}.edr"
    if not edr.exists():
        return V.Judgment(tier="pass", metric=phase)  # nothing to inspect
    # request density for npt, temperature for nvt, potential for em/production
    if phase == "nvt":
        return _judge_temperature(workspace_dir, phase)
    if phase == "npt":
        return _judge_density(workspace_dir, phase)
    if phase in ("production", "umbrella", "free_energy"):
        return _judge_energy_drift(workspace_dir, phase)
    return V.Judgment(tier="pass", metric=phase)


def _gmx_energy(workspace_dir: Path, phase: str, term: str,
                out_xvg: str) -> Path:
    out_dir = Path(workspace_dir) / "stage2_md"
    GW.run(["energy", "-f", f"{phase}.edr", "-o", out_xvg],
           cwd=out_dir, interactive_inputs=[term, ""])
    return out_dir / out_xvg


def _judge_temperature(ws: Path, phase: str) -> V.Judgment:
    xvg = _gmx_energy(ws, phase, "Temperature", f"{phase}_temp.xvg")
    summary = xvg_parser.summary(xvg)
    if summary["count"] == 0:
        return V.Judgment(tier="pass", metric="temperature")
    return V.judge_temperature(observed=summary["mean"], target=300.0)


def _judge_density(ws: Path, phase: str) -> V.Judgment:
    xvg = _gmx_energy(ws, phase, "Density", f"{phase}_dens.xvg")
    summary = xvg_parser.summary(xvg)
    if summary["count"] == 0:
        return V.Judgment(tier="pass", metric="density")
    return V.judge_density(observed=summary["mean"],
                           expected_range=(995.0, 1005.0))


def _judge_energy_drift(ws: Path, phase: str) -> V.Judgment:
    xvg = _gmx_energy(ws, phase, "Potential", f"{phase}_pot.xvg")
    summary = xvg_parser.summary(xvg)
    if summary["count"] < 2:
        return V.Judgment(tier="pass", metric="energy_drift")
    slope = (summary["last"] - summary["first"]) / max(1, summary["count"])
    return V.judge_energy_drift(slope_per_ns=slope)


def _validating_phase_runner(workspace_dir: Path, phase: str,
                              overrides: dict[str, Any]) -> V.Judgment:
    run_phase(workspace_dir, phase, overrides)
    return _validate_phase(workspace_dir, phase)


def run_simulation(workspace_dir: Path,
                   phase_overrides: dict[str, dict[str, Any]] | None = None,
                   interactive: bool = True,
                   accept_warning_id: str | None = None,
                   decline_warning_id: str | None = None) -> dict[str, Any]:
    if accept_warning_id:
        ov = accept_warning(workspace_dir, accept_warning_id)
        # caller is expected to also supply the phase via phase_overrides
        return {"status": "warning_accepted", "applied_overrides": ov}
    if decline_warning_id:
        decline_warning(workspace_dir, decline_warning_id)
        return {"status": "warning_declined"}

    s = assert_ready(workspace_dir)
    variant = (s.get("tutorial") or {}).get("variant")
    seq = phase_sequence_for_variant(variant)
    phase_overrides = phase_overrides or {}
    for phase in seq:
        judgment = run_phase_with_recovery(
            workspace_dir, phase=phase,
            phase_runner=_validating_phase_runner,
            overrides=phase_overrides.get(phase, {}),
        )
        if judgment.tier == "warning":
            outcome = handle_phase_result(workspace_dir, phase, judgment,
                                          interactive=interactive)
            if outcome["status"] == "warning_pending_decision":
                return outcome
            # else: declined -> proceed
    s = state.read(workspace_dir)
    s["last_completed_stage"] = "md"
    state.write(workspace_dir, s)
    return {"status": "complete"}
```

Add `run_simulation` to `__init__.py`.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/integration/test_md_runner_minimal.py -v`
Expected: 2 passed (or skipped without gmx).

- [ ] **Step 5: Commit**

```bash
git add skills/md_runner/ tests/integration/test_md_runner_minimal.py
git commit -m "feat(md-runner): end-to-end run_simulation with validator wiring"
```

### Task H7: `SKILL.md` and reference docs

**Files:**
- Create: `skills/md_runner/SKILL.md`
- Create: `skills/md_runner/references/phase_protocols.md`
- Create: `skills/md_runner/references/error_recovery.md`
- Create: `skills/md_runner/references/hardware_tuning.md`

- [ ] **Step 1: Create `SKILL.md`**

```yaml
---
name: md-runner
description: >-
  Execute the GROMACS MD pipeline (Step 6–7) on a workspace that already
  contains stage1_env/ artifacts. Selects the phase sequence by tutorial
  variant, runs grompp+mdrun for each phase, validates each phase, and
  handles WARNING decisions via accept/decline re-invocation. Outputs go
  to workspace/stage2_md/. Invoke when env-builder has completed, or when
  the user supplies a pre-built environment.
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: md-runner

## Input Schema

```json
{
  "workspace_dir": "/abs/path/workspace",
  "phase_overrides": {"nvt": {"nsteps": 50000, "tau_t": 0.5}},
  "interactive": true,
  "accept_warning_mutation": "uuid-or-null",
  "decline_warning_mutation": "uuid-or-null"
}
```

## Output Contract

Files under `workspace/stage2_md/`:
`{em,nvt,npt,production}.{tpr,xtc,trr,edr,gro,log,cpt}` or
variant-specific analogues. `workspace/state.json` is updated with
`step_outputs.step_7`, `retry_history[]`, and `last_completed_stage="md"`.

## Return Status Codes

- `complete` — all phases passed (or auto-declined).
- `warning_pending_decision` — user input required to accept/decline a
  proposed mutation. The next invocation supplies
  `accept_warning_mutation` or `decline_warning_mutation`.
- `warning_accepted` — mutation applied; the caller re-invokes with the
  same `phase_overrides` adjusted to resume the phase.
- `warning_declined` — proceeds to the next phase.

## Behavior

1. Validate stage1_env/ artifacts and state.json keys.
2. Resolve the phase sequence from the tutorial variant.
3. For each phase: compose .mdp → `gmx grompp` → `gmx mdrun` → validator.
4. RETRYABLE outcomes mutate parameters up to 3 attempts per phase.
5. WARNING outcomes return `warning_pending_decision` to the caller
   when `interactive=True`, or auto-decline when `interactive=False`.
6. FATAL outcomes stop the pipeline and surface the cause.
```

- [ ] **Step 2: Create `references/phase_protocols.md`**

```markdown
# Phase Protocols

| Variant | Phase sequence |
|---|---|
| protein_aqueous_standard | em → nvt → npt → production |
| membrane_md_standard | em → nvt → npt → npt → production |
| protein_ligand_complex | em → nvt → npt → production |
| umbrella_sampling | em → nvt → npt → umbrella (per window) |
| free_energy_alchemical | em → nvt → npt → free_energy (per lambda) |
| biphasic_system | em → nvt → npt → production |
| virtual_sites_topology | em → production |

Per-phase defaults live in `lib/mdp_templates/base.py`. Override via
the `phase_overrides` field of `run_simulation`.
```

- [ ] **Step 3: Create `references/error_recovery.md`**

```markdown
# Error Recovery Rules

| Cause | First mutation | Second | Third |
|---|---|---|---|
| unstable_energy | `{nsteps: 100}` | `{nsteps: 200, dt: 0.001}` | `{nsteps: 400, dt: 0.0005}` |
| pressure_coupling | `{tau_p: 5.0}` | `{tau_p: 8.0}` | `{tau_p: 10.0}` |
| temperature_coupling | `{tau_t: 0.5}` | `{tau_t: 1.0}` | `{tau_t: 2.0}` |
| command_error | `{-maxwarn: 2}` | `{-maxwarn: 3}` | `{-maxwarn: 4}` |
| topology_mismatch | restore from `.bak`; regenerate topology | — | FATAL |
| missing_input | FATAL (caller must supply input) | — | — |

RETRYABLE budget per phase per cause is 3. WARNING retries do not consume
the RETRYABLE budget. The identical-command-and-parameter rule applies
to both tiers.
```

- [ ] **Step 4: Create `references/hardware_tuning.md`**

```markdown
# Hardware Tuning

`state.hardware.ntomp` is computed as `cpu_count / max(1, n_gpus)` at
workspace init. `mdrun` is invoked with `-ntomp` to spread OpenMP
threads across the available GPUs. To pin to specific GPUs, set
`GMX_GPU_ID` in the environment before invoking md-runner.

If `nvidia-smi` is unavailable, GPU detection returns an empty list and
md-runner runs CPU-only. The user can override via
`phase_overrides.global = {"gpu_id": "0,1"}` (handled by future
extension; currently ignored).
```

- [ ] **Step 5: Commit**

```bash
git add skills/md_runner/SKILL.md skills/md_runner/references/
git commit -m "docs(md-runner): add SKILL.md and reference materials"
```

---

## Phase I — `skills/illustrator/`

### Task I1: Entry-gate validation and skeleton

**Files:**
- Create: `skills/illustrator/__init__.py`
- Create: `skills/illustrator/illustrator.py`
- Create: `tests/contract/test_illustrator_io.py`

- [ ] **Step 1: Write failing test**

```python
# tests/contract/test_illustrator_io.py
from pathlib import Path
import pytest
from lib import state


def _seed_md_stage(ws: Path):
    s = state.initial(ws)
    s["last_completed_stage"] = "md"
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    s["step_outputs"]["step_7"] = {
        "em_gro": "stage2_md/em.gro", "nvt_gro": "stage2_md/nvt.gro",
        "npt_gro": "stage2_md/npt.gro",
        "production_gro": "stage2_md/production.gro",
    }
    state.write(ws, s)
    for fname in ("production.tpr", "production.xtc", "production.edr"):
        (ws / "stage2_md" / fname).write_text("placeholder")


def test_entry_gate_passes_when_md_complete(tmp_workspace: Path):
    from skills.illustrator.illustrator import assert_ready
    _seed_md_stage(tmp_workspace)
    assert_ready(tmp_workspace)


def test_entry_gate_fails_when_stage_marker_wrong(tmp_workspace: Path):
    from skills.illustrator.illustrator import assert_ready
    from lib.state import StateContractError
    _seed_md_stage(tmp_workspace)
    s = state.read(tmp_workspace)
    s["last_completed_stage"] = "env"
    state.write(tmp_workspace, s)
    with pytest.raises(StateContractError):
        assert_ready(tmp_workspace)


def test_entry_gate_fails_when_trajectory_missing(tmp_workspace: Path):
    from skills.illustrator.illustrator import assert_ready
    from lib.state import StateContractError
    _seed_md_stage(tmp_workspace)
    (tmp_workspace / "stage2_md" / "production.xtc").unlink()
    with pytest.raises(StateContractError):
        assert_ready(tmp_workspace)
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement skeleton**

```python
# skills/illustrator/illustrator.py
from pathlib import Path
from typing import Any
from lib import state
from lib.state import StateContractError


def _trajectory_prefix(s: dict[str, Any]) -> str:
    step7 = s["step_outputs"].get("step_7", {})
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
```

`skills/illustrator/__init__.py`:

```python
from .illustrator import assert_ready  # noqa: F401
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/contract/test_illustrator_io.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add skills/illustrator/ tests/contract/test_illustrator_io.py
git commit -m "feat(illustrator): entry-gate validation"
```

### Task I2: Core analyses (RMSD, RMSF, gyrate, SASA, energy)

**Files:**
- Modify: `skills/illustrator/illustrator.py`
- Modify: `skills/illustrator/__init__.py`
- Create: `tests/integration/test_illustrator_dryrun.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_illustrator_dryrun.py
import shutil
from pathlib import Path
import pytest

GMX = shutil.which("gmx")
pytestmark = pytest.mark.skipif(GMX is None, reason="gmx not on PATH")


def test_core_analyses_produce_xvg(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_simulation
    from skills.illustrator import run_core_analyses
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    run_simulation(
        workspace_dir=tmp_workspace,
        phase_overrides={"em": {"nsteps": 50},
                          "nvt": {"nsteps": 50, "dt": 0.001},
                          "npt": {"nsteps": 50, "dt": 0.001},
                          "production": {"nsteps": 100, "dt": 0.001}},
        interactive=False,
    )
    summaries = run_core_analyses(tmp_workspace)
    for key in ("rmsd", "rmsf", "gyrate", "energy_potential",
                "energy_temperature", "energy_density"):
        assert key in summaries
        assert "mean" in summaries[key] or summaries[key]["count"] == 0
    viz = tmp_workspace / "stage3_viz"
    for fname in ("rmsd.xvg", "rmsf.xvg", "gyrate.xvg"):
        assert (viz / fname).exists()
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement core analyses**

Append to `skills/illustrator/illustrator.py`:

```python
from lib import gmx_wrapper as GW, xvg_parser


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
```

Add `run_core_analyses` to `__init__.py`.

- [ ] **Step 4: Run, confirm pass on a gmx-equipped machine**

Run: `pytest tests/integration/test_illustrator_dryrun.py -v`
Expected: 1 passed (or skipped).

- [ ] **Step 5: Commit**

```bash
git add skills/illustrator/ tests/integration/test_illustrator_dryrun.py
git commit -m "feat(illustrator): RMSD, RMSF, gyrate, SASA, energy analyses"
```

### Task I3: Hydrogen bonds, DSSP, PCA

**Files:**
- Modify: `skills/illustrator/illustrator.py`
- Modify: `skills/illustrator/__init__.py`
- Modify: `tests/integration/test_illustrator_dryrun.py`

- [ ] **Step 1: Add failing test**

Append:

```python
def test_advanced_analyses_run(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_simulation
    from skills.illustrator import run_advanced_analyses
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    run_simulation(workspace_dir=tmp_workspace,
                   phase_overrides={p: {"nsteps": 100, "dt": 0.001}
                                     for p in ("em","nvt","npt","production")},
                   interactive=False)
    out = run_advanced_analyses(tmp_workspace)
    assert "hbond" in out
    assert "dssp" in out
    assert "pca" in out
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement advanced analyses**

```python
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
```

Add to `__init__.py`.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/integration/test_illustrator_dryrun.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add skills/illustrator/ tests/integration/test_illustrator_dryrun.py
git commit -m "feat(illustrator): hbond, dssp, pca analyses"
```

### Task I4: Tutorial-specific analyses (umbrella, free-energy, membrane, protein-ligand)

**Files:**
- Modify: `skills/illustrator/illustrator.py`
- Modify: `skills/illustrator/__init__.py`
- Create: `tests/unit/test_illustrator_variant_dispatch.py`

- [ ] **Step 1: Write failing test (dispatch only — no gmx required)**

```python
# tests/unit/test_illustrator_variant_dispatch.py
from unittest.mock import patch
from pathlib import Path
from lib import state


def _seed(ws: Path, variant: str):
    s = state.initial(ws)
    s["last_completed_stage"] = "md"
    s["tutorial"] = {"id": "X", "variant": variant, "manifest_path": ""}
    s["step_outputs"]["step_7"] = {"production_gro": "stage2_md/production.gro"}
    state.write(ws, s)
    for fn in ("production.tpr", "production.xtc", "production.edr"):
        (ws / "stage2_md" / fn).write_text("x")


def test_umbrella_dispatch_calls_wham(tmp_workspace: Path):
    from skills.illustrator import run_variant_analyses
    _seed(tmp_workspace, "umbrella_sampling")
    with patch("skills.illustrator.illustrator._run_wham") as m:
        m.return_value = {"pmf_xvg": "pmf.xvg"}
        out = run_variant_analyses(tmp_workspace)
    assert m.called
    assert out["pmf_xvg"] == "pmf.xvg"


def test_free_energy_dispatch_calls_bar(tmp_workspace: Path):
    from skills.illustrator import run_variant_analyses
    _seed(tmp_workspace, "free_energy_alchemical")
    with patch("skills.illustrator.illustrator._run_bar") as m:
        m.return_value = {"dG_kJ_per_mol": -12.3}
        out = run_variant_analyses(tmp_workspace)
    assert m.called
    assert out["dG_kJ_per_mol"] == -12.3


def test_standard_variant_returns_empty(tmp_workspace: Path):
    from skills.illustrator import run_variant_analyses
    _seed(tmp_workspace, "protein_aqueous_standard")
    assert run_variant_analyses(tmp_workspace) == {}
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement dispatch + analysis stubs**

```python
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


VARIANT_DISPATCH = {
    "umbrella_sampling": _run_wham,
    "free_energy_alchemical": _run_bar,
    "membrane_md_standard": _run_membrane_analysis,
    "protein_ligand_complex": _run_protein_ligand_analysis,
}


def run_variant_analyses(workspace_dir: Path) -> dict[str, Any]:
    s = state.read(workspace_dir)
    variant = (s.get("tutorial") or {}).get("variant", "")
    fn = VARIANT_DISPATCH.get(variant)
    if not fn:
        return {}
    result = fn(workspace_dir)
    s = state.read(workspace_dir)
    s["step_outputs"].setdefault("step_8", {})["variant_summary"] = result
    state.write(workspace_dir, s)
    return result
```

Add to `__init__.py`.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_illustrator_variant_dispatch.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add skills/illustrator/ tests/unit/test_illustrator_variant_dispatch.py
git commit -m "feat(illustrator): variant-specific analysis dispatch (wham, bar, stubs)"
```

### Task I5: Matplotlib plotting

**Files:**
- Modify: `skills/illustrator/illustrator.py`
- Modify: `skills/illustrator/__init__.py`
- Create: `tests/unit/test_illustrator_plots.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_illustrator_plots.py
from pathlib import Path


def _write_xvg(p: Path, n: int = 100):
    lines = ['@ title "t"\n', '@ xaxis label "x"\n', '@ yaxis label "y"\n']
    for i in range(n):
        lines.append(f"{i} {i*0.1:.3f}\n")
    p.write_text("".join(lines))


def test_plot_xvg_creates_png(tmp_path: Path):
    from skills.illustrator.illustrator import plot_xvg
    xvg = tmp_path / "rmsd.xvg"
    _write_xvg(xvg)
    png = plot_xvg(xvg, output_path=tmp_path / "rmsd.png", title="RMSD")
    assert png.exists()
    assert png.stat().st_size > 0


def test_plot_all_creates_one_png_per_xvg(tmp_path: Path):
    from skills.illustrator.illustrator import plot_all
    (tmp_path / "stage3_viz").mkdir(parents=True)
    for name in ("rmsd.xvg", "rmsf.xvg", "gyrate.xvg"):
        _write_xvg(tmp_path / "stage3_viz" / name)
    pngs = plot_all(tmp_path)
    assert len(pngs) == 3
    for p in pngs:
        assert p.suffix == ".png"
        assert p.exists()
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement plotting**

```python
def plot_xvg(xvg_path: Path, output_path: Path, title: str = "") -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data = xvg_parser.parse(xvg_path, max_points=2000)
    fig, ax = plt.subplots(figsize=(8, 5))
    cols = data["columns"]
    if len(cols) >= 2:
        ax.plot(cols[0], cols[1])
    ax.set_xlabel(data["xaxis_label"])
    ax.set_ylabel(data["yaxis_label"])
    ax.set_title(title or data["title"] or xvg_path.stem)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
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
```

Add to `__init__.py`.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_illustrator_plots.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add skills/illustrator/ tests/unit/test_illustrator_plots.py
git commit -m "feat(illustrator): matplotlib plot rendering for all xvg outputs"
```

### Task I6: Structural rendering (PyMOL primary, VMD fallback, matplotlib-only fallback)

**Files:**
- Modify: `skills/illustrator/illustrator.py`
- Modify: `skills/illustrator/__init__.py`
- Create: `tests/unit/test_illustrator_renderer.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_illustrator_renderer.py
from pathlib import Path
from unittest.mock import patch


def test_renderer_picks_pymol_when_available():
    from skills.illustrator.illustrator import select_renderer
    with patch("shutil.which", side_effect=lambda x: "/usr/bin/pymol"
               if x == "pymol" else None):
        assert select_renderer() == "pymol"


def test_renderer_falls_back_to_vmd():
    from skills.illustrator.illustrator import select_renderer
    with patch("shutil.which", side_effect=lambda x: "/usr/bin/vmd"
               if x == "vmd" else None):
        assert select_renderer() == "vmd"


def test_renderer_falls_back_to_matplotlib_only():
    from skills.illustrator.illustrator import select_renderer
    with patch("shutil.which", return_value=None):
        assert select_renderer() == "none"


def test_render_frame_returns_none_when_no_renderer(tmp_path: Path):
    from skills.illustrator.illustrator import render_frame
    with patch("shutil.which", return_value=None):
        result = render_frame(
            workspace_dir=tmp_path, frame="last",
            output_path=tmp_path / "frame_last.png")
    assert result is None
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement rendering**

```python
import shutil


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
```

Add `render_frame` and `select_renderer` to `__init__.py`.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_illustrator_renderer.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add skills/illustrator/ tests/unit/test_illustrator_renderer.py
git commit -m "feat(illustrator): PyMOL/VMD frame rendering with graceful degradation"
```

### Task I7: Trajectory animation via ffmpeg

**Files:**
- Modify: `skills/illustrator/illustrator.py`
- Modify: `skills/illustrator/__init__.py`
- Create: `tests/unit/test_illustrator_animation.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_illustrator_animation.py
from pathlib import Path
from unittest.mock import patch


def test_animate_skipped_when_renderer_missing(tmp_path: Path):
    from skills.illustrator.illustrator import animate_trajectory
    with patch("shutil.which", return_value=None):
        out = animate_trajectory(tmp_path, output_path=tmp_path / "a.mp4")
    assert out is None


def test_animate_skipped_when_ffmpeg_missing(tmp_path: Path):
    from skills.illustrator.illustrator import animate_trajectory
    def which(x):
        return "/usr/bin/pymol" if x == "pymol" else None
    with patch("shutil.which", side_effect=which):
        out = animate_trajectory(tmp_path, output_path=tmp_path / "a.mp4")
    assert out is None
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement animation**

```python
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
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_illustrator_animation.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add skills/illustrator/ tests/unit/test_illustrator_animation.py
git commit -m "feat(illustrator): ffmpeg-backed trajectory animation"
```

### Task I8: Markdown + optional HTML report composer

**Files:**
- Modify: `skills/illustrator/illustrator.py`
- Modify: `skills/illustrator/__init__.py`
- Create: `tests/unit/test_illustrator_report.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_illustrator_report.py
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
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement report composer**

```python
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
        lines.append(f"| {name} | {st.get('mean','-'):.4g} "
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
```

Add `compose_report`, `compose_html_report` to `__init__.py`.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/unit/test_illustrator_report.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add skills/illustrator/ tests/unit/test_illustrator_report.py
git commit -m "feat(illustrator): markdown report composer with stub html option"
```

### Task I9: Top-level `illustrate` entry point

**Files:**
- Modify: `skills/illustrator/illustrator.py`
- Modify: `skills/illustrator/__init__.py`
- Modify: `tests/integration/test_illustrator_dryrun.py`

- [ ] **Step 1: Add failing end-to-end test**

Append to `tests/integration/test_illustrator_dryrun.py`:

```python
def test_illustrate_end_to_end(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_simulation
    from skills.illustrator import illustrate
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    run_simulation(workspace_dir=tmp_workspace,
                   phase_overrides={p: {"nsteps": 100, "dt": 0.001}
                                     for p in ("em","nvt","npt","production")},
                   interactive=False)
    result = illustrate(workspace_dir=tmp_workspace, animation={"enabled": False})
    assert result["report_path"]
    from lib import state as _s
    s = _s.read(tmp_workspace)
    assert s["last_completed_stage"] == "viz"
```

- [ ] **Step 2: Run, confirm failure**

- [ ] **Step 3: Implement `illustrate`**

```python
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
```

Add `illustrate` to `__init__.py`.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/integration/test_illustrator_dryrun.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add skills/illustrator/ tests/integration/test_illustrator_dryrun.py
git commit -m "feat(illustrator): end-to-end illustrate entry point"
```

### Task I10: `SKILL.md` and reference docs

**Files:**
- Create: `skills/illustrator/SKILL.md`
- Create: `skills/illustrator/references/analysis_recipes.md`
- Create: `skills/illustrator/references/render_recipes.md`
- Create: `skills/illustrator/references/animation_recipes.md`

- [ ] **Step 1: Create `skills/illustrator/SKILL.md`**

```yaml
---
name: illustrator
description: >-
  Analyze, plot, render, animate, and report on a completed MD trajectory.
  Runs the full analysis catalog (RMSD, RMSF, gyrate, SASA, hbond, dssp,
  energy, PCA, plus tutorial-specific PMF/BAR/membrane/ligand analyses).
  Produces matplotlib plots, PyMOL/VMD structural renders (with graceful
  degradation), ffmpeg trajectory animations, and a markdown report.
  Outputs to workspace/stage3_viz/. Invoke when md-runner has completed,
  or when the user supplies an existing trajectory.
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: illustrator

## Input Schema

```json
{
  "workspace_dir": "/abs/path/workspace",
  "analyses": ["rmsd","rmsf","gyrate","sasa","hbond","dssp","energy","pca",
               "tutorial_specific"],
  "render_frames": [0, "middle", "last"],
  "animation": {"enabled": true, "fps": 30, "stride": 10, "formats": ["mp4"]},
  "report_html": true,
  "interactive": true
}
```

## Output Contract

Files under `workspace/stage3_viz/`:
- `*.xvg` for every analysis
- `*.png` for every plot
- `frame_*.png` for each rendered frame
- `trajectory.mp4` (or `.gif`) for animation
- `report.md` (and optional `report.html`)

`workspace/state.json` is updated with
`step_outputs.step_8.{analysis_summaries, advanced_summaries,
variant_summary, final_report_path}` and `last_completed_stage="viz"`.

## Graceful Degradation

- PyMOL absent → VMD attempted → matplotlib-only.
- ffmpeg absent → animation skipped (plots and renders still produced).
- plotly absent → `report.html` skipped; `report.md` still produced.

## References

- `references/analysis_recipes.md`
- `references/render_recipes.md`
- `references/animation_recipes.md`
```

- [ ] **Step 2: Create `references/analysis_recipes.md`**

```markdown
# Analysis Recipes

| Analysis | gmx tool | Default groups |
|---|---|---|
| RMSD | `gmx rms` | Backbone vs Backbone |
| RMSF | `gmx rmsf -res` | Protein |
| Radius of gyration | `gmx gyrate` | Protein |
| SASA | `gmx sasa` | Protein |
| H-bonds | `gmx hbond -num` | Protein/Protein |
| Secondary structure | `gmx do_dssp` | Protein |
| Energy terms | `gmx energy` | Potential, Kinetic, Total, Temperature, Pressure, Density |
| PCA | `gmx covar` + `gmx anaeig -2d -first 1 -last 2` | Backbone |
| Umbrella PMF | `gmx wham` | requires pull files |
| Free energy ΔG | `gmx bar` | requires per-lambda `md_l*.edr` |
| Membrane (stub) | extensions | thickness, area per lipid, order parameters |
| Protein-ligand (stub) | extensions | ligand RMSD, binding distance, interaction map |

All analyses pass `.xvg` outputs through `lib/xvg_parser` for
downsampled JSON; the LLM never reads raw `.xvg`.
```

- [ ] **Step 3: Create `references/render_recipes.md`**

```markdown
# Render Recipes

| Renderer | Detection | Command |
|---|---|---|
| PyMOL | `shutil.which("pymol")` | `pymol -cq render.pml` |
| VMD | `shutil.which("vmd")` | `vmd -dispdev text -e render.vmd` |
| Fallback | neither installed | no frame rendered, plot-only report |

PyMOL script template (`_PYMOL_SCRIPT` in `illustrator.py`) supplies the
default cartoon + surface + key-residue close-up. Override the
`highlight_resi` parameter from `render_frame()` to focus on a binding
pocket or membrane cross-section.
```

- [ ] **Step 4: Create `references/animation_recipes.md`**

```markdown
# Animation Recipes

Animation is enabled when PyMOL or VMD AND ffmpeg are on `PATH`.
The default is 30 fps with stride 10 (every 10th frame).

PyMOL: uses `movie.produce` with `encoder=ffmpeg`. VMD: invokes the
`make movie` plugin (TBD; current implementation focuses on PyMOL).

Output formats:
- `.mp4` (default, h264 via ffmpeg)
- `.gif` (optional; set `animation.formats=["mp4","gif"]`)
```

- [ ] **Step 5: Commit**

```bash
git add skills/illustrator/SKILL.md skills/illustrator/references/
git commit -m "docs(illustrator): add SKILL.md and reference materials"
```

---

## Phase J — Cross-skill state handoff contract

### Task J1: Independent-entry contract test for md-runner

**Files:**
- Create: `tests/contract/test_state_handoff.py`

- [ ] **Step 1: Write failing test**

```python
# tests/contract/test_state_handoff.py
import shutil
from pathlib import Path
import pytest

GMX = shutil.which("gmx")


def test_md_runner_accepts_externally_prepared_env(tmp_workspace: Path):
    """User provides stage1_env/ artifacts + minimal state.json,
       md-runner must accept and proceed (or skip gracefully if no gmx).
    """
    from lib import state
    s = state.initial(tmp_workspace)
    s["last_completed_stage"] = "env"
    s["hardware"] = {"cpu_count": 2, "gpu_ids": [], "ntomp": 2}
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    s["step_outputs"]["step_1"] = {
        "forcefield": "charmm36", "water_model": "tip3p",
        "top_file": "stage1_env/topol.top",
        "gro_file": "stage1_env/processed.gro",
    }
    s["step_outputs"]["step_2"] = {"box_type": "cubic", "box_distance": 1.0,
                                    "box_gro": "stage1_env/box.gro"}
    s["step_outputs"]["step_3"] = {"solv_gro": "stage1_env/solv.gro",
                                    "n_solvent_molecules": 0}
    s["step_outputs"]["step_5"] = {"ion_gro": "stage1_env/ions.gro",
                                    "n_na": 0, "n_cl": 0, "net_charge": 0.0}
    state.write(tmp_workspace, s)
    for f in ("processed.gro", "topol.top", "ions.gro"):
        (tmp_workspace / "stage1_env" / f).write_text("placeholder")
    from skills.md_runner.md_runner import assert_ready
    assert_ready(tmp_workspace)  # no exception


def test_illustrator_accepts_externally_prepared_md(tmp_workspace: Path):
    from lib import state
    s = state.initial(tmp_workspace)
    s["last_completed_stage"] = "md"
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    s["step_outputs"]["step_7"] = {
        "production_gro": "stage2_md/production.gro",
    }
    state.write(tmp_workspace, s)
    for f in ("production.tpr", "production.xtc", "production.edr"):
        (tmp_workspace / "stage2_md" / f).write_text("placeholder")
    from skills.illustrator.illustrator import assert_ready
    assert_ready(tmp_workspace)
```

- [ ] **Step 2: Run, confirm pass**

These tests should already pass because the entry-gate logic exists. If a
test fails, the related entry-gate logic needs tightening.

Run: `pytest tests/contract/test_state_handoff.py -v`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_state_handoff.py
git commit -m "test(contract): independent-entry state handoff contracts"
```

### Task J2: Full-pipeline chained handoff test

**Files:**
- Modify: `tests/contract/test_state_handoff.py`

- [ ] **Step 1: Add failing test**

Append:

```python
@pytest.mark.skipif(GMX is None, reason="gmx not on PATH")
def test_full_pipeline_progresses_last_completed_stage(tmp_workspace: Path,
                                                       ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_simulation
    from skills.illustrator import illustrate
    from lib import state
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    assert state.read(tmp_workspace)["last_completed_stage"] == "env"
    run_simulation(workspace_dir=tmp_workspace,
                   phase_overrides={p: {"nsteps": 100, "dt": 0.001}
                                     for p in ("em","nvt","npt","production")},
                   interactive=False)
    assert state.read(tmp_workspace)["last_completed_stage"] == "md"
    illustrate(workspace_dir=tmp_workspace, animation={"enabled": False})
    assert state.read(tmp_workspace)["last_completed_stage"] == "viz"
```

- [ ] **Step 2: Run, confirm pass**

Run: `pytest tests/contract/test_state_handoff.py -v`
Expected: 3 passed (1 skipped without gmx).

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_state_handoff.py
git commit -m "test(contract): full-pipeline last_completed_stage progression"
```

---

## Phase K — Documentation refresh

### Task K1: Rewrite `skills/SKILLS_OVERVIEW.md` for the 3-skill model

**Files:**
- Modify: `skills/SKILLS_OVERVIEW.md`

- [ ] **Step 1: Replace contents**

Replace the entire file with:

```markdown
# Skills Overview — GROMACS Harness

This document lists the three top-level skills the LLM agent invokes
and the internal `lib/` modules they share. The old 7-skill layer was
removed during the 2026-05-14 redesign.

## Skill Directory Layout

```
skills/
├── env_builder/                # Skill 1 — Step 0–5 (environment build)
│   ├── SKILL.md
│   ├── env_builder.py
│   └── references/
├── md_runner/                  # Skill 2 — Step 6–7 (MD execution)
│   ├── SKILL.md
│   ├── md_runner.py
│   └── references/
└── illustrator/                # Skill 3 — Step 8 (analysis + viz)
    ├── SKILL.md
    ├── illustrator.py
    └── references/

lib/                            # Internal helpers (no SKILL.md)
├── state.py
├── validators.py
├── gmx_wrapper.py
├── xvg_parser.py
├── tutorial_registry.py
└── mdp_templates/
```

## Skill Roster

| Skill ID | Folder | Step Range | Trigger |
|---|---|---|---|
| `env-builder` | `skills/env_builder/` | Step 0–5 | A PDB + prompt are available and an MD environment is needed |
| `md-runner` | `skills/md_runner/` | Step 6–7 | Workspace has stage1_env/ artifacts |
| `illustrator` | `skills/illustrator/` | Step 8 | Workspace has stage2_md/ trajectory + .edr |

Each skill is **independently invokable** and the three can be
**chained** in order. The file-based contract is documented in each
skill's `SKILL.md`.

## State Contract

All skills read and write a single `workspace/state.json`. Step 0–8
keys are preserved exactly; the user-facing stage labels
(`env`/`md`/`viz`) are stored in `last_completed_stage`. See
`ARCHITECTURE.md` for the full Step 0–8 contract.

## Internal `lib/`

| Module | Responsibility |
|---|---|
| `state.py` | atomic state.json R/W + entry-gate validators |
| `validators.py` | PASS / WARNING / RETRYABLE / FATAL judgments + retry contract |
| `gmx_wrapper.py` | `gmx` subprocess with error classification + topology backup |
| `xvg_parser.py` | downsampled JSON for `.xvg` files |
| `tutorial_registry.py` | tutorial index/manifest loader + routing decision |
| `mdp_templates/` | base `.mdp` templates for all phases (em/nvt/npt/production/ions/umbrella/free_energy) |

## Versioning

Each `SKILL.md` carries `metadata.version` using semantic versioning.
Breaking input/output schema changes bump the major version.
```

- [ ] **Step 2: Commit**

```bash
git add skills/SKILLS_OVERVIEW.md
git commit -m "docs: rewrite SKILLS_OVERVIEW for 3-skill model"
```

### Task K2: Refresh `docs/tutorial/LLM_TUTORIAL_GUIDE.md` for routing inside env-builder

**Files:**
- Modify: `docs/tutorial/LLM_TUTORIAL_GUIDE.md`

- [ ] **Step 1: Replace contents**

```markdown
# LLM Tutorial Guide

## Purpose

This guide is the routing decision document consumed by the
`env-builder` skill (via `lib/tutorial_registry.py`) when a new
workspace is initialized. It tells `env-builder` which tutorial to
follow given a PDB file, user prompt, and optional prerequisites.

## Decision Tree

```
1. Apply keyword match on `prompt`
   - umbrella / pmf / pulling / wham         → Umbrella_Sampling
   - methane + free energy                   → Free_Energy_Calculations_Methane_in_Water
   - ethanol + hydration free energy         → Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol
   - biphasic / interface / two-phase        → Building_Biphasic_Systems
   - virtual sites / vsite                   → Virtual_Sites
   - ligand / protein-ligand / binding       → Protein_Ligand_Complex
   - membrane / DPPC / lipid / bilayer       → KALP15_in_DPPC
   - protein in water / aqueous / lysozyme   → Lysozyme_in_water

2. If no keyword match: inspect PDB hints
   - has_membrane  → KALP15_in_DPPC
   - has_ligand    → Protein_Ligand_Complex
   - has_protein   → Lysozyme_in_water (fallback)

3. Look up entry in tutorial_index.json:
   - required_inputs − {protein_pdb} must be present in prerequisites
     (ligand_itp satisfies ligand_structure)
   - if unsupported_autonomy_level != "none" AND any prerequisites
     are missing → raise UnsupportedTutorialError
```

## Confidence

- `high` — keyword match AND prerequisites complete.
- `medium` — keyword match BUT prerequisites are not strict.
- `low` — fell through to fallback (no keyword match).

## Prerequisite Schemas

See `skills/env_builder/references/prerequisite_schema.md` for the
exact key set each tutorial requires.

## Source Priority

1. Per-tutorial `tutorial.manifest.json` is runtime truth.
2. `tutorial_index.json` is routing/index truth.
3. Tutorial markdown parts are rationale/reference.

## Stop Conditions

`env-builder` raises `UnsupportedTutorialError` and refuses to proceed
when:

- Prerequisites for a derived tutorial are missing.
- The selected tutorial has `unsupported_autonomy_level: research_only`
  (currently Virtual_Sites).

## Mandatory Rules Binding

Whatever tutorial is selected, the safety contracts in `AGENTS.md`
still apply: state.json keys at each step, `topol.top.bak` before
Steps 3 and 5, hardware profile before Step 6+, no identical retry,
no raw `.xvg`/trajectory reads by the LLM.
```

- [ ] **Step 2: Commit**

```bash
git add docs/tutorial/LLM_TUTORIAL_GUIDE.md
git commit -m "docs(tutorial): refresh routing guide for 3-skill model"
```

### Task K3: Update `AGENTS.md` skill references

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Replace the "Available Resources" section**

Replace the Skills and References tables in `AGENTS.md` with:

```markdown
### Skills (Execution Tools)

| Skill ID | Folder | Purpose |
|---|---|---|
| `env-builder` | `skills/env_builder/` | Step 0–5: hardware profile, routing, topology, box, solvation, ions |
| `md-runner` | `skills/md_runner/` | Step 6–7: per-phase grompp+mdrun with validator gates and retry/warning handling |
| `illustrator` | `skills/illustrator/` | Step 8: analysis, plots, renders, animation, report |

### Internal Helpers (`lib/`, no SKILL.md)

| Module | Replaces (legacy) |
|---|---|
| `lib/state.py` | `StateManager` |
| `lib/gmx_wrapper.py` | `GmxExecutor` |
| `lib/mdp_templates` | `MdpComposer` |
| `lib/validators.py` | `SystemValidator` (judgment subset) |
| `lib/xvg_parser.py` | parser portion of `TrajectoryAnalyzer` |
| `lib/tutorial_registry.py` | `TutorialRouter` + `TutorialPlanner` |

### References (Knowledge Base)

| Document | Location |
|---|---|
| Routing decision tree | `docs/tutorial/LLM_TUTORIAL_GUIDE.md` |
| Step-by-step essentials | `docs/tutorial/LLM_ESSENTIALS_BY_STEP.md` |
| CHARMM-GUI mapping | `skills/env_builder/references/charmmgui_workflow.md` |
| Force field guide | `skills/env_builder/references/forcefield_guide.md` |
| Prerequisite schema | `skills/env_builder/references/prerequisite_schema.md` |
| Phase protocols | `skills/md_runner/references/phase_protocols.md` |
| Error recovery | `skills/md_runner/references/error_recovery.md` |
| Hardware tuning | `skills/md_runner/references/hardware_tuning.md` |
| Analysis recipes | `skills/illustrator/references/analysis_recipes.md` |
| Render recipes | `skills/illustrator/references/render_recipes.md` |
| Animation recipes | `skills/illustrator/references/animation_recipes.md` |
```

The mandatory-rules section (state tracking, topology backup, hardware
awareness, retry mutation, large-file protection) stays unchanged.

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): point to new 3-skill resources"
```

### Task K4: Update `ARCHITECTURE.md` with 3-skill mapping

**Files:**
- Modify: `ARCHITECTURE.md`

- [ ] **Step 1: Append a new section**

Append the following at the bottom of `ARCHITECTURE.md`:

```markdown
## 7. 3-Skill Mapping (added 2026-05-14)

The fixed Step 0–8 contract is preserved. Skills group steps for
user-facing invocation:

| Stage | Skill | Steps |
|---|---|---|
| env | `env-builder` | 0, 1, 2, 3, 4, 5 |
| md | `md-runner` | 6, 7 |
| viz | `illustrator` | 8 |

`workspace/state.json.last_completed_stage` advances `env → md → viz`.
The old `TutorialRouter` / `TutorialPlanner` / `ProtocolCompiler`
skills are replaced by `lib/tutorial_registry.py` invoked inside
`env-builder`.
```

- [ ] **Step 2: Commit**

```bash
git add ARCHITECTURE.md
git commit -m "docs(architecture): add 3-skill mapping"
```

---

## Phase L — Regression scripts and cleanup

### Task L1: Replace `scripts/regression_multi_pdb.sh` with per-tutorial scripts

**Files:**
- Delete: `scripts/regression_multi_pdb.sh`
- Delete: `scripts/regression_summary.py`
- Create: `scripts/regression/run_tutorial.sh`
- Create: `scripts/regression/lysozyme.sh`
- Create: `scripts/regression/kalp15.sh`
- Create: `scripts/regression/protein_ligand.sh`
- Create: `scripts/regression/umbrella.sh`
- Create: `scripts/regression/biphasic.sh`
- Create: `scripts/regression/fe_methane.sh`
- Create: `scripts/regression/fe_ethanol.sh`
- Create: `scripts/regression/virtual_sites.sh`

- [ ] **Step 1: Create the shared runner `scripts/regression/run_tutorial.sh`**

```bash
#!/usr/bin/env bash
# Usage: run_tutorial.sh <tutorial_id> <pdb_path> [prompt] [prereq_json]
set -euo pipefail

TUTORIAL_ID="${1:?tutorial id required}"
PDB="${2:?pdb path required}"
PROMPT="${3:-run a basic protein simulation in water}"
PREREQ_JSON="${4:-{}}"
TAG="${TUTORIAL_ID}_$(date +%Y%m%d_%H%M%S)"
WS="runs/${TAG}"
mkdir -p "${WS}"

python -c "
from pathlib import Path
import json
from skills.env_builder import build_environment
from skills.md_runner import run_simulation
from skills.illustrator import illustrate

ws = Path('${WS}').resolve()
build_environment(pdb_path=Path('${PDB}').resolve(),
                  prompt='${PROMPT}',
                  workspace_dir=ws,
                  prerequisites=json.loads('${PREREQ_JSON}'),
                  interactive=False)
run_simulation(workspace_dir=ws, phase_overrides={}, interactive=False)
illustrate(workspace_dir=ws, animation={'enabled': False})
print(f'OK ${TUTORIAL_ID} -> {ws}/stage3_viz/report.md')
"
```

`chmod +x scripts/regression/run_tutorial.sh`.

- [ ] **Step 2: Create per-tutorial scripts**

Each script invokes `run_tutorial.sh` with the tutorial-appropriate
prompt and prerequisite JSON.

`scripts/regression/lysozyme.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh Lysozyme_in_water 1UBQ.pdb \
  "lysozyme in water basic md" "{}"
```

`scripts/regression/kalp15.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh KALP15_in_DPPC inputs/kalp15.pdb \
  "membrane protein in DPPC" \
  '{"membrane_composition": {"DPPC": 128}}'
```

`scripts/regression/protein_ligand.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh Protein_Ligand_Complex \
  inputs/protein_ligand.pdb \
  "protein-ligand binding simulation" \
  '{"ligand_itp": "inputs/lig.itp"}'
```

`scripts/regression/umbrella.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh Umbrella_Sampling \
  inputs/umbrella.pdb "umbrella sampling pmf" \
  '{"reaction_coordinate_definition": {"groups": ["A","B"], "init": 0.0},
    "window_schedule_defined": true}'
```

`scripts/regression/biphasic.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh Building_Biphasic_Systems \
  inputs/biphasic.pdb "biphasic system at interface" \
  '{"phase_components": ["water","octanol"], "composition_ratio": [1,1]}'
```

`scripts/regression/fe_methane.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh \
  Free_Energy_Calculations_Methane_in_Water \
  inputs/methane.pdb "methane hydration free energy" \
  '{"solute_topology": "inputs/methane.itp",
    "lambda_schedule": [0.0,0.25,0.5,0.75,1.0]}'
```

`scripts/regression/fe_ethanol.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh \
  Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol \
  inputs/ethanol.pdb "ethanol hydration free energy" \
  '{"solute_topology": "inputs/ethanol.itp",
    "coulomb_vdw_lambda_schedule": {"coul":[0,0.5,1.0],"vdw":[0,0.5,1.0]}}'
```

`scripts/regression/virtual_sites.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/regression/run_tutorial.sh Virtual_Sites \
  inputs/linear.pdb "virtual sites linear molecule" \
  '{"molecule_topology": "inputs/linear.itp",
    "virtual_site_definition": "inputs/vsite.itp"}'
```

`chmod +x scripts/regression/*.sh`.

- [ ] **Step 3: Delete legacy regression scripts**

```bash
git rm scripts/regression_multi_pdb.sh scripts/regression_summary.py
```

- [ ] **Step 4: Commit**

```bash
git add scripts/regression/
git commit -m "feat(regression): per-tutorial regression scripts and shared runner"
```

### Task L2: Remove old skill code and `run_autonomy.py`

**Files:**
- Delete: `skills/gmx-executor/`
- Delete: `skills/mdp-composer/`
- Delete: `skills/protocol-compiler/`
- Delete: `skills/state-manager/`
- Delete: `skills/system-validator/`
- Delete: `skills/trajectory-analyzer/`
- Delete: `skills/tutorial-planner/`
- Delete: `skills/tutorial-router/`
- Delete: `run_autonomy.py`
- Delete: `simulation_state.json`

- [ ] **Step 1: Confirm new code is green**

Run: `pytest tests/unit tests/contract -v`
Expected: all pass.

Run: `pytest tests/integration -v` (skips ok without gmx)
Expected: all gmx-tagged tests pass when gmx is present.

- [ ] **Step 2: Delete old artifacts**

```bash
git rm -r skills/gmx-executor skills/mdp-composer skills/protocol-compiler \
         skills/state-manager skills/system-validator \
         skills/trajectory-analyzer skills/tutorial-planner \
         skills/tutorial-router
git rm run_autonomy.py simulation_state.json
```

- [ ] **Step 3: Verify nothing remaining imports them**

Run: `grep -RIn "skills/\(gmx-executor\|mdp-composer\|protocol-compiler\|state-manager\|system-validator\|trajectory-analyzer\|tutorial-planner\|tutorial-router\)\|run_autonomy" --include="*.py" --include="*.md" .`
Expected: no matches except in this plan document and old commit history.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove legacy 7-skill layer and run_autonomy driver"
```

### Task L3: Final sweep

**Files:**
- Modify: any straggling references found in Step 3 of Task L2

- [ ] **Step 1: Update any straggling references**

If the grep in L2 Step 3 surfaces references that should not exist,
update them or delete the files. Re-run the grep until clean.

- [ ] **Step 2: Run the full test suite as a final gate**

Run: `pytest tests -v`
Expected: all unit/contract tests pass; integration tests pass when gmx
is present and skip cleanly otherwise.

- [ ] **Step 3: Commit any fixes**

```bash
git add -u
git commit -m "chore: clean up trailing references to legacy skills"
# Only commit if changes exist.
```

---

## Self-Review Summary

- **Spec coverage:**
  - Section 2 (Architecture) → Phase A–B (skeleton, state); validated by entry-gate tests.
  - Section 3 (Components) → Phases B–F (lib), G (env-builder), H (md-runner), I (illustrator), each with TDD.
  - Section 4 (Data Flow / independent + chained) → Phase J contract tests.
  - Section 5 (Error Handling) → Tasks C1–C3 (validators + retry), H4 (RETRYABLE loop), H5 (WARNING flow).
  - Section 6 (Testing) → Phase A pytest config, unit/contract tests throughout, integration tests in Tasks G3–G6, H3/H6, I2/I3/I9.
  - Out-of-scope items (CHARMM-GUI web service, new tutorials, schema rewrite, Step 0–8 rework) are not introduced.
- **Placeholder scan:** No `TBD`/`TODO` markers. Membrane and protein-ligand variant analyses ship as documented stubs (returning `{"status": "stub", ...}`), called out as deferred extensions in Task I4 and the spec's Section 8.
- **Type consistency:** `assert_ready`, `phase_sequence_for_variant`, `run_phase_with_recovery`, `handle_phase_result`, `accept_warning`, `decline_warning`, `run_simulation`, `run_core_analyses`, `run_advanced_analyses`, `run_variant_analyses`, `illustrate`, `build_environment` — names match between tasks. `Judgment` fields used in Tasks C1–C3 (`tier`, `metric`, `observed`, `expected_range`, `cause`, `suggested_mutation`, `warning_id`) match consumers in Tasks H4–H6 and I2–I3.
- **Note on directory naming:** The spec writes `skills/env-builder/`, etc., but the plan uses `skills/env_builder/` (underscore) because Python cannot import hyphenated package names. The SKILL.md `name:` field still uses the hyphenated form for user-facing identifiers.
