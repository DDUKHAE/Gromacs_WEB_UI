# System Builder 구현 사전 학습 자료

System Builder를 이해하고 구현하기 위해 필요한 MD 기초 지식과 GROMACS 개념을 단계별로 정리한 학습 가이드입니다.  
각 항목은 설계 문서의 어느 부분과 연관되는지 표시했습니다.

---

## 학습 순서 권장

```
1단계: MD가 뭔지 (30분)
2단계: GROMACS 파이프라인 이해 (1~2시간)
3단계: 각 Builder Step 파라미터 (필요할 때마다 참고)
4단계: CHARMM-GUI 직접 사용해보기 (1시간)
```

---

## 1단계 — 분자동역학(MD) 기초

### MD란 무엇인가

| 개념 | 한 줄 설명 | 학습 자료 |
|------|-----------|-----------|
| 분자동역학 | 원자들의 위치와 속도를 뉴턴 운동방정식으로 시간 전개 | [Wikipedia: Molecular dynamics](https://en.wikipedia.org/wiki/Molecular_dynamics) |
| Force Field | 원자 간 인력/척력을 계산하는 수학적 함수 모음 | [CHARMM Force Fields 소개](https://www.charmm.org/charmm/documentation/force-fields/) |
| 시뮬레이션 박스 | 주기적 경계 조건(PBC)으로 무한 시스템을 모사하는 가상 상자 | [GROMACS PBC 설명](https://manual.gromacs.org/current/reference-manual/algorithms/periodic-boundary-conditions.html) |
| Time step | 한 번 계산하는 시간 간격 (보통 2 fs) | [GROMACS mdp 옵션](https://manual.gromacs.org/current/user-guide/mdp-options.html) |

**추천 입문 영상:**
- [MD Simulation Explained Simply (YouTube)](https://www.youtube.com/watch?v=lLFEqKl3sm4) — 15분, 시각적 설명
- [GROMACS 공식 소개](https://www.gromacs.org/About_Gromacs) — 텍스트, 5분

---

## 2단계 — GROMACS 파이프라인

현재 프로젝트의 Steps 0~8이 어떤 gmx 명령어에 대응하는지 이해합니다.

### 전체 흐름 (Lysozyme 튜토리얼 기준)

가장 표준적인 튜토리얼. 이것만 이해하면 Solution Builder 구현 가능.

**[Justin Lemkul의 GROMACS Lysozyme 튜토리얼](https://www.mdtutorials.com/gmx/lysozyme/)**  
→ 한 페이지씩 읽으면서 각 명령어가 무엇을 하는지 파악. Step 1~6이 Builder Steps 1~4에 직접 대응.

| 튜토리얼 Step | gmx 명령 | Builder Step | 설정 파라미터 |
|--------------|----------|-------------|--------------|
| [Step 1: pdb2gmx](https://www.mdtutorials.com/gmx/lysozyme/01_pdb2gmx.html) | `gmx pdb2gmx` | Builder Step 2 | Force Field, Water Model |
| [Step 2: editconf](https://www.mdtutorials.com/gmx/lysozyme/02_editconf.html) | `gmx editconf` | Builder Step 3 | 박스 형태, 여백 거리 |
| [Step 3: solvate](https://www.mdtutorials.com/gmx/lysozyme/03_solvate.html) | `gmx solvate` | Builder Step 3 | (물 자동 채움) |
| [Step 4: ions](https://www.mdtutorials.com/gmx/lysozyme/04_ions.html) | `gmx genion` | Builder Step 4 | 이온 종류, 농도 |
| [Step 5: EM](https://www.mdtutorials.com/gmx/lysozyme/05_EM.html) | `gmx mdrun` | Expert Step 5 | 에너지 최소화 |
| [Step 6: NVT](https://www.mdtutorials.com/gmx/lysozyme/06_equilibration.html) | `gmx mdrun` | Expert Step 5 | 온도, Thermostat |
| [Step 7: NPT](https://www.mdtutorials.com/gmx/lysozyme/07_equilibration.html) | `gmx mdrun` | Expert Step 5 | 압력, Barostat |
| [Step 8: MD](https://www.mdtutorials.com/gmx/lysozyme/08_MD.html) | `gmx mdrun` | Expert Step 5 | 시뮬레이션 시간 |

---

## 3단계 — Builder 각 Step 파라미터 상세

### Builder Step 2: Force Field & Water Model

**Force Field란?**
원자 간 상호작용을 수식으로 표현한 파라미터 집합. 단백질 시뮬레이션에서 결과의 정확도를 좌우.

| Force Field | 특징 | 적합한 시스템 |
|------------|------|--------------|
| CHARMM36m | 단백질·지질 최신 버전, 현재 프로젝트 기본 | 단백질, 막 단백질 |
| AMBER99SB-ILDN | 단백질 폴딩 연구에 많이 사용 | 단백질 |
| OPLS-AA | 소분자·유기 화합물에 강점 | 리간드 포함 시스템 |

📚 [Force Field 선택 가이드 (GROMACS FAQ)](https://manual.gromacs.org/current/reference-manual/topologies/force-field-organization.html)

**Water Model이란?**
물 분자의 전하 분포를 어떻게 모델링할지 결정.

| 모델 | 특징 |
|------|------|
| TIP3P | 가장 빠름, CHARMM FF와 기본 조합 |
| SPC/E | TIP3P보다 물 특성 더 정확 |
| TIP4P | 4점 모델, 더 정확하지만 느림 |

📚 [Water Model 비교 (Wikipedia)](https://en.wikipedia.org/wiki/Water_model)

---

### Builder Step 3: 박스 설정

**왜 박스 형태가 중요한가?**  
박스 부피가 클수록 물 분자가 많아져 계산이 느려짐. 단백질을 효율적으로 감싸는 형태를 선택하면 계산량을 줄일 수 있음.

| 박스 형태 | 모양 | 부피 효율 | 용도 |
|----------|------|----------|------|
| Cubic | 정육면체 | 낮음 (가장 큰 부피) | 단순, 초보자 |
| Dodecahedron | 12면체 | 중간 (~71%) | 구형 단백질, 권장 |
| Octahedron | 팔면체 | 높음 (~77%) | 구형 단백질, 빠른 계산 |

📚 [GROMACS editconf 설명](https://www.mdtutorials.com/gmx/lysozyme/02_editconf.html)  
📚 [박스 형태 비교 (GROMACS 매뉴얼)](https://manual.gromacs.org/current/reference-manual/algorithms/periodic-boundary-conditions.html)

**여백 거리 (edge distance):**  
단백질 표면에서 박스 벽까지의 최소 거리. 보통 1.0~1.2 nm. 너무 작으면 단백질이 자기 자신과 상호작용 (PBC 아티팩트).

---

### Builder Step 4: 이온 설정

**왜 이온을 넣는가?**
1. **중성화:** 단백질은 보통 순 전하를 가짐. 이온을 추가해 시스템 전체 전하를 0으로 만들어야 PME(정전기 계산) 가능
2. **생리적 조건:** 세포 내 이온 농도(~0.15 M NaCl)를 재현해 생물학적으로 의미 있는 결과

📚 [이온화 설명 (Lemkul 튜토리얼 Step 4)](https://www.mdtutorials.com/gmx/lysozyme/04_ions.html)

---

### Builder Step 5 (Expert): 시뮬레이션 파라미터

**평형화 단계란?**  
에너지 최소화 후 바로 생산 시뮬레이션을 하면 시스템이 불안정. 단계적으로 안정화:

```
에너지 최소화 (EM)  →  NVT 평형화  →  NPT 평형화  →  생산 MD
(구조 최적화)         (온도 고정)      (압력 고정)     (데이터 수집)
```

| 파라미터 | 단위 | 기본값 | 의미 |
|---------|------|--------|------|
| 온도 | K | 300 | 시뮬레이션 온도 (실온 = 298 K) |
| 압력 | bar | 1.0 | 1기압 = 1.01325 bar |
| 시뮬레이션 시간 | ns | 1.0 | 생산 MD 길이 |
| Thermostat | — | V-rescale | 온도 유지 알고리즘 |
| Barostat | — | Parrinello-Rahman | 압력 유지 알고리즘 |

📚 [NVT 평형화 (Lemkul)](https://www.mdtutorials.com/gmx/lysozyme/06_equilibration.html)  
📚 [NPT 평형화 (Lemkul)](https://www.mdtutorials.com/gmx/lysozyme/07_equilibration.html)  
📚 [전체 .mdp 옵션 목록](https://manual.gromacs.org/current/user-guide/mdp-options.html)

---

## 4단계 — CHARMM-GUI 직접 사용해보기

실제로 CHARMM-GUI를 사용해보면 Builder UI를 어떻게 만들어야 할지 감이 잡힘.

1. [https://www.charmm-gui.org](https://www.charmm-gui.org) 접속 (무료 계정 필요)
2. **Input Generator → Solution Builder** 선택
3. 현재 프로젝트의 `tutorial_data/Lysozyme_in_water/1AKI.pdb` 파일 업로드
4. 각 Step에서 어떤 설정이 있는지 직접 확인
5. 마지막에 GROMACS 패키지 다운로드 → 생성된 `.mdp` 파일들 열어보기

---

## 5단계 — 구현 관련 추가 자료

### Python에서 PDB 파싱
Builder Step 1에서 원자 수, 체인 수 등을 파싱할 때 필요.

- [BioPython PDB 파서](https://biopython.org/wiki/The_Biopython_Structural_Bioinformatics_FAQ) — 가장 표준적
- [MDAnalysis](https://www.mdanalysis.org/) — 더 강력하지만 의존성 큼
- 단순 텍스트 파싱: PDB 포맷은 고정 컬럼 텍스트, `ATOM`/`HETATM` 레코드만 읽으면 됨

### GROMACS 명령어 레퍼런스
각 Builder Step에서 사용하는 명령어 공식 문서.

| 명령어 | 공식 문서 |
|--------|---------|
| `gmx pdb2gmx` | [링크](https://manual.gromacs.org/current/onlinehelp/gmx-pdb2gmx.html) |
| `gmx editconf` | [링크](https://manual.gromacs.org/current/onlinehelp/gmx-editconf.html) |
| `gmx solvate` | [링크](https://manual.gromacs.org/current/onlinehelp/gmx-solvate.html) |
| `gmx genion` | [링크](https://manual.gromacs.org/current/onlinehelp/gmx-genion.html) |
| `gmx grompp` | [링크](https://manual.gromacs.org/current/onlinehelp/gmx-grompp.html) |

### Force Field 목록 확인 (로컬)
```bash
# 설치된 force field 목록
ls $(gmx -quiet pdb2gmx -h 2>&1 | grep "GMXDATA" | awk '{print $2}')/top/
# 또는
gmx pdb2gmx -h 2>&1 | grep -A 50 "Force fields"
```

---

## 관련 논문 (심화, 필수 아님)

- CHARMM-GUI 원본: [Jo et al., J. Comput. Chem. 2008](https://doi.org/10.1002/jcc.20945)
- CHARMM36m FF: [Huang et al., Nature Methods 2017](https://doi.org/10.1038/nmeth.4067)
- GROMACS 4.5: [Hess et al., J. Chem. Theory Comput. 2008](https://doi.org/10.1021/ct700301q)

---

## 설계 문서 위치

`docs/superpowers/specs/2026-06-11-system-builder-design.md`
