# Skill: SystemValidator

각 파이프라인 Step 완료 후 생성된 결과물을 물리적으로 검증하고, 다음 단계로 진행해도 되는지 여부를 판단하는 품질 제어(QC) 스킬입니다. 에이전트는 이 스킬의 판정 없이 다음 단계로 넘어가서는 안 됩니다.

---

## 1. 역할 및 존재 이유

MD 시뮬레이션에서 한 단계의 실패는 이후 모든 단계를 무의미하게 만듭니다. 예를 들어:
- 에너지 최소화(EM)가 수렴하지 않은 채로 NVT를 진행하면 즉시 "Lincs Warning" 또는 구조 붕괴가 발생합니다.
- NPT 평형화가 완료되지 않으면 본 시뮬레이션의 압력/밀도가 비정상적으로 나옵니다.

`SystemValidator`는 `gmx energy` 등의 분석 도구를 내부적으로 호출하여, 정량적 수치가 `docs/simulation_criteria.md`의 기준값을 만족하는지 확인합니다.

---

## 2. 입력 스키마 (Input Schema)

```json
{
  "phase": "<검증할 단계 Phase ID>",
  "files": {
    "tpr": "<.tpr 파일 경로>",
    "edr": "<.edr 파일 경로>",
    "log": "<.log 파일 경로>"
  }
}
```

---

## 3. 반환 스키마 (Output Schema)

```json
{
  "verdict": "PASS | FAIL | WARNING",
  "phase": "<검증한 단계>",
  "metrics": {
    "<측정 항목>": "<측정값>"
  },
  "reason": "<판정 근거 (기준값 대비 측정값 비교)>",
  "recommendation": "<FAIL/WARNING 시 권고 행동>"
}
```

---

## 4. 단계별 검증 기준 (Validation Criteria)

> 상세 기준값은 `docs/simulation_criteria.md`를 참조합니다. 아래는 스킬이 내부적으로 사용하는 체크리스트입니다.

### Phase: `minim` (에너지 최소화 검증)
```yaml
검증 항목:
  - 항목: "최대 힘(Maximum Force)"
    내부 명령어: "gmx energy -f em.edr -o energy_em.xvg"
    PASS 조건: "Fmax < 1000 kJ/mol/nm (emtol 설정값 이하)"
    FAIL 시 권고: "nsteps를 늘리거나 emstep을 줄인 후 재실행"

  - 항목: "퍼텐셜 에너지(Potential Energy)"
    PASS 조건: "값이 충분히 큰 음수이며 단조 감소 추세"
    FAIL 시 권고: "초기 구조(.pdb)에 충돌하는 원자가 있을 수 있음. pdb2gmx 단계를 재확인"
```

### Phase: `nvt` (NVT 평형화 검증)
```yaml
검증 항목:
  - 항목: "온도(Temperature)"
    내부 명령어: "gmx energy (선택: Temperature)"
    PASS 조건: "목표 온도(ref_t) ± 5K 이내에서 안정적으로 수렴"
    WARNING 조건: "온도가 요동(oscillation)하나 평균은 목표치에 근접"
    FAIL 시 권고: "tau_t 값을 0.1 → 0.05로 줄이고 재실행"
```

### Phase: `npt` (NPT 평형화 검증)
```yaml
검증 항목:
  - 항목: "압력(Pressure)"
    PASS 조건: "ref_p ± 100 bar 이내 (압력은 요동이 큼)"
    WARNING: "평균값이 ref_p에 근접하면 WARNING도 통과로 처리"

  - 항목: "밀도(Density)"
    PASS 조건: "물 기반 시스템: 950~1050 kg/m³"
    FAIL 시 권고: "tau_p 값을 조정하거나 NPT를 더 길게(100ps → 500ps) 실행"
```

### Phase: `md` (본 시뮬레이션 검증)
```yaml
검증 항목:
  - 항목: "RMSD (Root Mean Square Deviation)"
    내부 명령어: "gmx rms -s md.tpr -f md.xtc -o rmsd.xvg"
    PASS 조건: "시뮬레이션 후반부에 안정적인 plateau에 도달 (일반적으로 < 3Å)"

  - 항목: "에너지 보존"
    PASS 조건: "Total Energy가 드리프트(drift) 없이 수렴"
```

---

## 5. 호출 예시

### NVT 완료 후 검증
```json
{
  "skill": "SystemValidator",
  "params": {
    "phase": "nvt",
    "files": {
      "tpr": "nvt.tpr",
      "edr": "nvt.edr",
      "log": "nvt.log"
    }
  }
}
```

### 예상 반환 (PASS)
```json
{
  "verdict": "PASS",
  "phase": "nvt",
  "metrics": {
    "temperature_avg": "299.8 K",
    "temperature_std": "2.1 K"
  },
  "reason": "평균 온도 299.8K이 목표 온도 300K ± 5K 기준을 만족합니다.",
  "recommendation": "NPT 평형화 단계로 진행하세요."
}
```

### 예상 반환 (FAIL)
```json
{
  "verdict": "FAIL",
  "phase": "minim",
  "metrics": {
    "fmax": "15234.2 kJ/mol/nm"
  },
  "reason": "최대 힘(Fmax) 15234.2 kJ/mol/nm이 기준값 1000 kJ/mol/nm을 초과합니다.",
  "recommendation": "nsteps를 50000 → 100000으로 늘리거나 emstep을 0.01 → 0.001로 줄인 후 에너지 최소화를 재실행하세요."
}
```
