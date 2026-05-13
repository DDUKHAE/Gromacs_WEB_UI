---
name: state-manager
description: >-
  현재 시뮬레이션의 상태(최신 구조 파일명, 토폴로지 상태, 하드웨어 스펙 등)를 추적하고 업데이트합니다.
  각 시뮬레이션 Step을 완료한 후 호출하여 `simulation_state.json`을 기록해야 합니다.
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: StateManager

긴 시뮬레이션 파이프라인에서 LLM 에이전트가 컨텍스트 창(Context window) 한계나 연결 끊김으로 인해 현재 진행 상황을 잊어버리는 것을 방지하는 상태 관리 스킬입니다.

---

## 1. 역할 및 존재 이유

MD 시뮬레이션 중 생성되는 파일명(`protein_box.gro`, `protein_solv_ions.gro` 등)과 토폴로지 구성은 계속 변합니다.
`StateManager`는 `simulation_state.json` 파일을 작업 디렉토리에 유지하여 "현재 내가 다뤄야 할 최신 파일이 무엇인지" 단일 진실 공급원(Single Source of Truth)을 제공합니다.

---

## 2. 입력 스키마 (Input Schema)

```json
{
  "action": "init | update | read",
  "data": {
    "current_step": 3,
    "latest_gro": "protein_solv.gro",
    "topol_molecules": {"Protein": 1, "SOL": 12500},
    "hardware_specs": {"gpu_count": 1, "cpu_cores": 16}
  }
}
```

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `action` | string | ✅ | `init`(초기화), `update`(부분 갱신), `read`(상태 읽어오기) |
| `data` | object | ❌ | `update` 또는 `init` 시 반영할 상태 데이터 딕셔너리 |

---

## 3. 반환 스키마 (Output Schema)

```json
{
  "status": "success | error",
  "state": {
    "current_step": 3,
    "latest_gro": "protein_solv.gro",
    "topol_molecules": {"Protein": 1, "SOL": 12500},
    "hardware_specs": {"gpu_count": 1, "cpu_cores": 16},
    "last_updated": "2026-05-13T10:00:00Z"
  }
}
```

---

## 4. 호출 시점 및 사용법

1. **초기화 (Step 0):** 파이프라인 시작 전 `gmx hardware` 결과를 파싱하여 `hardware_specs`와 함께 `init`을 호출합니다.
2. **상태 갱신 (각 Step 완료 시):** `gmx solvate`가 끝나면 `latest_gro`를 업데이트하고, `SystemValidator` PASS 후 진행도를 갱신합니다.
3. **상태 복구 (세션 재시작/에러 복구 시):** 에이전트가 컨텍스트를 잃었거나 다시 시작될 때, 아무런 데이터 없이 `action: "read"`로 호출하여 마지막 상태를 복원합니다.
