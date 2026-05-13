# Force Field 및 물 모델 선택 가이드

LLM 에이전트가 `gmx pdb2gmx` 실행 전(Step 1), 시스템 조건에 맞는 포스필드와 물 모델을 선택하기 위한 의사결정 가이드입니다.

---

## 1. 포스필드 선택 의사결정 트리 (Decision Tree)

에이전트는 사용자가 제공한 시스템 정보를 바탕으로 아래 트리를 따라 포스필드를 선택합니다.

```
시스템에 소분자 리간드(Ligand)가 포함되어 있는가?
│
├── YES → AMBER 계열 선택 (GAFF/GAFF2 파라미터와 호환성 우수)
│         └─ 주의: 리간드는 pdb2gmx로 단독 처리 불가. 아래 '5. 리간드 처리 가이드' 참조.
│
└── NO → 단백질만 있는가?
          │
          ├── 막 단백질(Membrane Protein)인가?
          │   └── YES → CHARMM36m (지질 이중층 시뮬레이션 최적화)
          │
          └── 수용액 단백질(Soluble Protein)인가?
              ├── CHARMM36m (범용 표준, 권장)
              └── OPLS-AA/L (2차 구조 예측 정확도 우수)
```

---

## 2. 포스필드별 상세 정보

| 포스필드 | GROMACS 내부 ID | 장점 | 단점 | 최적 사용 시나리오 |
|---|---|---|---|---|
| **CHARMM36m** | `charmm36m-ut` | 막/수용액 단백질 모두 우수, 널리 검증됨 | 파라미터 파일 크기가 큼 | 범용 단백질 시뮬레이션 (1순위 권장) |
| **AMBER99SB-ILDN** | `amber99sb-ildn` | 단백질 골격 다이헤드럴 최적화 | 소분자 파라미터 별도 필요 | 수용액 단백질, 단백질 폴딩 연구 |
| **AMBER14SB** | `amber14sb` | 최신 AMBER 포스필드, RNA 정확도 개선 | CHARMM36m보다 검증 적음 | 단백질-핵산(RNA/DNA) 복합체 |
| **OPLS-AA/L** | `oplsaa` | 2차 구조 안정성 우수 | 비표준 잔기 지원 부족 | alpha-helix/beta-sheet 분석 |

---

## 3. 물 모델 선택 가이드

물 모델은 선택한 포스필드와 반드시 호환되어야 합니다.

| 물 모델 | GROMACS ID | 분자 사이트 수 | 호환 포스필드 | 특징 |
|---|---|---|---|---|
| **TIP3P** | `tip3p` | 3-site | CHARMM, AMBER | 가장 범용적, 계산 효율 우수. **기본 선택** |
| **SPC/E** | `spce` | 3-site | OPLS, GROMOS | 물의 유전 상수 재현성 우수 |
| **TIP4P** | `tip4p` | 4-site | AMBER | 더 정확한 물 구조, 계산 비용 증가 |

> **권장 조합:** CHARMM36m + TIP3P, AMBER99SB-ILDN + TIP3P

---

## 4. `pdb2gmx` 명령어 예시

```bash
# CHARMM36m + TIP3P 조합 (표준 수용액 단백질)
gmx pdb2gmx -f protein.pdb -o protein_processed.gro -p topol.top \
            -ff charmm36m-ut -water tip3p -ignh
```

> `-ignh` 플래그: PDB 파일의 기존 수소 원자를 무시하고 새로 추가합니다.

---

## 5. ⚠️ 리간드 (Ligand) 및 비표준 잔기 처리 가이드

단백질 이외의 유기 소분자(리간드)나 비표준 잔기가 포함된 경우 `gmx pdb2gmx` 단일 명령어만으로는 토폴로지 생성이 실패합니다.

### 5-1. 리간드 처리 파이프라인
1. **리간드 분리:** 원본 PDB에서 단백질과 리간드를 분리합니다 (`protein.pdb`, `ligand.pdb`).
2. **단백질 처리:** `protein.pdb`는 기존대로 `gmx pdb2gmx`를 통해 `topol.top`과 `protein.gro`를 생성합니다.
3. **리간드 파라미터화 (외부 툴 사용):**
   - **AMBER 환경 시:** **ACPYPE** (또는 Antechamber)를 사용하여 `ligand.pdb`로부터 `ligand.itp`와 `ligand.gro` 생성.
   - **CHARMM 환경 시:** **CGenFF** 서버/스크립트를 사용하여 `ligand.itp` 생성.
4. **통합:** 
   - `protein.gro`와 `ligand.gro`를 병합하여 `complex.gro` 생성 (총 원자 개수 업데이트 필수).
   - `topol.top` 파일에 `#include "ligand.itp"` 구문을 추가하고, 맨 아래 `[ molecules ]` 섹션 끝에 `Ligand 1` 과 같이 추가합니다.

> **LLM 에이전트 주의사항:** 에이전트 환경에 ACPYPE 등의 외부 파라미터화 툴이 연동되어 있지 않다면, 리간드 처리 중 에러가 발생했을 때 파이프라인을 중단하고 사용자에게 리간드용 `.itp` 및 `.gro` 파일을 제공해 줄 것을 즉시 보고/요청해야 합니다.

### 5-2. 비표준 잔기(Non-standard residues) 및 Missing Atom 대응
PDB 파일 내의 누락된 원자(Missing atom)나 비표준 아미노산(예: TPO, SEP)으로 인해 `pdb2gmx` 실행 시 `Residue XXX not found` 에러가 발생하는 경우:
1. GROMACS 자체 도구만으로는 단백질 결측치나 복잡한 수식(PTM)을 완전히 자동 복원할 수 없습니다.
2. 해결책: 즉각적으로 사용자에게 "Modeller 등의 도구로 누락된 원자를 복원하거나, 비표준 잔기를 표준 잔기로 변환(예: MSE -> MET)한 PDB 구조를 제공해 줄 것"을 요청해야 합니다.
