# XVG Parsing & Analysis Guide

`TrajectoryAnalyzer` 스킬이 `.xvg` 파일을 파싱하고 결과를 해석하는 상세 규칙.

---

## 1. XVG 파일 파싱 규칙

GROMACS가 생성하는 `.xvg` 파일은 다음 구조를 가진다.

```
# Created by: gmx rms ...          ← '#'으로 시작: 주석 (무시)
@ title "RMSD"                     ← '@'으로 시작: Grace 메타데이터 (무시)
@ xaxis label "Time (ns)"
@ yaxis label "RMSD (nm)"
0.000000  0.001234                  ← 실제 데이터 (공백/탭 구분)
0.010000  0.002345
...
```

### 파싱 의사코드

```python
data = []
with open("result.xvg") as f:
    for line in f:
        line = line.strip()
        if line.startswith('#') or line.startswith('@'):
            continue          # 헤더/메타데이터 무시
        cols = line.split()
        data.append([float(c) for c in cols])
```

---

## 2. 분석별 해석 기준

### RMSD (rmsd.xvg)

| 지표 | 계산 방법 | PASS | WARNING | FAIL |
|---|---|---|---|---|
| Plateau 여부 | 후반 50% 데이터의 표준편차 | `std < 0.05 nm` | `0.05–0.1 nm` | `> 0.1 nm` |
| Plateau 값 | 후반 50% 데이터의 평균 | `< 0.3 nm (3Å)` | `0.3–0.5 nm` | `> 0.5 nm` |

> **단위 주의:** GROMACS RMSD 출력 단위는 **nm**이다. 보고 시 Å로 변환 (× 10).

### RMSF (rmsf.xvg)

| 지표 | 계산 방법 | 활용 |
|---|---|---|
| 최대 유연 잔기 | `argmax(col2)` | 루프, N/C 말단 확인 |
| 평균 유연성 | `mean(col2)` | 단백질 전체 강성(rigidity) 평가 |
| 고유연 잔기 목록 | `col2 > mean + 2*std` | 활성 부위 유연성, 약물 결합 부위 분석 |

> RMSF 단위: **nm**. 잔기 번호는 `col1` (1-indexed 잔기 번호).

### Radius of Gyration (gyrate.xvg)

| 지표 | 계산 방법 | PASS 기준 |
|---|---|---|
| 평균 Rg | `mean(col2)` | 수렴 여부 판단 (값 자체는 단백질 크기에 따라 다름) |
| Rg 수렴 여부 | 후반 50% 표준편차 | `std < 0.02 nm` |

> gyrate.xvg는 컬럼이 여러 개일 수 있음: `col1`=시간, `col2`=Rg(전체), `col3~5`=Rg(x,y,z 성분).

### Energy (energy.xvg)

`gmx energy` 실행 시 선택 항목별 별도 파일 생성을 권장한다.

| 선택 항목 | 해석 |
|---|---|
| `Potential` | 퍼텐셜 에너지; 음수이며 수렴해야 함 |
| `Total Energy` | 총 에너지; drift가 없어야 함 (drift < 0.01% / ns 권장) |
| `Temperature` | 목표 온도 ± 5K 이내 |
| `Pressure` | 목표 압력 ± 100 bar 이내 (평균값 기준) |
| `Density` | 950–1050 kg/m³ (물 기반 시스템) |

---

## 3. 보고서 마크다운 템플릿

```markdown
## 시뮬레이션 품질 분석 보고서

**시스템:** {protein_name}
**시뮬레이션 시간:** {duration} ns
**분석 일시:** {timestamp}

### RMSD 분석
- 후반부 평균 RMSD: {rmsd_avg} Å
- 후반부 표준편차: {rmsd_std} Å
- 판정: {PASS | WARNING | FAIL}

### RMSF 분석
- 평균 유연성: {rmsf_avg} Å
- 최고 유연 잔기: Residue {max_rmsf_res} ({max_rmsf_val} Å)

### 회전 반경 (Rg)
- 평균 Rg: {rg_avg} nm
- 수렴 판정: {converged | not_converged}

### 에너지 수렴
- Total Energy drift: {energy_drift}
- 판정: {stable | drifting}

### 종합 판정
{PASS | WARNING | FAIL} — {판정 근거 한 줄 요약}

### 후속 연구 제안
{후속 분석 또는 연구 방향}
```
