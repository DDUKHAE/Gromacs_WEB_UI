# Harness Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 하네스를 다중 PDB 반복 작업에 공통 적용 가능한 수준으로 강화하고, 런 간 오염 없이 예측 가능한 실패/복구를 제공한다.

**Architecture:** `run_autonomy.py`를 중심으로 실행 전처리(런 격리/인자 검증), 실행 중 게이트(토폴로지-좌표 일관성, 물리 안정성), 실행 후 리포트(회귀 요약)를 계층화한다. 재시도 엔진은 런타임 플래그 재시도와 물리 파라미터 재시도를 분리해 기록한다.

**Tech Stack:** Python 3, GROMACS CLI, shell regression script, JSON state/report files

---

### Task 1: Run Metadata and Capability Report

**Files:**
- Modify: `run_autonomy.py`
- Test: `scripts/regression_multi_pdb.sh`

- [ ] **Step 1: Write the failing test**

```python
# pseudo-test target behavior
result = run({"prompt":"run standard protein in water MD","pdb_path":"1UBQ.pdb","target_name":"ubq","execute":False})
assert "run_dir" in result
assert "capabilities" in result
assert "validator_loaded" in result["capabilities"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 run_autonomy.py '{"prompt":"run standard protein in water MD","pdb_path":"1UBQ.pdb","target_name":"ubq","execute":false}'`
Expected: `run_dir` 또는 `capabilities`가 없어서 기준 미충족

- [ ] **Step 3: Write minimal implementation**

```python
# run() return payload에 추가
"run_dir": cwd,
"capabilities": {
  "validator_loaded": validate_phase is not None,
  "analyzer_loaded": analyze_trajectory is not None,
  "gmx_bin": gmx_bin,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 run_autonomy.py '{"prompt":"run standard protein in water MD","pdb_path":"1UBQ.pdb","target_name":"ubq","execute":false}'`
Expected: JSON에 `run_dir`, `capabilities` 포함

- [ ] **Step 5: Commit**

```bash
git add run_autonomy.py
git commit -m "feat: include run metadata and capability report"
```

### Task 2: Retry Engine Uniqueness Guard

**Files:**
- Modify: `run_autonomy.py`
- Modify: `skills/gmx-executor/gmx_executor.py`
- Test: `scripts/regression_multi_pdb.sh`

- [ ] **Step 1: Write the failing test**

```python
# pseudo-test target behavior
# same phase retry attempts must produce unique executable command fingerprints
fp1 = command_fingerprint(cmd_attempt_1)
fp2 = command_fingerprint(cmd_attempt_2)
assert fp1 != fp2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `scripts/regression_multi_pdb.sh`
Expected: `Modify parameters before retry to avoid infinite loop.` 재발

- [ ] **Step 3: Write minimal implementation**

```python
# run_autonomy.py retry mutation
# genion/grompp/mdrun 재시도마다 실제 실행 인자(삭제되지 않는 인자) 변경 보장
if cmd_name == "genion" and attempt >= 1:
    mutated["-conc"] = "0.10" if attempt == 1 else "0.15"

if cmd_name == "mdrun" and attempt >= 1:
    mutated["-ntomp"] = str(max(1, 8 - attempt))
    mutated["-pin"] = "off"
    mutated["-nb"] = "cpu" if attempt >= 2 else mutated.get("-nb", "auto")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `scripts/regression_multi_pdb.sh`
Expected: fingerprint dead-end 문구가 최소한 `genion` 경로에서는 사라짐

- [ ] **Step 5: Commit**

```bash
git add run_autonomy.py skills/gmx-executor/gmx_executor.py
git commit -m "fix: guarantee retry fingerprint uniqueness for execution args"
```

### Task 3: Topology/GRO Consistency Gate with Remediation

**Files:**
- Modify: `run_autonomy.py`
- Test: `scripts/regression_multi_pdb.sh`

- [ ] **Step 1: Write the failing test**

