# System Builder — 설계 문서

**작성일:** 2026-06-11  
**상태:** 승인됨 (구현 대기)  
**구현 범위:** Phase 1 — Solution Builder  
**문서 범위:** Phase 1 구현 명세 + Phase 2~5 확장 로드맵

---

## 1. 배경 및 목적

현재 Gromacs Web UI는 LLM이 Steps 0~8을 자율 실행한다. 사용자는 어떤 파라미터(박스 크기, 이온 농도 등)가 사용됐는지 실행 후에야 확인할 수 있고, 동일 설정으로 재실행하려면 처음부터 다시 튜토리얼을 따라야 한다.

**목적:**
- **가시성(Visibility):** 시스템 구성 파라미터를 실행 전에 사용자가 직접 보고 제어
- **재현성(Reproducibility):** 설정을 프리셋으로 저장하고 재사용·공유

CHARMM-GUI를 참고 레퍼런스로 삼되, 현재 프로젝트의 LLM 실행 자동화 강점을 유지하는 방향으로 설계한다.

---

## 2. 핵심 설계 원칙

1. **하위 호환성 보장:** `system_config.json`이 없으면 기존 동작 완전 유지
2. **LLM 역할 유지:** Builder는 설정만 담당, 실행·에러처리·재시도는 여전히 LLM
3. **점진적 노출:** 기본 UI는 단순하게, Expert 토글로 고급 파라미터 추가 노출
4. **확장 가능 구조:** Phase 2~5 Builder 모듈을 플러그인 방식으로 추가 가능

---

## 3. 아키텍처 개요

```
┌──────────────────────────────────────────────────────────────┐
│                   System Builder (Phase 1)                    │
│                                                               │
│  [마법사 UI]  →  system_config.json  →  [LLM 파이프라인]     │
│                                                               │
│  Step 1: PDB 업로드                                           │
│  Step 2: Force Field · Water Model      (pdb2gmx)            │
│  Step 3: Box 설정 (크기·형태)            (editconf)           │
│  Step 4: 이온 설정 (종류·농도)           (solvate → genion)  │
│  [Expert] Step 5: 시뮬레이션 파라미터   (.mdp)               │
│  Step 6: 검토 · 프리셋 저장 · 런 시작                        │
└──────────────────────────────────────────────────────────────┘
          ↓  system_config.json 생성
┌──────────────────────────────────────────────────────────────┐
│               LLM Runner (기존, 최소 변경)                    │
│                                                               │
│  system_config.json 존재 → 프롬프트에 제약 블록 주입         │
│  파일 없음 → 기존 동작 그대로 (튜토리얼 자율 결정)           │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. UI — 마법사 단계 명세

### 진입점
기존 "런 생성" 버튼 → 현재 단순 모달 대신 멀티스텝 마법사 모달로 교체.  
마법사 없이 빠른 생성도 "Skip Builder" 옵션으로 제공 (하위 호환).

### Step 1 — 구조 파일 업로드
| 항목 | 내용 |
|------|------|
| 입력 | PDB 파일 드래그&드롭 또는 클릭 업로드 |
| 재사용 | 기존 런에서 구조 파일 선택 가능 |
| 자동 표시 | 분자명, 원자 수, 체인 수, 리간드 포함 여부 |

### Step 2 — Force Field & Water Model
| 항목 | 내용 |
|------|------|
| Force Field | 설치된 목록 드롭다운 (기본: charmm36-jul2022) |
| Water Model | TIP3P / SPC/E / TIP4P 등 (기본: TIP3P) |
| 터미널 처리 | 자동 / 수동 선택 |

### Step 3 — 박스 설정
| 항목 | 내용 |
|------|------|
| 박스 형태 | Cubic / Dodecahedron / Octahedron (모식도 표시) |
| 여백 거리 | 분자↔벽 최소 거리 nm (기본: 1.0 nm) |
| 경고 | 예상 원자 수 / 시스템 크기 경고 |

### Step 4 — 이온 설정
| 항목 | 내용 |
|------|------|
| 이온 종류 | NaCl / KCl / MgCl₂ 등 |
| 농도 | 단위 M (기본: 0.15 M) |
| 전하 중성화 | 자동 체크박스 |
| 자동 계산 | 시스템 순 전하, 추가될 이온 수 미리보기 |

### Step 5 — 시뮬레이션 파라미터 (Expert 토글 시만 표시)
| 항목 | 내용 |
|------|------|
| 온도 | K 단위 (기본: 300 K) |
| 압력 | bar 단위 (기본: 1.0 bar) |
| 시뮬레이션 시간 | ns 단위 (기본: 1.0 ns) |
| Thermostat | V-rescale / Nosé-Hoover |
| Barostat | Parrinello-Rahman / Berendsen |

Expert 토글은 Step 3과 Step 4 사이에 배치. 비활성화 시 기본값이 `system_config.json`에 기록됨.

### Step 6 — 검토 · 프리셋 · 시작
| 항목 | 내용 |
|------|------|
| 설정 요약 | 전체 파라미터 읽기 전용 표시 |
| 프리셋 저장 | 이름 입력 후 저장 (선택사항) |
| 프리셋 불러오기 | 저장된 프리셋 드롭다운 (선택 시 Step 2~5 자동 채움) |
| LLM 선택 | 기존 드롭다운 |
| 시작 | `system_config.json` 생성 후 런 시작 |

---

## 5. 데이터 모델

### `system_config.json` 스키마

```json
{
  "version": "1.0",
  "builder_type": "solution",

  "structure": {
    "pdb_filename": "1AKI.pdb"
  },

  "forcefield": {
    "name": "charmm36-jul2022",
    "water_model": "tip3p",
    "terminal_patches": "auto"
  },

  "box": {
    "type": "dodecahedron",
    "edge_distance_nm": 1.0
  },

  "ions": {
    "salt_type": "NaCl",
    "concentration_M": 0.15,
    "neutralize": true
  },

  "simulation": {
    "_expert_mode": false,
    "temperature_K": 300,
    "pressure_bar": 1.0,
    "sim_time_ns": 1.0,
    "thermostat": "V-rescale",
    "barostat": "Parrinello-Rahman"
  },

  "meta": {
    "preset_name": "Lysozyme Standard",
    "created_at": "2026-06-11T10:00:00",
    "builder_version": "1.0"
  }
}
```

**필드 규칙:**
- `builder_type`: Phase 2~5 확장 시 `"membrane"`, `"ligand"`, `"qmmm"`, `"multicomponent"` 추가
- `simulation._expert_mode`: `false`이면 기본값, `true`이면 사용자 입력값
- 모든 필드는 선택사항 — 없으면 LLM이 튜토리얼 기본값 사용

### 파일 저장 위치

```
runs/
└── {run_id}/
    └── system_config.json      ← 이 런의 설정

