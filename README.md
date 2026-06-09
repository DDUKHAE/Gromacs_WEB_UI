# Gromacs Web UI

PDB 파일 업로드 한 번으로 GROMACS 분자동역학(MD) 시뮬레이션을 브라우저에서 완전 제어하는 웹 하네스.  
LLM(Claude / Codex / Gemini)을 오케스트레이터로 활용하거나, 직접 단계별 실행도 지원합니다.

---

## Features

### 파이프라인 제어
- **3-Stage 파이프라인** — `env-builder` (Step 0–5) → `md-runner` (Step 6–7) → `illustrator` (Step 8)
- **단계별 스테퍼** — 현재 진행 단계를 한국어/영어 병기로 실시간 시각화
- **Continue / Abort** — 각 단계 완료 후 사용자가 직접 다음 단계로 진행 또는 중단

### LLM 자율 실행
- **LLM 어댑터** — Claude Code, OpenAI Codex CLI, Gemini CLI 지원
- **PTY 터미널** — xterm.js 기반 실시간 양방향 터미널 (WebSocket + PTY 프록시)
- **Permission 다이얼로그** — LLM 도구 승인 요청 자동 감지 → Y/N 팝업으로 처리

### 결과 뷰어
- **분석 갤러리** — `stage3_viz/*.xvg` 파싱 후 Canvas 2D 스파크라인 카드로 표시
- **실행 통계** — 현재 Step · Stage · 상태를 아이콘+색상 배지로 표시

### UI/UX
- **CSS 디자인 시스템** — `:root` 커스텀 프로퍼티 기반 다크 테마
- **스켈레톤 로딩** — 데이터 로드 중 shimmer 애니메이션
- **Toast 알림** — 성공/오류/경고 비침습적 알림
- **온보딩 모달** — 첫 방문 시 워크플로우 안내
- **파라미터 툴팁** — Force field / Water model / Box type 설명
- **반응형 레이아웃** — 768px / 480px 브레이크포인트
- **접근성** — ARIA 레이블, role 속성, 키보드 탐색, aria-live 실시간 영역

---

## Directory Layout

```
.
├── main.py                    서버 진입점 (uvicorn 래퍼)
├── pyproject.toml             Python 패키지 설정
├── requirements.txt           의존성
├── AGENTS.md                  LLM 운영 규칙 + skill 자원 매핑
├── ARCHITECTURE.md            Step 0–8 계약, 3-skill 매핑
│
├── web/                       FastAPI 웹 서버
│   ├── server.py              REST API + WebSocket 엔드포인트
│   ├── llm_runner.py          PTY 기반 LLM 프로세스 관리
│   ├── runner.py              직접 실행 subprocess 래퍼
│   ├── run_reader.py          실행 상태 파일 파서
│   ├── llm_adapters/          Claude / Codex / Gemini CLI 어댑터
│   └── static/
│       ├── index.html         단일 페이지 프론트엔드 (vanilla JS)
│       ├── xterm.js           터미널 에뮬레이터
│       └── xterm-addon-fit.js 터미널 자동 크기 조정
│
├── skills/                    3개 파이프라인 스킬
│   ├── env_builder/           Step 0–5: topology / box / solvate / ions
│   ├── md_runner/             Step 6–7: grompp + mdrun, retry 처리
│   └── illustrator/           Step 8: RMSD/RMSF/PCA + 플롯 + 리포트
│
├── lib/                       내부 공용 라이브러리
│   ├── xvg_parser.py          XVG 파일 파서 (갤러리용)
│   ├── state.py               workspace/state.json 입출력
│   ├── validators.py          Step별 검증 게이트
│   ├── gmx_wrapper.py         GROMACS 명령 래퍼
│   ├── tutorial_registry.py   튜토리얼 라우팅
│   └── mdp_templates/         MDP 파라미터 템플릿
│
└── docs/
    ├── STATE_SCHEMA.md        state.json 공식 스키마
    ├── pipeline_contract.md   Step별 입출력/안전 계약
    ├── WARNING_FLOW.md        사용자 결정형 WARNING 분기
    ├── runbook.md             수동 복구 절차
    └── tutorial/              8개 튜토리얼 매니페스트 + LLM 가이드
```

---

## Prerequisites

| 항목 | 비고 |
|------|------|
| Python 3.11+ | |
| GROMACS (`gmx` on PATH) | `conda-forge::gromacs` 권장 |
| `pip install -r requirements.txt` | FastAPI, uvicorn 포함 |
| matplotlib (선택) | illustrator 플롯 |
| PyMOL 또는 VMD (선택) | 구조 렌더링 |
| ffmpeg (선택) | 트래젝토리 애니메이션 |
| Claude Code / Codex / Gemini CLI (선택) | LLM 자율 실행 |

---

## Quick Start

```bash
# 1. 저장소 클론
git clone https://github.com/DDUKHAE/Gromacs_WEB_UI.git
cd Gromacs_WEB_UI

# 2. GROMACS 환경 구성 (conda 권장)
conda create -n gromacs -y -c conda-forge gromacs python=3.11
conda activate gromacs

# 3. Python 의존성 설치
pip install -r requirements.txt

# 4. 서버 실행 → 브라우저 자동 오픈
python main.py
```

