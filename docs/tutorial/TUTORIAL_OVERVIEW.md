# GROMACS Tutorial Overview

이 문서는 GROMACS 하네스(Agent) 환경에서 참고하고 활용할 수 있도록 정리된 튜토리얼 문서들의 전체 개요를 설명합니다. 각 튜토리얼 폴더는 특정한 분자 동역학(Molecular Dynamics, MD) 시뮬레이션 목적과 방법론을 다루며, 모든 문서는 시스템 자동화와 에이전트 파싱을 고려하여 논리적인 단계별 마크다운(Markdown) 형태로 통일되어 있습니다.

## 튜토리얼 폴더 목록 및 설명

### 1. Lysozyme_in_water
- **설명**: 수용액 상태의 단백질(Lysozyme)을 모의실험하는 가장 기초적이고 표준적인 튜토리얼입니다. 
- **내용**: PDB 구조 변환, 상자(Box) 생성 및 용매화(Solvation), 이온 추가, 에너지 최소화(EM), 평형화(NVT, NPT), 최종 프로덕션 MD 및 기본 궤적 분석 방법 등을 다룹니다.

### 2. KALP15_in_DPPC (Membrane Protein)
- **설명**: 지질 이중층(DPPC)에 삽입된 막 단백질(KALP15 펩타이드) 시스템을 구성하고 시뮬레이션하는 튜토리얼입니다.
- **내용**: 소수성 지질 막 내부에 단백질을 배치하는 방법(`InflateGRO` 등)과 특수 막 평형화 과정을 다룹니다.

### 3. Protein_Ligand_Complex
- **설명**: 단백질과 리간드 복합체의 토폴로지를 생성하고 모의실험을 진행하는 튜토리얼입니다.
- **내용**: CGenFF 등을 활용하여 GROMACS에서 기본적으로 지원하지 않는 소분자 리간드의 파라미터를 생성하는 방법, 단백질과 리간드 간 상호작용 에너지 및 수소 결합 분석 등을 다룹니다.

### 4. Umbrella_Sampling
- **설명**: 우산 표집(Umbrella Sampling) 기법을 이용해 Potential of Mean Force (PMF) 프로파일을 도출하는 튜토리얼입니다.
- **내용**: 펩타이드를 단백질에서 떼어내는 당기기 시뮬레이션(Steered MD), 위치 제어, 반응 좌표(Reaction Coordinate) 설정, WHAM을 이용한 자유 에너지 계산을 다룹니다.

### 5. Building_Biphasic_Systems
- **설명**: 물과 소수성 용매(Cyclohexane)로 이루어진 다상(Biphasic) 시스템을 구축하는 튜토리얼입니다.
- **내용**: 두 개의 서로 다른 층이 만나는 경계면 시뮬레이션을 위해 개별 상자를 만들고 결합하는 `insert-molecules`와 `genconf`, `editconf` 활용법을 다룹니다.

### 6. Free_Energy_Calculations_Methane_in_Water
- **설명**: 물 속 메탄(Methane) 분자의 반데르발스(van der Waals) 상호작용을 서서히 줄여가며(Decoupling) 자유 에너지를 계산하는 튜토리얼입니다.
- **내용**: 자유 에너지 섭동의 기초 이론, 람다(λ) 파라미터 벡터를 이용한 시뮬레이션 설정, Bennett Acceptance Ratio (BAR) 방법(`gmx bar`)을 활용한 자유 에너지 차이(ΔG) 도출을 다룹니다.

### 7. Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol
- **설명**: 메탄 튜토리얼에서 한 단계 나아가, 쿨롱 상호작용(Coulombic)과 반데르발스 상호작용을 모두 변환하여 에탄올의 수화 자유 에너지(Hydration Free Energy)를 도출하는 심화 튜토리얼입니다.
- **내용**: 다중 람다(λ) 상태를 순차적으로 끄고 켜는(Decoupling) 워크플로우 설정법을 중점적으로 다룹니다.

### 8. Virtual_Sites
- **설명**: 선형 분자(Linear molecule, 예: CO2) 모델링 시 발생하는 구조적 불안정성을 해결하기 위해 가상 사이트(Virtual Sites)를 구축하는 튜토리얼입니다.
- **내용**: 관성 모멘트를 보존하기 위한 수학적 계산과, `[ virtual_sites2 ]` 지시어를 활용한 토폴로지 수동 구성 방법을 다룹니다.

---

이 문서들을 기반으로 에이전트 환경의 `GmxExecutor` 및 `SystemValidator`는 다양한 GROMACS 워크플로우를 자율적이고 일관되게 수행 및 모니터링할 수 있습니다. 각 하위 폴더에는 세부 단계별로 분리된 마크다운 문서가 준비되어 있습니다.