presets/                         ← 프로젝트 루트 신규 디렉토리
├── Lysozyme_Standard.json
├── Protein_Ligand_Basic.json
└── ...
```

---

## 6. 백엔드 변경 명세

### 6-1. `web/server.py` — 새 API 엔드포인트

```
GET  /api/presets              → presets/ 디렉토리 목록 반환
POST /api/presets              → 새 프리셋 저장 (body: {name, config})
DELETE /api/presets/{name}     → 프리셋 삭제

POST /api/runs  (기존)         → body에 system_config 필드 추가 (선택)
                                 존재 시 runs/{id}/system_config.json 저장
```

### 6-2. `web/llm_runner.py` — 제약 주입

런 시작 시 `system_config.json` 존재 여부 확인 후 프롬프트에 제약 블록 주입:

```python
config_path = run_dir / "system_config.json"
if config_path.exists():
    config = json.loads(config_path.read_text())
    prompt += build_system_config_constraint(config)
```

`build_system_config_constraint()` 출력 예시:

```
[SYSTEM BUILDER CONSTRAINTS — MUST FOLLOW EXACTLY]
The user has pre-configured this system via the System Builder.
You MUST use these parameters without modification:

- Force field: charmm36-jul2022
- Water model: tip3p
- Box type: dodecahedron, edge distance: 1.0 nm
- Ions: NaCl at 0.15 M, neutralize=true
- Temperature: 300 K, Pressure: 1.0 bar
- Simulation time: 1.0 ns

Do NOT override these settings based on tutorial defaults.
```

### 6-3. `lib/system_config_validator.py` — 사후 검증 (신규)

`TutorialAuditor`와 동일한 패턴으로, 실행 완료 후 `system_config.json`과 실제 사용된 파라미터를 비교해 위반 항목을 `audit` 결과에 포함.

### 6-4. `web/static/index.html` — 마법사 UI

기존 "런 생성" 모달 → 멀티스텝 마법사로 교체.  
"Skip Builder" 버튼으로 기존 단순 생성도 지원.

---

## 7. 확장 로드맵 (문서화 — 미구현)

향후 각 Phase는 `BuilderModule` 추상 클래스를 구현하는 플러그인으로 추가.  
`builder_type` 필드로 라우팅, 기존 Solution Builder 코드 변경 없음.

| Phase | Builder 유형 | 주요 추가 설정 | 비고 |
|-------|------------|--------------|------|
| 1 ✅ | Solution | 박스·물·이온 | 현재 구현 범위 |
| 2 | Membrane | 지질 종류·조성·두께, 단백질 삽입 위치·각도 | CHARMM-GUI 생성 파일 import 또는 자체 구현 |
| 3 | Ligand Binder | 리간드 파라미터화(CGenFF/GAFF), FEP 람다 스케줄 | acpype 연동 |
| 4 | QM/MM | QM 영역 원자 선택, 양자 계산 방법(DFT 등) | ORCA/CP2K 인터페이스 |
| 5 | Multicomponent | 다중 분자 조합, PBC 어셈블리, 상대적 위치/회전 | gmx insert-molecules |

### `BuilderModule` 인터페이스 (스텁 — Phase 2부터 구현)

```python
class BuilderModule:
    builder_type: str                          # "solution", "membrane", ...

    def validate_config(self, config: dict) -> list[str]:
        """설정 유효성 검사. 오류 메시지 목록 반환."""
        ...

    def build_constraint_prompt(self, config: dict) -> str:
        """LLM 제약 블록 생성."""
        ...

    def get_wizard_schema(self) -> dict:
        """마법사 UI가 렌더링할 폼 스키마 반환."""
        ...
```

---

## 8. 미결 사항 (구현 시 결정)

- 마법사에서 PDB 파일을 업로드하면 원자 수 파싱을 어디서 할지 (프론트엔드 vs 백엔드)
- `presets/` 디렉토리 위치: 프로젝트 루트 vs `~/.gromacs_webui/presets/` (사용자 전역)
- Expert 모드 기본값을 마지막 사용 상태로 기억할지 여부
