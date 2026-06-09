# Operational Runbook: Manual Intervention Guide

자율 복구(RETRYABLE 3회)에 실패했거나 사용자의 명시적 결정이 필요한 WARNING 상황에서 따라야 할 절차를 안내한다.

`workspace/state.json`은 `lib/state.py`가 관리하는 single source of truth다.

## 1. WARNING 상황 처리 — 사용자 결정 흐름

skill이 `warning_pending_decision` 상태를 반환하면 즉시 사용자/LLM이 결정을 내려야 한다. 상세 시퀀스는 [`WARNING_FLOW.md`](WARNING_FLOW.md).

요약:

1. `state.pending_warnings[]`의 최신 항목에서 `warning_id`, `metric`, `observed`, `suggested_mutation` 확인.
2. 선택지:
   - **수락(accept)**: 제안된 mutation으로 phase 재실행. skill 재호출 시 `accept_warning_mutation=<warning_id>`.
   - **거부(decline)**: 결정을 영구 기록하고 다음 step 진행. `decline_warning_mutation=<warning_id>`.
3. skill은 결정을 `retry_history`에 `tier:"warning"`으로 기록한다.

비대화형 환경에서 `interactive=False`로 호출하면 WARNING은 자동으로 decline 처리된다.

## 2. 자율 복구(RETRYABLE) 실패 시 점검 항목

### 2.1 로그 분석
- `workspace/state.json.retry_history`의 마지막 엔트리에서 `cause`, `remediation`, `command` 확인.
- `workspace/stage2_md/<phase>.log`를 열어 `Fatal error` 또는 `LINCS warning`을 검색.

### 2.2 Topology mismatch
- **증상**: `gmx grompp` 출력에 `does not match topology` 또는 `moltype.*not found`.
- **원인**: Step 3 또는 Step 5의 topology mutation 후 `.gro`와 `.top`의 분자 수 불일치.
- **해결**:
  1. `workspace/state.json.topology_backups`에서 가장 최근 `.bak` 경로 확인.
  2. `cp stage1_env/topol.top.bak stage1_env/topol.top`로 복원.
  3. `env-builder.run_step3_solvate(workspace)` 또는 `run_step5_genion(workspace, concentration=...)`을 재호출.

### 2.3 온도/압력 발산
- **증상**: `judge_temperature` 또는 `judge_density`가 retryable을 반환하고 3회 mutation 모두 실패.
- **해결**:
  1. `lib/mdp_templates/{nvt,npt}.mdp`의 `tau_t`, `tau_p`, `compressibility` 값을 수동 검토.
  2. `phase_overrides`로 `tau_p`를 더 크게(예: 10.0) 강제.
  3. 초기 구조의 겹침(clash) 가능성을 `gmx check -c <gro>`로 확인.
  4. `emstep`을 줄여 EM을 더 정밀하게 재실행.

### 2.4 LINCS / NaN potential
- **증상**: production 또는 NVT 도중 `LINCS warning`이나 potential NaN 폭주.
- **해결**:
  1. EM이 충분히 수렴했는지 `stage2_md/em.edr`을 `gmx energy`로 점검.
  2. `dt`를 0.001로 줄여 재실행.
  3. 단백질-용매 충돌 가능성: `editconf -d`를 키워 box를 확장.

## 3. 수동 복구 절차

1. **상태 동기화**: 외부에서 직접 명령을 실행해 파일을 생성한 경우 `lib.state.write`로 `state.json`을 갱신한다.
   ```python
   from pathlib import Path
   from lib import state
   s = state.read(workspace_dir)
   s["step_outputs"]["step_7"]["nvt_gro"] = "stage2_md/nvt.gro"
   s["current_step"] = 7
   state.write(workspace_dir, s)
   ```
2. **Skill 재진입**: 적절한 stage marker(`last_completed_stage = "env"` 등)를 설정한 뒤 다음 skill을 호출.
3. **재시도 메타 보존**: `retry_history`는 보존한다. 새 시도가 동일 (command, parameters) 조합이면 `lib.validators.assert_unique_attempt`가 차단하므로 mutation을 반드시 동반.

## 4. 중단 기준

다음 상황에서는 즉시 운용을 멈추고 시스템 설계를 재검토한다.

- GPU/CPU OOM이 mutation 후에도 반복 발생.
- 사용 중인 force field와 PDB 잔기명이 근본적으로 불일치 (예: 비표준 변이 잔기).
- `topol.top.bak` 생성이 권한 문제로 실패.
- `state.json`이 손상되어 `json.load` 실패 (백업/복원 불가).

## 5. Workspace 청소

각 풀-파이프라인은 `runs/<tag>_<timestamp>/`에 격리된 workspace를 생성한다. 디스크 압박 시:

```bash
# 안전 청소: 30일 이상 된 워크스페이스 삭제
find runs -maxdepth 1 -type d -mtime +30 -print -exec rm -rf {} +
```

문제 워크스페이스를 외부에서 분석할 경우 `state.json`, `stage*/`, `*.log`만 보존하면 충분하다.
