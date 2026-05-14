# LLM Tutorial Guide

## Purpose

이 문서는 TutorialRouter가 입력 목표와 가용 입력을 기반으로 어떤 튜토리얼을 우선 읽을지 결정하는 운영 기준이다.

## Routing Priority

1. 사용자 목표의 명시 키워드
2. 필수 입력 충족 여부
3. manifest 존재 여부
4. `tutorial_index.json`의 `system_type`, `domain`, `confidence`
5. fallback: `Lysozyme_in_water`

## Domain Routing Tree

- Protein in water 기본 MD
  - 조건: `protein_pdb`만으로 시작 가능
  - 선택: `Lysozyme_in_water`
- Membrane protein
  - 조건: `membrane_composition` 및 막 구성 전제 충족
  - 선택: `KALP15_in_DPPC`
- Protein-ligand complex
  - 조건: `ligand_structure`, `ligand_parameterization_ready`
  - 선택: `Protein_Ligand_Complex`
- Umbrella sampling
  - 조건: `reaction_coordinate_definition`, `window_schedule_defined`
  - 선택: `Umbrella_Sampling`
- Free energy
  - 조건: `lambda_schedule` 또는 `coulomb_vdw_lambda_schedule`
  - 선택: `Free_Energy_Calculations_Methane_in_Water` 또는 ethanol tutorial
- Biphasic/virtual-sites
  - 조건: topology 수동 편집/시스템 수동 조립 전제
  - 선택: 대응 튜토리얼, 단 `unsupported_autonomy_level` 검사 필수

## Minimal Read Path

1. `docs/tutorial/TUTORIAL_OVERVIEW.md`
2. `docs/tutorial/tutorial_index.json`
3. 선택 튜토리얼의 `tutorial.manifest.json` (있을 경우)
4. `recommended_docs.minimal`
5. 실행 Step와 직접 관련된 part 문서만 추가 로딩

## Deep Read Path

- 최소 경로 + `recommended_docs.deep` + 분석/심화 part
- 첫 진입 도메인이 free energy, umbrella, membrane인 경우 deep path 권장

## Manifest/Fallback Policy

- manifest 존재 시: manifest가 runtime truth
- manifest 부재 시: `tutorial_index.json`의 `derived=true` 엔트리 사용
- fallback 순서:
  1. `tutorial_index.json` 후보 필터
  2. `TUTORIAL_OVERVIEW.md` 목적 확인
  3. `recommended_docs.minimal` 로딩
  4. 입력 누락/리스크 점검 후 계속 또는 FAIL

## Mandatory Rules Binding

Router가 문서를 선택하더라도 아래 항목은 반드시 충족해야 한다.

- 상태 추적: Step 시작 전/종료 후 `simulation_state.json` 갱신
- topology 보호: Step 3, Step 5 전 `topol.top.bak` 생성
- 하드웨어 인식: Step 0에서 자원 탐지 후 `-ntomp`, `-gpu_id` 조정
- 재시도 제약: 동일 command string/동일 파라미터 재시도 금지
- 대용량 파일 처리: `.xvg` 직접 읽지 않고 parser utility 사용

## Stop Conditions

아래는 즉시 FAIL 또는 제한 실행으로 전환한다.

- `missing_inputs`가 비어있지 않음
- `unsupported_autonomy_level`이 `manual_prerequisite_required` 이상이고 전제 불충족
- ligand/membrane/free-energy 필수 전처리 누락
- Step 0-8에 매핑 불가능한 사용자 목표

## Router Output Contract

- `confidence`: `high | medium | low`
- `missing_inputs`: 즉시 준비가 필요한 입력 목록
- `unsupported_reason`: 자동 실행 제한 사유
- `selected_docs`: 이번 런에 실제로 읽을 문서 경로 목록
