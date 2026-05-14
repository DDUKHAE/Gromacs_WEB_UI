# GROMACS Tutorial Overview

이 문서는 GROMACS 하네스(Agent) 환경에서 참고하고 활용할 수 있도록 정리된 튜토리얼 문서들의 전체 개요를 설명합니다.

## Runtime-First Reading Order

LLM 런타임에서는 아래 문서를 먼저 읽고 튜토리얼 part 본문으로 진입합니다.

1. `docs/tutorial/TUTORIAL_OVERVIEW.md`
2. `docs/tutorial/tutorial_index.json`
3. 선택 튜토리얼 `tutorial.manifest.json` (있는 경우)
4. `docs/tutorial/LLM_TUTORIAL_GUIDE.md`
5. `docs/tutorial/LLM_ESSENTIALS_BY_STEP.md`
6. 필요한 tutorial part 문서

관련 운영 문서:

- 가이드: `docs/tutorial/LLM_TUTORIAL_GUIDE.md`
- Step 필수요약: `docs/tutorial/LLM_ESSENTIALS_BY_STEP.md`
- 토큰 정책: `docs/tutorial/TUTORIAL_TOKENIZATION_POLICY.md`
- 런타임 계약: `docs/tutorial/README_LLM_RUNTIME.md`
- 검증 체크리스트: `docs/tutorial/LLM_DOC_VALIDATION_CHECKLIST.md`

## 튜토리얼 폴더 목록 및 설명

### 1. Lysozyme_in_water

- 설명: 수용액 상태의 단백질(Lysozyme) 표준 워크플로우.
- 내용: topology, box/solvation, ions, EM/NVT/NPT/production, 분석.

### 2. KALP15_in_DPPC (Membrane Protein)

- 설명: 지질 이중층 막 단백질 시스템.
- 내용: 막 환경 특화 준비/평형화.

### 3. Protein_Ligand_Complex

- 설명: 단백질-리간드 복합체 워크플로우.
- 내용: ligand parameterization, 복합체 시뮬레이션, 상호작용 분석.

### 4. Umbrella_Sampling

- 설명: PMF 계산용 umbrella sampling.
- 내용: pulling, window setup, WHAM 분석.

### 5. Building_Biphasic_Systems

- 설명: 물/소수성 용매 다상 시스템.
- 내용: 상자 결합, 계면 구성.

### 6. Free_Energy_Calculations_Methane_in_Water

- 설명: 메탄 수화 자유에너지(주로 vdW decoupling) 계산.
- 내용: lambda schedule, BAR 분석.

### 7. Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol

- 설명: 에탄올 수화 자유에너지(쿨롱+vdW staged decoupling).
- 내용: 다중 람다 상태 실행/요약.

### 8. Virtual_Sites

- 설명: 선형 분자 virtual sites topology 모델링.
- 내용: 수동 topology 구성과 안정화.
