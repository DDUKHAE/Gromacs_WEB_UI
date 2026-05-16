# WARNING Decision Flow

`md-runner`가 phase 검증에서 권장 범위 이탈을 감지하면 retryable 자동 mutation 대신 **사용자 결정 분기**(WARNING)를 통과시킨다. 이 문서는 그 end-to-end 시퀀스를 설명한다.

관련 코드:
- 판정: `lib/validators.py::Judgment` (tier=`"warning"`)
- 분기 로직: `skills/md_runner/md_runner.py::handle_phase_result`, `accept_warning`, `decline_warning`
- 검증 기준: [`simulation_criteria.md`](simulation_criteria.md)

## 1. 트리거 조건

phase 종료 후 validator gate가 WARNING tier를 반환하는 경우. 예시:

- NPT 단계 평균 density가 expected_range(995–1005)에서 2% 이내 이탈
- NVT 단계 평균 temperature가 target ± 3K~10K
- Production 단계 energy drift가 0.5~5.0 kJ/mol/ns

## 2. 시퀀스 (interactive=True)

```
LLM/User                       md-runner                       state.json
   │  run_simulation(interactive=True)
   │─────────────────────────────▶│
   │                              │  run_phase("npt")
   │                              │  validator → Judgment(tier="warning", ...)
   │                              │  handle_phase_result()
   │                              │  - pending_warnings.append(payload)
   │                              │─────────────────────────────▶
   │                              │
   │  status="warning_pending_decision"
   │  warning_id, suggested_mutation
   │◀─────────────────────────────│
   │
   │  사용자 결정
   │  - accept: 제안된 mutation 적용 후 phase 재실행
   │  - decline: 결정 기록 후 다음 phase 진행
   │
   │  run_simulation(accept_warning_mutation=<id>)  또는
   │  run_simulation(decline_warning_mutation=<id>)
   │─────────────────────────────▶│
   │                              │  _pop_warning(warning_id)
   │                              │  retry_history.append({tier:"warning", ...})
   │                              │─────────────────────────────▶
   │                              │  (accept) phase_overrides 갱신 후 run_phase 재시도
   │                              │  (decline) 다음 phase로 진행
```

## 3. 페이로드 형식

skill이 반환하는 객체:

```json
{
  "status": "warning_pending_decision",
  "warning_id": "8c5e1f5e-...",
  "payload": {
    "warning_id": "8c5e1f5e-...",
    "step": 7,
    "phase": "npt",
    "metric": "density",
    "observed": 985.2,
    "expected_range": [995, 1005],
    "cause": "pressure_coupling",
    "suggested_mutation": {
      "target": "npt.mdp",
      "changes": {"tau_p": "2.0 → 5.0"},
      "rationale": "barostat coupling too tight; relax tau_p"
    }
  }
}
```

## 4. 사용자 응답

### 수락 (accept)
```python
from skills.md_runner import run_simulation
result = run_simulation(
    workspace_dir=ws,
    accept_warning_id="8c5e1f5e-...",
)
# result == {"status": "warning_accepted", "applied_overrides": {"tau_p": 5.0}}
```

`accept_warning`이 `suggested_mutation.changes`를 파싱해 phase override dict를 반환한다. 호출자는 동일 `phase_overrides`에 이를 합쳐 다시 `run_simulation`을 호출하면 해당 phase가 재실행된다.

### 거부 (decline)
```python
result = run_simulation(
    workspace_dir=ws,
    decline_warning_id="8c5e1f5e-...",
)
# result == {"status": "warning_declined"}
```

`pending_warnings`에서 제거되고 `retry_history`에 `{cause: "user_decline", tier: "warning"}` 엔트리가 기록된다. 사용자가 직접 `run_simulation`을 다시 호출해 남은 phase를 진행한다.

## 5. 비대화형 처리 (interactive=False)

```python
run_simulation(workspace_dir=ws, interactive=False)
```

WARNING이 감지되면 자동으로 decline 처리되고 `retry_history`에 `cause:"auto_decline_noninteractive"`로 기록된다. 회귀 테스트(`scripts/regression/*.sh`)는 이 모드를 사용한다.

## 6. RETRYABLE과의 차이

| 항목 | WARNING | RETRYABLE |
|---|---|---|
| 사용자 결정 필요 | yes (interactive=True) | no |
| Budget 소비 | `retry_history`에 기록되지만 `retryable_budget_remaining` 카운트에는 미포함 | (step, phase)당 3회 한도 |
| 자동 재시도 | accept 시에만 1회 | 매 cause 발생마다 자동 mutation |
| 사용 시점 | 권장 범위에서 살짝 벗어났으나 진행 가능 | 명백한 발산/불안정 |

## 7. 안전 계약

- 동일 (command, parameters) 조합 재시도는 WARNING accept 경로에서도 차단된다 (`lib/validators.assert_unique_attempt`).
- `pending_warnings`에 같은 `warning_id`가 중복 추가되지 않는다.
- skill 호출 시 `accept_warning_mutation`과 `decline_warning_mutation`을 동시에 지정하면 `accept`가 우선한다.

## 8. 디버깅 팁

- `state.pending_warnings`에 항목이 남아있다면 사용자 결정이 누락된 것.
- `retry_history`에서 `tier="warning"` 엔트리를 시간순으로 보면 어떤 phase가 반복 WARNING을 받았는지 확인 가능.
- 같은 phase에 WARNING이 누적되면 임계값을 조정할지 검토 ([`simulation_criteria.md`](simulation_criteria.md) §5 변경 절차).