브라우저가 자동으로 `http://localhost:8000` 을 엽니다.

```bash
python main.py --port 8080       # 포트 변경
python main.py --host 0.0.0.0    # 외부 접속 허용
python main.py --no-browser      # 브라우저 자동 오픈 비활성화
```

---

## Web UI 사용 방법

### 새 시뮬레이션 시작

1. **New Run** 패널에서 PDB 파일 선택
2. Force field / Water model / Box type 파라미터 설정 (툴팁으로 각 옵션 설명 확인 가능)
3. LLM 선택 (선택사항) — 미선택 시 직접 단계 제어 모드
4. **Start** 클릭

### LLM 모드

- LLM이 Step 0–8을 자율 실행
- 도구 승인 요청 발생 시 Permission 다이얼로그 자동 팝업 → Y/N 응답
- 터미널에서 LLM 출력 실시간 확인

### 직접 제어 모드

- `env-builder` 완료 후 **Continue** → `md-runner` 시작
- `md-runner` 완료 후 **Continue** → `illustrator` 시작
- 언제든 **Abort** 로 중단 가능

### 결과 확인

- 시뮬레이션 완료 후 **Results Gallery** 패널에서 RMSD, RMSF, 에너지 등 분석 그래프 확인

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/runs` | 실행 목록 조회 |
| `POST` | `/api/runs` | 새 실행 생성 (PDB 업로드) |
| `GET` | `/api/runs/{run_id}` | 실행 상세 + 로그 |
| `GET` | `/api/runs/{run_id}/artifacts` | XVG 분석 결과 목록 |
| `POST` | `/api/runs/{run_id}/action` | `continue` / `abort` |
| `GET` | `/api/llms` | 사용 가능한 LLM 목록 |
| `WS` | `/ws/runs/{run_id}` | 터미널 스트림 (바이너리 PTY + JSON 이벤트) |

---

## 3-Skill 파이프라인

```
PDB 파일
  │
  ▼
env-builder  (Step 0–5)
  ├─ Step 0: 하드웨어 프로파일 + 상태 초기화
  ├─ Step 1: Topology 생성 (gmx pdb2gmx)
  ├─ Step 2: Box 정의 (gmx editconf)
  ├─ Step 3: 용매화 (gmx solvate)
  ├─ Step 4: Ion 준비 (gmx grompp)
  └─ Step 5: Ion 주입 (gmx genion)
  │
  ▼
md-runner    (Step 6–7)
  ├─ Step 6: EM / NVT / NPT 준비 (gmx grompp × 4)
  └─ Step 7: Production MD (gmx mdrun)
  │
  ▼
illustrator  (Step 8)
  ├─ RMSD, RMSF, PCA, DSSP, SASA 분석
  ├─ matplotlib 플롯 + XVG 파싱
  └─ markdown 리포트 → stage3_viz/
```

각 skill은 `workspace/state.json` + 디렉터리만 공유합니다.  
외부 도구(CHARMM-GUI 등) 산출물로 `md-runner`나 `illustrator`만 단독 진입 가능 — [`docs/independent_entry_guide.md`](docs/independent_entry_guide.md) 참조.

---

## 지원 튜토리얼

| 튜토리얼 | 대상 |
|----------|------|
| Lysozyme in Water | 기본 단백질 MD |
| KALP15 in DPPC | 막 단백질 |
| Protein-Ligand Complex | 단백질-리간드 결합 |
| Umbrella Sampling | 자유에너지 샘플링 |
| Building Biphasic Systems | 이상계 시스템 |
| Free Energy (Methane) | 수화 자유에너지 |
| Free Energy (Ethanol) | 수화 자유에너지 |
| Virtual Sites | 가상 사이트 |

---

## Documentation

| 문서 | 용도 |
|------|------|
| [`AGENTS.md`](AGENTS.md) | LLM 운영 규칙 + skill 자원 매핑 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Step 0–8 계약, 3-skill 매핑 |
| [`docs/STATE_SCHEMA.md`](docs/STATE_SCHEMA.md) | `workspace/state.json` 공식 스키마 |
| [`docs/pipeline_contract.md`](docs/pipeline_contract.md) | Step별 입출력/안전 계약 |
| [`docs/WARNING_FLOW.md`](docs/WARNING_FLOW.md) | 사용자 결정형 WARNING 분기 |
| [`docs/runbook.md`](docs/runbook.md) | 수동 복구 절차 |
| [`docs/tutorial/LLM_TUTORIAL_GUIDE.md`](docs/tutorial/LLM_TUTORIAL_GUIDE.md) | 튜토리얼 라우팅 결정 트리 |

---

## License

MIT — [`LICENSE`](LICENSE) 참조.

GROMACS 자체는 LGPL-2.1로 별도 배포되며, 이 저장소는 GROMACS를 호출만 합니다.
