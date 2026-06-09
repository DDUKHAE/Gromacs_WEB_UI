# 튜토리얼 데이터를 활용한 테스트 가이드

이 문서는 `tutorial_data/` 디렉터리에 포함된 표준 입력 파일을 사용하여 GROMACS Harness를 테스트하는 방법을 안내합니다.

## 테스트 데이터 목록

| 튜토리얼 | 파일 | 출처 |
|---|---|---|
| Lysozyme_in_water | `1AKI.pdb` | RCSB PDB |
| Protein_Ligand_Complex | `3HTB.pdb` | RCSB PDB |
| Umbrella_Sampling | `2BEG.pdb`, `2BEG_model1_capped.pdb` | RCSB PDB / mdtutorials.com |
| KALP15_in_DPPC | `KALP-15_princ.pdb` | mdtutorials.com |
| Free_Energy_Methane_in_Water | `methane_water.gro`, `topol.top` | mdtutorials.com |
| Free_Energy_Ethanol | `etoh.pdb` | mdtutorials.com |
| Building_Biphasic_Systems | `chx.gro`, `chx.top`, `chx_10ns.gro` | mdtutorials.com |
| Virtual_Sites | `co2.pdb` | mdtutorials.com |

> **참고:** KALP15_in_DPPC 튜토리얼에 필요한 Berger lipid 파라미터(`dppc128.pdb`, `dppc.itp`, `lipid.itp`)는 2023년부터 원 배포처(Tieleman 연구실)에서 제공 중단되었습니다. 해당 튜토리얼은 현재 완전 실행이 불가합니다.

---

## 방법 1: 웹 UI를 통한 테스트

### 사전 준비

```bash
conda activate GROMACS
export ANTHROPIC_API_KEY="your-key"
python main.py
```

브라우저에서 `http://localhost:8000` 접속.

---

### 테스트 1 — Lysozyme in Water (권장 첫 테스트)

**입력 파일:** `tutorial_data/Lysozyme_in_water/1AKI.pdb`

1. 웹 UI에서 **파일 업로드** 클릭 → `tutorial_data/Lysozyme_in_water/1AKI.pdb` 선택
2. **Prompt** 입력:
   ```
   Simulate hen egg white lysozyme in water using CHARMM36 force field with TIP3P water model
   ```
3. **Run** 클릭
4. 파이프라인 진행 상황을 터미널 및 UI 로그에서 확인
5. 완료 후 결과 탭에서 RMSD, Rg 그래프 및 `report.md` 확인

**예상 소요 시간:** 환경 구성 ~5분 + 시뮬레이션 (1 ns 기준 GPU 환경 ~10분)

---

### 테스트 2 — Protein-Ligand Complex

**입력 파일:** `tutorial_data/Protein_Ligand_Complex/3HTB.pdb`

1. `tutorial_data/Protein_Ligand_Complex/3HTB.pdb` 업로드
2. **Prompt**:
   ```
   Simulate T4 lysozyme L99A/M102Q with JZ4 ligand using CHARMM36 force field
   ```
3. Run 실행

**특이사항:**
- JZ4 리간드 topology는 CHARMM-GUI CGenFF 또는 `cgenff_charmm2gmx.py`로 별도 생성 필요
- 리간드 topology 없이 실행 시 `env_builder`가 경고를 출력하고 단백질만 처리하거나 중단됨

---

### 테스트 3 — Free Energy (Methane in Water)

**입력 파일:** `tutorial_data/Free_Energy_Methane_in_Water/methane_water.gro`

1. `.gro` 파일 업로드
2. **Prompt**:
   ```
   Calculate free energy of decoupling van der Waals interactions for methane in TIP3P water using OPLS-AA
   ```
3. Run 실행

**특이사항:**
- 이 튜토리얼은 topology 파일(`topol.top`)도 함께 필요합니다. UI에서 추가 파일 업로드 기능을 이용하거나 동일 디렉터리에 배치하세요.

---

### 테스트 4 — Free Energy (Ethanol Hydration)

**입력 파일:** `tutorial_data/Free_Energy_Ethanol/etoh.pdb`

1. `etoh.pdb` 업로드
2. **Prompt**:
   ```
   Calculate hydration free energy of ethanol using CHARMM General Force Field and BAR method
   ```

---

### 테스트 5 — Umbrella Sampling

**입력 파일:** `tutorial_data/Umbrella_Sampling/2BEG_model1_capped.pdb`

1. `2BEG_model1_capped.pdb` 업로드 (N-terminus 아세틸화된 Aβ42 protofibril)
2. **Prompt**:
   ```
   Umbrella sampling simulation for Abeta42 protofibril peptide dissociation using GROMOS96 53A6 force field
   ```

