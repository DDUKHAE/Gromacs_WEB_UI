# Validation Criteria Reference

`SystemValidator` 스킬이 각 Phase 검증에 사용하는 정량적 기준값 정의.

---

## Phase: `minim` — 에너지 최소화 검증 기준

| 검증 항목 | gmx 명령어 | PASS | WARNING | FAIL |
|---|---|---|---|---|
| 최대 힘 (Fmax) | `gmx energy -f em.edr` | `< 1000 kJ/mol/nm` | `1000–5000` | `> 5000` |
| 퍼텐셜 에너지 | `gmx energy -f em.edr` | 음수이며 단조 감소 | 완만한 진동 | 양수 또는 급등 |

**FAIL 시 권고:**
- `nsteps`를 `50000 → 100000`으로 증가
- `emstep`을 `0.01 → 0.001`로 감소
- 원자 충돌이 의심되면 `pdb2gmx` 단계 재확인

---

## Phase: `nvt` — NVT 평형화 검증 기준

| 검증 항목 | gmx 명령어 | PASS | WARNING | FAIL |
|---|---|---|---|---|
| 온도 평균 | `gmx energy (Temperature)` | `ref_t ± 5K` | `ref_t ± 10K` | `> ref_t ± 10K` |
| 온도 표준편차 | 동일 | `< 5K` | `5–10K` | `> 10K` |

**FAIL 시 권고:**
- `tau_t`를 `0.1 → 0.05`로 감소 후 재실행
- `gen_seed`를 변경하여 초기 속도 재부여

---

## Phase: `npt` — NPT 평형화 검증 기준

| 검증 항목 | gmx 명령어 | PASS | WARNING | FAIL |
|---|---|---|---|---|
| 압력 평균 | `gmx energy (Pressure)` | `ref_p ± 100 bar` | `± 200 bar` | `> ± 200 bar` |
| 밀도 | `gmx energy (Density)` | `950–1050 kg/m³` | `900–1100 kg/m³` | 범위 초과 |

> 압력은 본질적으로 요동이 크므로 평균값으로 판단한다.

**FAIL 시 권고:**
- `tau_p`를 조정하거나 NPT 시뮬레이션 시간 연장 (`100ps → 500ps`)

---

## Phase: `md` — 본 시뮬레이션 검증 기준

| 검증 항목 | gmx 명령어 | PASS | WARNING | FAIL |
|---|---|---|---|---|
| Total Energy drift | `gmx energy (Total Energy)` | drift 없이 수렴 | 미약한 drift | 현저한 drift |

**FAIL 시 권고:**
- Energy drift: 시간 스텝(`dt`)을 줄이거나 PME 설정 재검토

---

## 💡 Interactive Command (대화형 프롬프트 입력) 처리 힌트

에이전트가 `gmx energy` 등의 분석 도구를 자동 실행할 때, 분석할 그룹(예: 10: Potential 등)을 묻는 프롬프트를 띄웁니다. 에이전트는 이를 우회하기 위해 **표준 입력(stdin) 파이프(`|`)**를 적극적으로 활용해야 합니다.

*   **예시 (에너지 추출):** 
    `echo "10 0" | gmx energy -f nvt.edr -o energy.xvg`
    (10=Potential, 0=종료를 순서대로 자동 입력)

> **주의:** 시스템 구성에 따라 그룹 번호가 동적으로 변할 수 있습니다. 에이전트는 안전을 위해 사전에 그룹 번호 목록을 단순 조회하여 인덱스를 파악하는 단계를 거치는 것이 좋습니다.
