# MDP Templates Reference

`MdpComposer` 스킬이 내부적으로 사용하는 완전한 기본 템플릿 모음.

---

## Phase: `ions` (이온화 준비용 더미 Run)

```ini
; Ions Preparation — Minimal Run (nsteps=0)
integrator    = steep
nsteps        = 0
emtol         = 1000.0
emstep        = 0.01

cutoff-scheme = Verlet
; ns_type = grid  ← GROMACS 2020+에서 deprecated. Verlet scheme 사용 시 자동 처리됨.
nstlist       = 1
coulombtype   = PME
rcoulomb      = 1.0
rvdw          = 1.0
pbc           = xyz
```

---

## Phase: `minim` (에너지 최소화)

```ini
; Energy Minimization Parameters
integrator    = steep
emtol         = 1000.0    ; 수렴 기준: 최대 힘이 1000 kJ/mol/nm 이하
emstep        = 0.01      ; 초기 스텝 크기
nsteps        = 50000     ; 최대 스텝 수

; 비결합 상호작용 설정
nstlist       = 1
cutoff-scheme = Verlet
; ns_type = grid  ← GROMACS 2020+에서 deprecated. Verlet scheme 사용 시 자동 처리됨.
coulombtype   = PME
rcoulomb      = 1.0
rvdw          = 1.0
pbc           = xyz
```

---

## Phase: `nvt` (NVT 평형화, 100ps)

```ini
; NVT Equilibration Parameters
integrator    = md
nsteps        = 50000     ; 100ps (2fs * 50000)
dt            = 0.002     ; 스텝 크기 2fs

; 출력 설정
nstxout       = 500
nstvout       = 500
nstenergy     = 500
nstlog        = 500

; 비결합 상호작용
cutoff-scheme = Verlet
nstlist       = 10
rcoulomb      = 1.0
rvdw          = 1.0
coulombtype   = PME

; 온도 제어 (V-rescale)
tcoupl        = V-rescale
tc-grps       = Protein Non-Protein
tau_t         = 0.1  0.1
ref_t         = 300  300

; 압력 제어 없음
pcoupl        = no

; 위치 구속 (단백질 중원자)
define        = -DPOSRES
gen_vel       = yes
gen_temp      = 300
gen_seed      = -1
```

---

## Phase: `npt` (NPT 평형화, 100ps)

```ini
; NPT Equilibration Parameters (NVT 설정 계승 + 압력 제어 추가)
integrator    = md
nsteps        = 50000
dt            = 0.002

; 출력 설정 (NVT와 동일)
nstxout       = 500
nstvout       = 500
nstenergy     = 500
nstlog        = 500

; 비결합 상호작용
cutoff-scheme = Verlet
nstlist       = 10
rcoulomb      = 1.0
rvdw          = 1.0
coulombtype   = PME

; 온도 제어 (V-rescale)
tcoupl        = V-rescale
tc-grps       = Protein Non-Protein
tau_t         = 0.1  0.1
ref_t         = 300  300

; 압력 제어 (Parrinello-Rahman)
pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau_p         = 2.0
ref_p         = 1.0
compressibility = 4.5e-5

; 위치 구속 유지
define        = -DPOSRES
gen_vel       = no
```

---

## Phase: `md` (본 시뮬레이션)

```ini
; Production MD Parameters
integrator    = md
nsteps        = 5000000   ; 10ns (2fs * 5000000) — overrides로 조정 가능
dt            = 0.002

; 출력 빈도 (압축 궤적만 저장)
nstxout       = 0
nstvout       = 0
nstfout       = 0
nstxout-compressed = 5000  ; .xtc에 10ps마다 기록
nstenergy     = 5000
nstlog        = 5000

; 비결합 상호작용
cutoff-scheme = Verlet
nstlist       = 10
rcoulomb      = 1.0
rvdw          = 1.0
coulombtype   = PME

; 온도 제어 (V-rescale)
tcoupl        = V-rescale
tc-grps       = Protein Non-Protein
tau_t         = 0.1  0.1
ref_t         = 300  300

; 압력 제어 (Parrinello-Rahman)
pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau_p         = 2.0
ref_p         = 1.0
compressibility = 4.5e-5

; 위치 구속 없음 (Production)
define        =
gen_vel       = no
```
