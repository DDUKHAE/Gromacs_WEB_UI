# JCIM Submission Roadmap — GROMACS Web UI

> Target journal: **Journal of Chemical Information and Modeling (JCIM)** — "New Software" section  
> Submission window target: **8 weeks from 2026-07-07**

---

## Overview

This document is the authoritative priority roadmap for preparing the GROMACS Web UI for JCIM submission. It covers four sequential phases, with Phases 2 and 3 running in parallel. Each phase lists:
- **목표 (Goal):** what must be done
- **필요한 결과물 (Required deliverables):** what the journal/reviewer expects
- **결과 추출 방법 (Extraction method):** exact commands, scripts, and metrics
- **코드 개선 사항 (Code improvements):** what must change in the codebase

---

## Phase 1 — Infrastructure & Code Quality (Weeks 1–2)

**Goal:** Make the codebase reproducible, citable, and clean before running any experiments.

### 1-1. GitHub Actions CI

**Deliverable:** Green CI badge on README; all 22+ tests pass on every push.

**Code improvement — create `.github/workflows/ci.yml`:**

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[test]"
      - run: pytest tests/ -v --tb=short
```

**Extraction method:** After workflow runs, capture badge URL:

```
https://github.com/<org>/<repo>/actions/workflows/ci.yml/badge.svg
```

Add to `README.md`:

```markdown
[![CI](https://github.com/<org>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<org>/<repo>/actions/workflows/ci.yml)
```

**Verification command:**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -5
# Expected: N passed in X.XXs
```

---

### 1-2. Zenodo DOI Registration

**Deliverable:** Persistent DOI for the software (required for JCIM data availability statement).

**Steps:**

1. Create `.zenodo.json` in repo root:

```json
{
  "title": "GROMACS Web UI: An LLM-Guided Web Interface for Autonomous MD Simulation",
  "description": "A FastAPI + vanilla JS web application that uses LLMs (Claude, Codex, Gemini) to autonomously execute GROMACS simulation tutorials via a skills-based pipeline.",
  "upload_type": "software",
  "license": "MIT",
  "keywords": ["GROMACS", "molecular dynamics", "LLM", "web interface", "CHARMM-GUI"],
  "creators": [{"name": "Author, Name", "affiliation": "Institution"}],
  "related_identifiers": []
}
```

2. Go to zenodo.org → Link GitHub repository → Enable automatic DOI on release.
3. Create a GitHub Release (v0.1.0) → Zenodo auto-mints DOI.
4. Add Zenodo badge to `README.md`.

**Extraction method:** After release, Zenodo provides DOI in format `10.5281/zenodo.XXXXXXX`. Record in `CITATION.cff`:

```yaml
cff-version: 1.2.0
title: GROMACS Web UI
doi: 10.5281/zenodo.XXXXXXX
version: 0.1.0
date-released: 2026-07-XX
```

---

### 1-3. PDB Preprocessor Fix

**Deliverable:** `lib/pdb_preprocessor.py` correctly pads residue names to exactly 3 PDB columns.

**Current code** (`lib/pdb_preprocessor.py:22`):

```python
new_name = his_states[key][:3]  # HSD, HSE, or HSP — truncates but doesn't pad
```

**Fix:**

```python
new_name = his_states[key][:3].ljust(3)  # ensures exactly 3 chars for PDB column alignment
```

Note: HSD/HSE/HSP are all 3-char names so this is a defensive correctness fix, not urgent for immediate runs.

**Verification:**

```bash
pytest tests/test_pdb_preprocessor.py -v
# All 8 tests must pass
```

---

### 1-4. Architecture Diagram (Figure 1)

**Deliverable:** Publication-quality Figure 1 showing system architecture.

**Content to illustrate:**

```
User Browser
  ├── Upload PDB / select tutorial
  ├── System Builder UI (force field, box, protonation, membrane, ligand)
  └── NGL Viewer (3D structure)
       ↓ POST /api/runs (pdb_file, tutorial_id, llm, auto_approve)
FastAPI Server (web/server.py)
  ├── system_config.json validation (lib/system_config.py)
  ├── PROPKA preprocessing (lib/protonation.py + lib/pdb_preprocessor.py)
  └── Skill dispatcher
       ↓ env-builder (Steps 0–5) → md-runner (Steps 6–7) → illustrator (Step 8 / "viz")
LLM CLI (claude / codex / gemini)
  ├── Reads: tutorial docs, system_config constraints, GROMACS error logs
  └── Generates: gmx commands per step
GROMACS binary (local/HPC)
  └── Outputs: .gro, .top, .tpr, .xtc, .edr
```

**Tool:** Draw in draw.io / Inkscape, export as 300 DPI PNG + SVG.  
**Saved to:** `docs/figures/fig1_architecture.svg`

---

### Phase 1 Exit Criteria

| Item | Check |
|------|-------|
| CI badge green on README | ✓ |
| Zenodo DOI minted | ✓ |
| `ljust(3)` fix merged | ✓ |
| All 22 tests passing in CI | ✓ |
| Figure 1 draft complete | ✓ |

---

## Phase 2 — Experimental Benchmarking (Weeks 3–7)

**Goal:** Run 72 LLM experiments (8 tutorials × 3 LLMs × 3 runs) and validate physical correctness for Lysozyme and FEP tutorials. This is the core evidence for Table 1 and the JCIM "Results" section.

### 2-1. Experiment Matrix

LLM 어댑터 키 (실제 `web/llm_adapters/__init__.py`): `"claude"`, `"codex"`, `"gemini"`  
`codex` 어댑터는 OpenAI Codex CLI를 통해 GPT 계열 모델을 호출합니다. 논문에서는 정확한 모델 버전을 명시하고 재현성을 위해 버전을 고정해야 합니다 (2-1a 참고).

| Tutorial | LLMs tested | Runs per LLM | Total |
|----------|------------|--------------|-------|
| Lysozyme_in_water | claude, codex, gemini | 3 | 9 |
| KALP15_in_DPPC | claude, codex, gemini | 3 | 9 |
| Protein_Ligand_Complex | claude, codex, gemini | 3 | 9 |
| Umbrella_Sampling | claude, codex, gemini | 3 | 9 |
| Building_Biphasic_Systems | claude, codex, gemini | 3 | 9 |
| Free_Energy_Calculations_Methane_in_Water | claude, codex, gemini | 3 | 9 |
| Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol | claude, codex, gemini | 3 | 9 |
| Virtual_Sites | claude, codex, gemini | 3 | 9 |
| **Total** | | | **72** |

#### 2-1a. LLM 버전 고정 (재현성 필수)

실험 전에 각 CLI 버전을 기록합니다:

```bash
mkdir -p docs/results
claude --version 2>&1 | tee  docs/results/llm_versions.txt
codex  --version 2>&1 | tee -a docs/results/llm_versions.txt
gemini --version 2>&1 | tee -a docs/results/llm_versions.txt
```

논문 Methods 섹션에 이 버전들을 명시합니다. 모든 72 실험은 동일 버전으로 수행해야 합니다.

---

### 2-2. Benchmark Runner Script

**실제 API 계약** (`web/server.py:425–435`):
- 업로드 필드명: `pdb_file` (multipart)
- Form 파라미터: `tutorial_id`, `llm`, `auto_approve` (기본값 `"false"`)
- `auto_approve="true"` 없이 실행하면 파이프라인이 승인 게이트에서 멈춥니다 → 전체 실험 무한 대기
- 완료 상태값 (`web/run_reader.py:derive_status()`): `pending / running / aborted / failed / paused / completed`
  - `completed` = exit code 0 + `last_completed_stage == "viz"` (illustrator 단계까지 완주)
  - `error` 상태는 존재하지 않습니다
- `elapsed_s` 필드는 서버 응답에 없으므로 클라이언트 측에서 `time.time()`으로 측정합니다

**Code improvement — create `scripts/run_benchmark.py`:**

```python
#!/usr/bin/env python3
"""Run all 72 benchmark experiments via the Web UI API.

Usage:
    python scripts/run_benchmark.py \
        --base-url http://localhost:8000 \
        --llm claude \
        --runs-per-tutorial 3 \
        --output-dir benchmark_results/claude_2026-07-15/
"""
import argparse
import json
import time
import requests
from pathlib import Path

TUTORIALS = [
    "Lysozyme_in_water",
    "KALP15_in_DPPC",
    "Protein_Ligand_Complex",
    "Umbrella_Sampling",
    "Building_Biphasic_Systems",
    "Free_Energy_Calculations_Methane_in_Water",
    "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol",
    "Virtual_Sites",
]

# Terminal states per web/run_reader.py:derive_status()
# "error" 상태는 없음; paused·aborted도 프로세스가 종료된 상태
_TERMINAL_STATES = {"completed", "failed", "aborted", "paused"}

POLL_INTERVAL_S = 30


def run_experiment(base_url: str, tutorial_id: str, llm: str, pdb_path: Path) -> dict:
    start = time.time()

    # 필드명은 pdb_file (server.py:427의 UploadFile = File(...) 파라미터명)
    with open(pdb_path, "rb") as f:
        r = requests.post(
            f"{base_url}/api/runs",
            files={"pdb_file": (pdb_path.name, f, "application/octet-stream")},
            data={
                "tutorial_id": tutorial_id,
                "llm": llm,
                "auto_approve": "true",  # 없으면 승인 게이트에서 무한 대기
            },
        )
    r.raise_for_status()
    run_id = r.json()["run_id"]

    # 완료될 때까지 폴링
    while True:
        status_r = requests.get(f"{base_url}/api/runs/{run_id}")
        status_r.raise_for_status()
        state = status_r.json()
        if state["status"] in _TERMINAL_STATES:
            break
        time.sleep(POLL_INTERVAL_S)

    elapsed_s = time.time() - start
    return {
        "run_id": run_id,
        "status": state["status"],
        "tutorial_id": tutorial_id,
        "llm": llm,
        "last_completed_stage": state.get("last_completed_stage"),
        "last_step": state.get("current_step"),
        "elapsed_s": round(elapsed_s, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--llm", required=True, choices=["claude", "codex", "gemini"])
    ap.add_argument("--runs-per-tutorial", type=int, default=3)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--pdb-dir", default="tutorial_data",
                    help="Directory containing <tutorial_id>/input.pdb files")
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = []

    for tutorial in TUTORIALS:
        pdb = Path(args.pdb_dir) / tutorial / "input.pdb"
        if not pdb.exists():
            print(f"SKIP {tutorial}: no input.pdb at {pdb}")
            continue
        for run_num in range(1, args.runs_per_tutorial + 1):
            print(f"Running {tutorial} / {args.llm} / run {run_num}...")
            try:
                r = run_experiment(args.base_url, tutorial, args.llm, pdb)
            except Exception as exc:
                r = {"run_id": None, "status": "api_error", "tutorial_id": tutorial,
                     "llm": args.llm, "error": str(exc), "elapsed_s": 0}
            r["run_num"] = run_num
            results.append(r)
            safe_name = tutorial.replace("/", "_")
            (out / f"{safe_name}_{args.llm}_run{run_num}.json").write_text(
                json.dumps(r, indent=2)
            )
            print(f"  -> {r['status']} in {r['elapsed_s']}s")

    (out / "summary.json").write_text(json.dumps(results, indent=2))
    completed = sum(1 for r in results if r["status"] == "completed")
    print(f"Done. {completed}/{len(results)} completed. Results in {out}/")


if __name__ == "__main__":
    main()
```

**Run commands (one per LLM):**

```bash
# Start the server first
python main.py &
sleep 5  # wait for startup

# Run for each LLM (실제 어댑터 키 사용)
python scripts/run_benchmark.py --llm claude  --output-dir benchmark_results/claude_$(date +%Y%m%d)/
python scripts/run_benchmark.py --llm codex   --output-dir benchmark_results/codex_$(date +%Y%m%d)/
python scripts/run_benchmark.py --llm gemini  --output-dir benchmark_results/gemini_$(date +%Y%m%d)/
```

---

### 2-3. Metrics Extraction Script

**Code improvement — create `scripts/collect_metrics.py`:**

```python
#!/usr/bin/env python3
"""Extract ACR, step failures, and timing from benchmark run directories.

Usage:
    python scripts/collect_metrics.py \
        --results-dir benchmark_results/ \
        --output docs/results/table1.csv
"""
import argparse
import csv
import json
from pathlib import Path
from collections import defaultdict

TUTORIALS = [
    "Lysozyme_in_water", "KALP15_in_DPPC", "Protein_Ligand_Complex",
    "Umbrella_Sampling", "Building_Biphasic_Systems",
    "Free_Energy_Calculations_Methane_in_Water",
    "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol",
    "Virtual_Sites",
]
# 실제 어댑터 키 (web/llm_adapters/__init__.py)
LLMS = ["claude", "codex", "gemini"]


def acr(results: list[dict]) -> float:
    """Autonomous Completion Rate = fraction with status='completed'."""
    if not results:
        return float("nan")
    return sum(1 for r in results if r["status"] == "completed") / len(results)


def mean_elapsed_min(results: list[dict]) -> str:
    # elapsed_s는 run_benchmark.py에서 클라이언트 측 time.time()으로 기록됨
    vals = [r["elapsed_s"] for r in results if isinstance(r.get("elapsed_s"), (int, float))]
    if not vals:
        return "N/A"
    return f"{sum(vals) / len(vals) / 60:.1f}"


def first_fail_step(results: list[dict]) -> str:
    counts: dict[int, int] = defaultdict(int)
    for r in results:
        if r["status"] != "completed" and r.get("last_step") is not None:
            counts[int(r["last_step"])] += 1
    if not counts:
        return "-"
    return str(dict(sorted(counts.items())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--output", default="docs/results/table1.csv")
    args = ap.parse_args()

    rows = []
    results_dir = Path(args.results_dir)

    for tutorial in TUTORIALS:
        row = {"tutorial": tutorial}
        safe = tutorial.replace("/", "_")
        for llm in LLMS:
            files = sorted(results_dir.glob(f"**/{safe}_{llm}_run*.json"))
            runs = [json.loads(f.read_text()) for f in files]
            row[f"{llm}_acr"] = f"{acr(runs):.2f}" if runs else "N/A"
            row[f"{llm}_n"] = len(runs)
            row[f"{llm}_elapsed_min"] = mean_elapsed_min(runs)
            row[f"{llm}_fail_steps"] = first_fail_step(runs)
        rows.append(row)

    fieldnames = (
        ["tutorial"] +
        [f"{llm}_{m}" for llm in LLMS for m in ["acr", "n", "elapsed_min", "fail_steps"]]
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Table 1 data written to {args.output}")


if __name__ == "__main__":
    main()
```

**Run command:**

```bash
python scripts/collect_metrics.py \
    --results-dir benchmark_results/ \
    --output docs/results/table1.csv
```

**Expected output (Table 1 skeleton):**

| Tutorial | Claude ACR | Codex ACR | Gemini ACR |
|----------|-----------|----------|-----------|
| Lysozyme_in_water | X.XX | X.XX | X.XX |
| KALP15_in_DPPC | X.XX | X.XX | X.XX |
| ... | | | |

---

### 2-4. Lysozyme Physical Validation

**Deliverable:** RMSD, Radius of Gyration, and potential energy plots for a completed Lysozyme run. These become Figure 2 in the paper.

**Prerequisites:** A completed Lysozyme run at `runs/<run_id>/` (status = `"completed"`, `last_completed_stage == "viz"`).

**Extraction commands (run inside the workspace):**

```bash
WORKSPACE=runs/<run_id>
cd $WORKSPACE

# 1. Remove periodic boundary conditions
gmx trjconv -s md.tpr -f md.xtc -o md_noPBC.xtc -pbc mol -center << 'EOF'
1
0
EOF

# 2. RMSD vs. initial structure (backbone)
gmx rms -s md.tpr -f md_noPBC.xtc -o rmsd_backbone.xvg -tu ns << 'EOF'
4
4
EOF
# Column 2 = RMSD in nm. Acceptable range for lysozyme: 0.1–0.3 nm plateau

# 3. Radius of Gyration
gmx gyrate -s md.tpr -f md_noPBC.xtc -o gyrate.xvg << 'EOF'
1
EOF
# Column 2 = Rg in nm. Lysozyme reference: ~1.39 nm (PDB 1AKI)

# 4. Potential energy
gmx energy -f ener.edr -o potential.xvg << 'EOF'
10
0
EOF
# Verify equilibration: energy should plateau within first 100 ps NVT/NPT
```

**Plotting (create `scripts/plot_validation.py`):**

```python
#!/usr/bin/env python3
"""Plot RMSD, Rg, and energy from GROMACS .xvg files.

Usage:
    python scripts/plot_validation.py \
        --rmsd runs/<id>/rmsd_backbone.xvg \
        --rg   runs/<id>/gyrate.xvg \
        --energy runs/<id>/potential.xvg \
        --output docs/figures/fig2_lysozyme_validation.pdf
"""
import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_xvg(path: str) -> tuple[list[float], list[float]]:
    x, y = [], []
    with open(path) as f:
        for line in f:
            if line.startswith(("#", "@")):
                continue
            parts = line.split()
            if len(parts) >= 2:
                x.append(float(parts[0]))
                y.append(float(parts[1]))
    return x, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rmsd", required=True)
    ap.add_argument("--rg", required=True)
    ap.add_argument("--energy", required=True)
    ap.add_argument("--output", default="fig2_lysozyme.pdf")
    args = ap.parse_args()

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))

    t_rmsd, rmsd = read_xvg(args.rmsd)
    axes[0].plot(t_rmsd, [v * 10 for v in rmsd], color="steelblue")  # nm→Å
    axes[0].set_xlabel("Time (ns)")
    axes[0].set_ylabel("RMSD (Å)")
    axes[0].set_title("Backbone RMSD")

    t_rg, rg = read_xvg(args.rg)
    axes[1].plot(t_rg, rg, color="darkorange")
    axes[1].set_xlabel("Time (ns)")
    axes[1].set_ylabel("Rg (nm)")
    axes[1].set_title("Radius of Gyration")

    t_e, energy = read_xvg(args.energy)
    axes[2].plot(t_e, energy, color="seagreen", linewidth=0.5)
    axes[2].set_xlabel("Time (ps)")
    axes[2].set_ylabel("Potential Energy (kJ/mol)")
    axes[2].set_title("Potential Energy")

    plt.tight_layout()
    plt.savefig(args.output, dpi=300)
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
```

**Run:**

```bash
pip install matplotlib
python scripts/plot_validation.py \
    --rmsd runs/<id>/rmsd_backbone.xvg \
    --rg   runs/<id>/gyrate.xvg \
    --energy runs/<id>/potential.xvg \
    --output docs/figures/fig2_lysozyme_validation.pdf
```

**Acceptance criteria:**
- RMSD plateau: 0.1–0.3 nm (1–3 Å) after 1 ns
- Rg stable: ±0.02 nm around ~1.39 nm
- Energy: converged within 100 ps of each phase (NVT, NPT)

---

### 2-5. FEP Validation (Methane Hydration Free Energy)

**Deliverable:** ΔG_hyd for methane in water, compared to experimental value (−2.0 kcal/mol) and prior GROMACS results.

**Prerequisites:** Completed `Free_Energy_Calculations_Methane_in_Water` run (status = `"completed"`).

**Extraction commands:**

```bash
WORKSPACE=runs/<fep_run_id>
cd $WORKSPACE

# Collect all dhdl files (one per lambda window)
ls dhdl.*.xvg

# Run BAR (Bennett Acceptance Ratio) analysis
gmx bar -f dhdl.*.xvg -o bar.xvg -oi barint.xvg -oh histogram.xvg 2>&1 | tee bar_output.txt

# Extract total ΔG from bar_output.txt
grep "total" bar_output.txt
# Expected: total ~−8.4 kJ/mol (≈ −2.0 kcal/mol)

# Convert: kJ/mol → kcal/mol = divide by 4.184
python3 -c "print(f'{-8.4 / 4.184:.2f} kcal/mol')"
```

**Acceptance criteria:**

| Source | ΔG_hyd (methane) |
|--------|-----------------|
| Experimental | −2.0 kcal/mol |
| This work (target) | −2.0 ± 0.5 kcal/mol |
| Reference: Shirts & Pande (2005) | −2.14 kcal/mol |

If result falls outside ±1 kcal/mol of experimental, inspect lambda spacing and equilibration.

---

### 2-6. ACR 정의 명확화 (논문 서술 지침)

**ACR의 정확한 의미:** `status == "completed"` = LLM이 illustrator(Step 8, viz stage)까지 파이프라인을 완주한 비율.  
이는 "과학적 정확성"이 아니라 "자율 완주율"입니다. 논문에서 이를 명확히 구분해야 합니다:

- **Methods 섹션:** "ACR은 LLM이 사용자 개입 없이 Step 8까지 완주한 실험의 비율로 정의한다. 물리적 정확성은 Lysozyme(RMSD/Rg/energy)과 FEP 메탄(ΔG_hyd)에 대해 별도로 검증한다."
- **Results 섹션:** ACR (Table 1)과 물리 검증 (Figure 2, Figure 3/Table 2)을 별도 subsection으로 분리.
- n=3은 통계적 주장에는 작으므로 "성공/실패 분산"을 함께 보고: e.g., "Claude achieved ACR = 1.00 ± 0.00 for Lysozyme (3/3 runs)."

---

### 2-7. Error Recovery Case Study

**Deliverable:** Table S1 in Supporting Information — documented cases where the LLM recovered from GROMACS errors without user intervention.

**Extraction method:**

```bash
# runner.log에서 재시도 패턴 추출
grep -n "retry\|Retry\|RETRY\|Error\|error\|Failed\|failed" runs/<run_id>/runner.log \
    | head -100 > docs/results/error_recovery_cases.txt

# state.json의 retry_history 파싱
python3 - << 'EOF'
import json, pathlib
for p in sorted(pathlib.Path("runs").glob("*/state.json")):
    s = json.loads(p.read_text())
    for step_key, data in s.get("steps", {}).items():
        history = data.get("retry_history", [])
        if history:
            print(f"{p.parent.name}  step={step_key}  retries={len(history)}")
            for h in history:
                print(f"  cause: {h.get('cause', '?')}")
                print(f"  action: {h.get('remediation', '?')}")
EOF
```

**Document 3–5 representative cases in the paper:**

| Case ID | Tutorial | Step | Error | LLM Recovery Action | Outcome |
|---------|----------|------|-------|--------------------|-|
| E1 | Lysozyme | 3 | `gmx solvate: no molecules found` | Added `-cs spc216.gro` flag | Success |
| E2 | KALP15 | 5 | `Fatal error: charge imbalance` | Adjusted ion count manually | Success |
| ... | | | | | |

---

### Phase 2 Exit Criteria

| Item | Check |
|------|-------|
| 72 experiment JSON files collected | ✓ |
| `table1.csv` generated with ACR per tutorial per LLM | ✓ |
| Lysozyme RMSD/Rg/energy plots created (Figure 2) | ✓ |
| FEP ΔG_hyd within ±1 kcal/mol of experimental | ✓ |
| ≥3 error recovery cases documented | ✓ |
| LLM versions recorded in `docs/results/llm_versions.txt` | ✓ |

---

## Phase 3 — Paper Draft (Weeks 3–7, parallel with Phase 2)

**Goal:** Draft the JCIM "New Software" manuscript while experiments run.

### 3-1. Manuscript Structure

**Target length:** 5,000–8,000 words (New Software section typical range).  
**Saved to:** `docs/paper/manuscript.docx` (JCIM requires Word submission).

**Section outline:**

```
1. Introduction (700 words)
   - MD simulation workflow complexity
   - Existing tools: CHARMM-GUI (strength: GUI, weakness: no automation),
     GROMACS user guide (strength: complete, weakness: manual)
   - Gap: no tool provides end-to-end LLM-guided autonomous execution
   - This work: GROMACS Web UI fills this gap

2. Methods (1500 words)
   2.1 System Architecture (reference Figure 1)
   2.2 LLM Integration Layer (system_config.json, constraint injection)
       - Three LLM CLI adapters: Claude, Codex (OpenAI), Gemini
       - Exact CLI versions and model IDs (from docs/results/llm_versions.txt)
   2.3 Skills-Based Pipeline (env-builder Steps 0–5, md-runner Steps 6–7, illustrator Step 8)
   2.4 Tutorial Coverage (8 systems, Table S1 in SI)
   2.5 Protonation Preprocessing (PROPKA + HIS renaming)
   2.6 Benchmark Protocol (72 experiments, ACR definition, auto_approve mode)

3. Results (2000 words)
   3.1 Autonomous Completion Rate (Table 1) — defined as "pipeline completion to viz stage"
   3.2 Physical Validation — Lysozyme (Figure 2: RMSD, Rg, Energy)
   3.3 Physical Validation — FEP Methane (Figure 3 or Table 2: ΔG_hyd)
   3.4 Error Recovery Analysis (Table S1 in SI, 2–3 cases in main text)
   3.5 Comparison with Manual Execution (wall-clock time, user actions required)

4. Discussion (1000 words)
   4.1 LLM capability differences (Claude vs Codex vs Gemini)
   4.2 Failure modes and limitations
   4.3 Reproducibility considerations (LLM stochasticity, n=3 per cell)
   4.4 ACR vs. scientific correctness: distinction and validation approach
   4.5 Roadmap: GPU cluster support, additional force fields

5. Conclusions (200 words)

6. Data Availability
   - Code: GitHub + Zenodo DOI
   - Benchmark results: Zenodo data deposit (all 72 run JSONs)

7. Supporting Information
   - Table S1: All 72 run outcomes (run_id, status, elapsed_min, fail_step)
   - Table S2: Tutorial descriptions and input requirements
   - Figure S1: FEP lambda spacing and convergence
   - Figure S2: KALP15 membrane validation (if available)
```

---

### 3-2. Table 1 (ACR Matrix) — Final Format

Generated from `docs/results/table1.csv` via `scripts/format_table1.py`:

```python
#!/usr/bin/env python3
"""Format table1.csv as Markdown for the paper.

Usage:
    python scripts/format_table1.py --input docs/results/table1.csv
"""
import argparse
import csv

TUTORIAL_SHORT = {
    "Lysozyme_in_water": "Lysozyme in water",
    "KALP15_in_DPPC": "KALP15 in DPPC",
    "Protein_Ligand_Complex": "Protein–ligand complex",
    "Umbrella_Sampling": "Umbrella sampling",
    "Building_Biphasic_Systems": "Biphasic system",
    "Free_Energy_Calculations_Methane_in_Water": "FEP: methane (water)",
    "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol": "FEP: ethanol (water)",
    "Virtual_Sites": "Virtual sites",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="docs/results/table1.csv")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.input)))

    # 실제 어댑터 키: claude / codex / gemini
    print("| Tutorial | Claude ACR | Codex ACR | Gemini ACR |")
    print("|----------|-----------|----------|-----------|")
    for r in rows:
        name = TUTORIAL_SHORT.get(r["tutorial"], r["tutorial"])
        print(f"| {name} | {r['claude_acr']} | {r['codex_acr']} | {r['gemini_acr']} |")


if __name__ == "__main__":
    main()
```

**Run:**

```bash
python scripts/format_table1.py --input docs/results/table1.csv
```

---

### Phase 3 Exit Criteria

| Item | Check |
|------|-------|
| All 5 sections drafted | ✓ |
| Table 1 formatted from real data (claude/codex/gemini) | ✓ |
| Figure 2 (Lysozyme) final version at 300 DPI | ✓ |
| Figure 3 (FEP) final version at 300 DPI | ✓ |
| Comparison with CHARMM-GUI written in Discussion | ✓ |
| ACR definition (completion rate, not accuracy) explicit in Methods | ✓ |
| LLM model versions stated in Methods | ✓ |

---

## Phase 4 — Final Submission Preparation (Week 8)

**Goal:** Polish manuscript and submit to JCIM.

### 4-1. Supporting Information (SI)

**File:** `docs/paper/supporting_information.pdf`

**Table S1 — All 72 runs:**

```bash
# Generate Table S1 from benchmark JSON files
python3 - << 'EOF' > docs/results/table_s1_all_runs.csv
import json, pathlib, csv, sys

rows = []
for f in sorted(pathlib.Path("benchmark_results").glob("**/*_run*.json")):
    r = json.loads(f.read_text())
    elapsed_min = f"{r.get('elapsed_s', 0)/60:.1f}" if r.get("elapsed_s") else "N/A"
    rows.append({
        "tutorial": r["tutorial_id"],
        "llm": r["llm"],
        "run": r["run_num"],
        "status": r["status"],
        "elapsed_min": elapsed_min,
        "last_completed_stage": r.get("last_completed_stage", "-"),
        "fail_step": r.get("last_step", "-") if r["status"] != "completed" else "-",
    })

w = csv.DictWriter(
    sys.stdout,
    fieldnames=["tutorial","llm","run","status","elapsed_min","last_completed_stage","fail_step"]
)
w.writeheader()
w.writerows(rows)
EOF
```

**Figure S1 — FEP convergence plot:**

```bash
# After FEP run completes
gmx bar -f runs/<fep_id>/dhdl.*.xvg -o bar.xvg -oi barint.xvg 2>&1
# Plot barint.xvg (cumulative ΔG vs lambda) as Figure S1
python scripts/plot_fep_convergence.py \
    --barint runs/<fep_id>/barint.xvg \
    --output docs/figures/figS1_fep_convergence.pdf
```

---

### 4-2. Cover Letter

**File:** `docs/paper/cover_letter.docx`

**Required elements:**
1. Statement that manuscript is original and not under review elsewhere
2. 2–3 sentences explaining novelty vs. CHARMM-GUI (LLM-guided autonomy, no expert intervention required)
3. Suggested reviewers: 2–3 names from JCIM editorial board with relevant MD/automation expertise
4. Data availability statement: "Code and benchmark data available at `https://github.com/<org>/<repo>` (Zenodo DOI: 10.5281/zenodo.XXXXXXX)"
5. Author contributions (CRediT taxonomy)

---

### 4-3. JCIM Submission Checklist

| Requirement | Status |
|-------------|--------|
| Manuscript in Word format (.docx) | |
| Abstract ≤ 250 words | |
| All figures as separate high-res files (300 DPI TIFF or PDF) | |
| Figure captions included at end of manuscript | |
| Supporting Information as single PDF | |
| All references in ACS format | |
| Zenodo DOI in Data Availability statement | |
| ORCID for all authors | |
| Cover letter uploaded | |
| Suggested reviewers listed (2–3) | |

**Submission portal:** https://pubs.acs.org/journal/jcisd8 → "Submit Manuscript"

---

### Phase 4 Exit Criteria

| Item | Check |
|------|-------|
| Table S1 (all 72 runs) complete | ✓ |
| Cover letter drafted | ✓ |
| All figures at 300 DPI | ✓ |
| JCIM submission checklist 100% | ✓ |
| Manuscript submitted | ✓ |

---

## Summary Timeline

```
Week 1–2:  Phase 1 — CI, Zenodo, ljust fix, Figure 1 diagram
Week 3–7:  Phase 2 — 72 experiments (run_benchmark.py, collect_metrics.py)
           Phase 3 — Paper draft (parallel)
Week 8:    Phase 4 — SI, cover letter, submission
```

---

## Code Improvements Summary

| File | Change | Priority |
|------|--------|----------|
| `lib/pdb_preprocessor.py:22` | `[:3]` → `[:3].ljust(3)` (defensive pad) | P2 (before CI) |
| `.github/workflows/ci.yml` | Create GitHub Actions CI | P1 (Week 1) |
| `.zenodo.json` | Create for DOI registration | P1 (Week 1) |
| `CITATION.cff` | Create for software citation | P1 (Week 1) |
| `scripts/run_benchmark.py` | Create experiment runner (API 계약 준수: pdb_file, codex, auto_approve, terminal states) | P1 (Week 3, before experiments) |
| `scripts/collect_metrics.py` | Create ACR/metrics extractor (elapsed_s 클라이언트 측 기록) | P1 (Week 3) |
| `scripts/plot_validation.py` | Create RMSD/Rg/energy plotter | P2 (Week 3) |
| `scripts/format_table1.py` | Create Table 1 formatter | P3 (Week 4) |
| `scripts/plot_fep_convergence.py` | Create FEP convergence plotter | P2 (Week 4) |
| `docs/results/llm_versions.txt` | Record CLI versions before experiments | P1 (Week 3) |
| `requirements.txt` | Add `matplotlib` for plotting scripts | P2 (Week 3) |

---

## Key Metrics for JCIM Acceptance

| Metric | Minimum target | Ideal |
|--------|--------------|-------|
| ACR (best LLM, easiest tutorial) | ≥ 0.67 (2/3) | 1.00 |
| ACR (best LLM, overall) | ≥ 0.50 | ≥ 0.75 |
| Lysozyme RMSD plateau | ≤ 0.3 nm | 0.1–0.2 nm |
| Methane ΔG_hyd error vs. experiment | ≤ 1.0 kcal/mol | ≤ 0.5 kcal/mol |
| Error recovery cases documented | ≥ 3 | ≥ 5 |
| Tutorials covered | 8 | 8 |

---

## API Contract Quick Reference (Phase 2 구현 시 참고)

실제 코드 기준 (`web/server.py`, `web/run_reader.py`):

| 항목 | 실제 값 | 잘못된 가정 |
|------|--------|------------|
| PDB 업로드 필드명 | `pdb_file` | ~~`pdb`~~ |
| LLM 어댑터 키 | `claude`, `codex`, `gemini` | ~~`gpt4o`~~ |
| 자동 승인 파라미터 | `auto_approve="true"` (Form 문자열) | 미전달 시 전 실험 무한 대기 |
| 완료 상태 (`completed`) | exit code 0 + `last_completed_stage == "viz"` | `status == "completed"` 만으로는 불충분 |
| 터미널 상태 집합 | `{completed, failed, aborted, paused}` | ~~`{completed, failed, error}`~~ |
| 소요 시간 | 클라이언트 `time.time()` 측정 | ~~`state["elapsed_s"]` (필드 없음)~~ |