**특이사항:**
- Chain B 위치 구속 설정이 필요합니다 (`posre_Protein_chain_B.itp`)
- Umbrella sampling은 다수의 독립 시뮬레이션 윈도우 실행을 포함하므로 최초 테스트에서는 짧은 pulling 구간만 수행하도록 prompt를 조정하세요.

---

### 테스트 6 — Biphasic System (Cyclohexane-Water)

**입력 파일:** `tutorial_data/Building_Biphasic_Systems/chx.gro` 또는 `chx_10ns.gro`

1. `chx_10ns.gro` 업로드 (평형화 완료된 사이클로헥산 박스)
2. **Prompt**:
   ```
   Build a biphasic cyclohexane-water system using GROMOS96 43A1 force field
   ```

---

### 테스트 7 — Virtual Sites (CO2)

**입력 파일:** `tutorial_data/Virtual_Sites/co2.pdb`

1. `co2.pdb` 업로드
2. **Prompt**:
   ```
   Simulate carbon dioxide using virtual sites with OPLS-AA force field
   ```

---

## 방법 2: 회귀 테스트 스크립트 (CLI)

GROMACS가 설치된 환경에서 직접 스크립트를 실행합니다.

```bash
conda activate GROMACS

# Lysozyme (기본 회귀)
./scripts/regression/lysozyme.sh

# Protein-Ligand
./scripts/regression/protein_ligand.sh

# Umbrella Sampling
./scripts/regression/umbrella.sh

# Free Energy - Methane
./scripts/regression/fe_methane.sh

# Free Energy - Ethanol
./scripts/regression/fe_ethanol.sh

# Biphasic
./scripts/regression/biphasic.sh

# Virtual Sites
./scripts/regression/virtual_sites.sh
```

각 스크립트는 `tutorial_data/` 하위 파일을 자동으로 참조합니다.

---

## 방법 3: Python API 직접 호출

```python
from pathlib import Path
from skills.env_builder import build_environment
from skills.md_runner import run_simulation
from skills.illustrator import illustrate

# 예시: Lysozyme
ws = Path("runs/test_lysozyme").resolve()
ws.mkdir(parents=True, exist_ok=True)

build_environment(
    pdb_path=Path("tutorial_data/Lysozyme_in_water/1AKI.pdb").resolve(),
    prompt="protein in water, CHARMM36 force field, TIP3P water",
    workspace_dir=ws,
    prerequisites={},
    interactive=False,
)

run_simulation(workspace_dir=ws, interactive=False)

illustrate(workspace_dir=ws, animation={"enabled": False})

print("결과:", ws / "stage3_viz" / "report.md")
```

---

## 방법 4: pytest 통합 테스트

```bash
# GROMACS 설치 필요
pytest tests/integration/test_env_builder_lysozyme.py -v

# 튜토리얼 데이터 경로를 fixture로 활용
pytest tests/integration -v --tb=short
```

---

## 결과 확인 체크리스트

각 테스트 완료 후 `runs/<run_id>/` 디렉터리에서 아래 항목을 확인합니다:

| 항목 | 파일 | 정상 기준 |
|---|---|---|
| State JSON | `stage1_env/state.json` | `"status": "ready"` |
| Topology | `stage1_env/topol.top` | 존재, 0 bytes 아님 |
| Coordinate | `stage1_env/*_processed.gro` | 존재 |
| EM 수렴 | `stage2_md/em.log` | `Potential Energy` 음수 수렴 |
| NVT 온도 | `stage2_md/nvt.xvg` | 목표 온도 ±5 K 이내 |
| NPT 밀도 | `stage2_md/npt.xvg` | ~1000 kg/m³ (순수 물 기준) |
| 보고서 | `stage3_viz/report.md` | 존재, RMSD/Rg 포함 |

---

## 문제 해결

| 증상 | 원인 | 조치 |
|---|---|---|
| `gmx: command not found` | GROMACS 미설치 | `conda activate GROMACS` 후 재실행 |
| `Fatal error: ... no force field` | force field 경로 불일치 | `GMXLIB` 환경 변수 확인 |
| `WARNING: 1 atoms missing` | PDB HOH 미제거 | `grep -v HOH 1AKI.pdb > 1AKI_clean.pdb` 후 재시도 |
| Topology 생성 실패 (리간드) | 리간드 RTP 엔트리 없음 | CGenFF/ACPYPE로 별도 topology 생성 필요 |
| DPPC 파라미터 없음 (KALP15) | Berger lipid 배포 중단 | 해당 튜토리얼은 현재 실행 불가 |

---

## 참조

- [GROMACS 공식 문서](https://manual.gromacs.org/)
- [mdtutorials.com](http://www.mdtutorials.com/gmx/) — Justin Lemkul 튜토리얼
- [`docs/runbook.md`](runbook.md) — 수동 복구 절차
- [`docs/independent_entry_guide.md`](independent_entry_guide.md) — 특정 skill 단독 진입
