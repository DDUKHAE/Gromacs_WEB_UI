# GROMACS 에러 트러블슈팅 사전

LLM 에이전트가 에러 발생 시 사용자의 개입 없이 스스로 진단하고 해결하기 위한 에러 패턴별 해결책 매핑 문서입니다.

> **사용 방법:** `GmxExecutor`로부터 `status: error`와 `fatal_error` 메시지를 받으면, 이 문서에서 해당 에러 키워드를 검색하여 `해결책`을 따릅니다.
에러를 해결하지 못하고 3회 이상 실패한 경우, **[복구 불가능 에러 보고 가이드](#fatal-error-report)**에 따라 사용자에게 보고합니다.

---

## 에러 목록 (Error Index)

1. [Water molecules cannot be settled](#error-1)
2. [LINCS Warning / LINCS Error](#error-2)
3. [Segmentation fault](#error-3)
4. [Topology file mismatch / Non-matching atom names](#error-4)
5. [No force field directory found](#error-5)
6. [Ewald sum grid size too large](#error-6)
7. [Pressure went too high / too low](#error-7)
8. [CUDA / Out of Memory (OOM) / 리소스 에러](#error-8)
9. [genion / editconf 관련 에러 (이온 추가 실패, Box 크기 오류)](#error-9)
10. [Residue/Atom not found in topology (리간드 파라미터 누락)](#error-10)

---

## 상세 에러 해결책

### ERROR-1: Water molecules cannot be settled {#error-1}
**발생 단계:** NVT, NPT 평형화 초반
**에러 메시지 패턴:**
`Water molecule cannot be settled.` / `Too many LINCS warnings`
**원인 분석:**
에너지 최소화(EM)가 완전히 수렴하지 못한 상태에서 다이나믹 시뮬레이션을 시작했습니다. 일부 원자들이 서로 너무 가까이 있어 결합 제약 알고리즘이 해를 구하지 못합니다.
**해결 절차:**
1. 에너지 최소화 로그(`em.log`) 확인: Fmax가 1000 kJ/mol/nm 이하인지 확인
2. **Fmax가 기준 초과:** `MdpComposer` 재호출, `minim` 페이즈에서 `nsteps: 100000`으로 증가 후 EM 재실행
3. **박스 크기 문제:** `editconf`에서 `-d` 값을 1.2 → 1.5nm로 증가 후 solvation부터 재시작

---

### ERROR-2: LINCS Warning / LINCS Error {#error-2}
**발생 단계:** NVT, NPT, Production MD
**에러 메시지 패턴:**
`WARNING: Constraint error in algorithm LINCS at step XXXX`
**원인 분석:**
시뮬레이션 스텝 크기(`dt`)가 너무 크거나, 빠른 원자 움직임이 제약 알고리즘의 허용 범위를 벗어났습니다.
**해결 절차:**
1. **경미한 WARNING (rms < 0.01):** 무시하고 계속 진행 가능
2. **심각한 WARNING / ERROR:**
   - `MdpComposer` 재호출, `dt: 0.002` → `dt: 0.001`로 절반 축소
   - `lincs_iter: 1` → `lincs_iter: 2`로 증가
3. 여전히 발생 시: EM 단계부터 재시작

---

### ERROR-3: Segmentation fault {#error-3}
**발생 단계:** 모든 단계
**에러 메시지 패턴:**
`Segmentation fault (core dumped)`
**원인 분석:**
메모리 접근 오류로, 잘못된 `.tpr` 파일이 원인인 경우가 많거나 MPI/OpenMP 스레드 충돌일 수 있습니다.
**해결 절차:**
1. `.tpr` 파일 재생성: `GmxExecutor`로 `grompp` 단계 재실행
2. 실행 시 `-ntomp` 플래그를 사용하여 OpenMP 스레드 수를 제한 (예: `-ntomp 4`)

---

### ERROR-4: Topology file mismatch / Non-matching atom names {#error-4}
**발생 단계:** `gmx grompp` 실행 시
**에러 메시지 패턴:**
`number of coordinates in coordinate file does not match topology`
`atom name XXX in coordinate file does not match topology`
**원인 분석:**
`.gro` 파일과 `topol.top` 파일의 원자 개수나 순서가 일치하지 않습니다.
**해결 절차:**
1. 현재 Step에 맞는 `.gro` 파일이 입력되었는지 검증 (예: Step 5 이후는 `{target}_solv_ions.gro`)
2. `topol.top`의 `[ molecules ]` 섹션에 선언된 분자 순서가 실제 `.gro` 파일 안의 순서와 일치하는지 확인.
3. 물(SOL)이나 이온(NA, CL)의 개수가 정확히 업데이트되었는지 확인.

---

### ERROR-5: No force field directory found {#error-5}
**발생 단계:** `gmx pdb2gmx` 실행 시
**에러 메시지 패턴:**
`No force field directory charmm36m-ut found in the GROMACS data directory`
**원인 분석:**
지정된 포스필드가 현재 GROMACS 설치 환경에 존재하지 않습니다.
**해결 절차:**
1. 사용 가능한 포스필드 목록 확인: `gmx pdb2gmx -h`
2. `docs/force_field_guide.md`의 `GROMACS 내부 ID`를 재확인하고 올바른 ID로 재시도
3. CHARMM36m이 없는 경우 `amber99sb-ildn`으로 대체 시도

---

### ERROR-6: Ewald sum grid size too large {#error-6}
**발생 단계:** `gmx grompp` 실행 시
**에러 메시지 패턴:**
`NOTE: The Ewald grid is too large for optimal efficiency.`
**원인 분석:**
시뮬레이션 박스 크기에 비해 PME 격자가 너무 조밀합니다.
**해결 절차:**
1. `.mdp` 파일에 `fourierspacing = 0.16`이 설정되어 있는지 확인. 이 에러는 NOTE(경고) 레벨이므로 무시하고 계속 진행 가능.

---

### ERROR-7: Pressure went too high / too low {#error-7}
**발생 단계:** NPT 평형화, Production MD
**에러 메시지 패턴:**
`Pressure XXX bar is too high for the time step`
**원인 분석:**
NPT 평형화가 충분히 이루어지지 않은 상태에서 MD를 시작했거나, `tau_p` 값이 너무 작습니다.
**해결 절차:**
1. NPT 평형화를 더 길게: `MdpComposer`에서 `npt` 페이즈, `nsteps: 250000` (500ps)으로 재실행
2. `tau_p: 2.0` → `tau_p: 5.0`으로 완화

---

### ERROR-8: CUDA / Out of Memory (OOM) / 리소스 에러 {#error-8}
**발생 단계:** `gmx mdrun` 실행 시
**에러 메시지 패턴:**
`CUDA error: out of memory`
`Failed to allocate memory for ...`
**원인 분석:**
GPU VRAM이 부족하거나, 시스템 크기(원자 수)가 장비 스펙에 비해 너무 큽니다.
**해결 절차:**
1. `mdrun` 명령어에 GPU 연산을 CPU로 분산시키는 옵션 추가 시도 (예: PME 연산을 CPU로 넘기기 `-pme cpu`)
2. `mdrun` 명령어에 `-gpu_id`를 명시하거나, CUDA를 사용하지 않도록 `-nb cpu` 옵션 사용(매우 느려짐 주의).
3. 해결 불가 시 사용자에게 리소스 부족 문제 보고.

---

### ERROR-9: genion / editconf 관련 에러 (이온 추가 실패, Box 크기 오류) {#error-9}
**발생 단계:** `gmx editconf`, `gmx solvate`, `gmx genion`
**에러 메시지 패턴:**
`No more replaceable solvent!` (genion)
`WARNING: The box volume is smaller than the volume of the solute` (editconf)
**원인 분석:**
- 이온 추가 시 치환할 물(SOL) 분자가 부족합니다.
- editconf에서 정의한 박스가 단백질을 온전히 담기엔 너무 작습니다.
**해결 절차:**
1. **editconf 에러:** 박스 마진(`-d`)을 1.0에서 1.2~1.5로 늘려 재실행 (`gmx editconf -f ... -box ... -d 1.5`)
2. **genion 에러:** `solvate`가 정상적으로 진행되어 `topol.top`에 SOL 분자가 등록되었는지 확인. `genion` 명령어 수행 시 프롬프트로 물 그룹(주로 13 또는 SOL)을 정확히 지정했는지 확인.

---

### ERROR-10: Residue/Atom not found in topology (리간드 파라미터 누락) {#error-10}
**발생 단계:** `gmx pdb2gmx` 실행 시
**에러 메시지 패턴:**
`Residue 'LIG' not found in residue topology database`
`Atom 'C1' not found in residue topology database`
**원인 분석:**
PDB 파일에 포스필드에 정의되지 않은 리간드(소분자) 또는 비표준 아미노산이 포함되어 있습니다.
**해결 절차:**
1. 리간드가 포함된 경우 `pdb2gmx` 단독으로는 처리할 수 없습니다. 
2. `force_field_guide.md`의 리간드 처리 파트를 참조하여 외부 파라미터화 툴(ACPYPE 등) 사용 워크플로우로 전환하거나 사용자에게 리간드용 `.itp` 파일을 요구해야 합니다.

---

## 복구 불가능 에러 보고 가이드 {#fatal-error-report}
에이전트가 위 절차들을 통해 3회 이상 재시도하였음에도 에러가 해결되지 않는 경우, 더 이상의 임의 수정은 시스템을 망가뜨릴 수 있으므로 사용자에게 즉각 보고해야 합니다.

**보고 시 포함해야 할 정보 (출력 포맷 예시):**
```markdown
🚨 **자율 복구 실패 보고 (Fatal Error)**

* **발생 단계:** {진행 중이던 Step 명}
* **실행 명령어:** `{실패한 gmx 명령어}`
* **마지막 에러 메시지:** 
  ```text
  {gmx 로그의 Fatal error 또는 핵심 에러 텍스트}
  ```
* **시도한 복구 내역:** 
  - 1차 시도: dt 0.001로 감소 (실패)
  - 2차 시도: EM nsteps 증가 (실패)
* **사용자 행동 요청:** 
  - "topol.top 파일의 [ molecules ] 섹션과 구조 파일의 분자 개수가 일치하는지 확인해 주세요."
  - "초기 PDB 구조에 원자 충돌이 심각하거나 결측치(Missing atoms)가 있을 수 있으니 구조 검토를 부탁드립니다."
```