```python
# pseudo-test target behavior
# when gro/top mismatch detected after solvate/genion,
# run returns structured gate failure or rollback retry path
assert result["status"] == "error"
assert "Topology/GRO consistency gate failed" in result["result"]["summary"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `scripts/regression_multi_pdb.sh`
Expected: mismatch가 있어도 원인 분류가 불명확하거나 rollback 없이 진행

- [ ] **Step 3: Write minimal implementation**

```python
# run_autonomy.py
# gate 실패 시: retry_history에 gate detail 기록 + topology backup rollback + 단계 재시도 1회
if gate_failed:
    _restore_topol(cwd, topology_backup)
    # annotate retry history with gate diagnostics
```

- [ ] **Step 4: Run test to verify it passes**

Run: `scripts/regression_multi_pdb.sh`
Expected: mismatch 발생 시 원인/복구 시도가 구조화된 형태로 기록됨

- [ ] **Step 5: Commit**

```bash
git add run_autonomy.py
git commit -m "feat: add topology-gro consistency remediation path"
```

### Task 4: NVT Fallback Profile v1 (Physics-First)

**Files:**
- Modify: `skills/mdp-composer/mdp_composer.py`
- Modify: `run_autonomy.py`
- Test: `scripts/regression_multi_pdb.sh`

- [ ] **Step 1: Write the failing test**

```python
# pseudo-test target behavior
# on LINCS/settled/NaN signatures, next retry_count run must use conservative NVT overrides
assert nvt_overrides["dt"] in ["0.0005", "0.0002"]
assert nvt_overrides["tc-grps"] == "System"
assert nvt_overrides["tau_t"] == "0.05"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `scripts/regression_multi_pdb.sh`
Expected: NVT 실패 시 동일/유사 프로파일 재시도

- [ ] **Step 3: Write minimal implementation**

```python
# run_autonomy.py when composing nvt.mdp under fallback
args["__override_dt"] = "0.0005" if retry_count == 1 else "0.0002"
args["__override_tau_t"] = "0.05"
args["__override_nsteps"] = "250000"
args["__override_tc_grps"] = "System"
```

```python
# mdp_composer whitelist + template support
MDP_WHITELIST.add("tc-grps")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `scripts/regression_multi_pdb.sh`
Expected: NVT 실패 후 fallback 파라미터 전환이 로그/상태에서 확인됨

- [ ] **Step 5: Commit**

```bash
git add run_autonomy.py skills/mdp-composer/mdp_composer.py
git commit -m "feat: add conservative NVT fallback profile"
```

### Task 5: Regression Summary Artifact

**Files:**
- Modify: `scripts/regression_multi_pdb.sh`
- Create: `scripts/regression_summary.py`
- Test: `scripts/regression_multi_pdb.sh`

- [ ] **Step 1: Write the failing test**

```python
# pseudo-test target behavior
# /tmp/harness_regression_summary.json should exist and contain 3 entries
with open('/tmp/harness_regression_summary.json') as f:
    data = json.load(f)
assert len(data["cases"]) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `scripts/regression_multi_pdb.sh`
Expected: summary artifact 없음

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/regression_summary.py
# read /tmp/{ubq,crn,aki}_regression.json and write aggregated JSON summary
```

```bash
# scripts/regression_multi_pdb.sh end
python3 scripts/regression_summary.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `scripts/regression_multi_pdb.sh`
Expected: `/tmp/harness_regression_summary.json` 생성

- [ ] **Step 5: Commit**

```bash
git add scripts/regression_multi_pdb.sh scripts/regression_summary.py
git commit -m "feat: add machine-readable regression summary artifact"
```

### Task 6: Plan/Docs Sync

**Files:**
- Modify: `docs/superpowers/specs/2026-05-14-cross-pdb-validation-feedback.md`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

```python
# pseudo-test target behavior
# docs mention per-run isolation and regression summary artifact path
assert "runs/<target>_<timestamp>" in docs_text
assert "/tmp/harness_regression_summary.json" in docs_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rg "harness_regression_summary|runs/<target>_<timestamp>" docs README.md`
Expected: 일부 누락

- [ ] **Step 3: Write minimal implementation**

```markdown
# docs updates
- per-run isolation policy
- regression summary artifact usage
- known failure taxonomy (validation_failed vs execution_failed)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rg "harness_regression_summary|runs/<target>_<timestamp>" docs README.md`
Expected: 관련 문구 모두 검색됨

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-05-14-cross-pdb-validation-feedback.md README.md
git commit -m "docs: sync hardening policy and regression artifact usage"
```
