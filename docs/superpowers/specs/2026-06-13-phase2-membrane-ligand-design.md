# Phase 2: Membrane Builder + Ligand Parameterization — Design Spec

**Date:** 2026-06-13  
**Phase:** 2  
**Scope:** Two independent builder modules added to the Gromacs Web UI System Builder  
**Prerequisite:** Phase 1 Solution Builder enhancement (complete)

---

## 1. Goals

Add two new simulation preparation modules:

1. **Membrane Builder** — Build lipid bilayer systems (membrane-only or protein+membrane) using `packmol-memgen` (AmberTools).
2. **Ligand Parameterization** — Parameterize small-molecule ligands with ACPYPE (GAFF2) and assemble protein-ligand complex topologies.

Both modules are independent of each other and of the existing Solution Builder.

---

## 2. Architecture Overview

### 2-1. UI Integration

The existing launch screen ("New Simulation / Visualization / Virtual Run") gains two new cards:

```
[ Simulation (Solution) ]  [ Membrane Builder ]  [ Protein-Ligand ]
[ Visualization          ]  [ Virtual Run      ]
```

Each new card launches an independent multi-step wizard page (not embedded in the existing Solution Builder wizard).

### 2-2. New Files

| File | Responsibility |
|------|---------------|
| `lib/membrane_builder.py` | packmol-memgen wrapper + lipid catalogue |
| `lib/ligand_params.py` | ACPYPE wrapper + complex assembler |
| `tests/test_membrane_builder.py` | Unit tests for membrane_builder |
| `tests/test_ligand_params.py` | Unit tests for ligand_params |
| `tests/test_membrane_api.py` | Integration tests for membrane API endpoints |
| `tests/test_ligand_api.py` | Integration tests for ligand API endpoints |

### 2-3. Modified Files

| File | Change |
|------|--------|
| `web/server.py` | Add 5 new API endpoints inside `create_app()` |
| `web/static/index.html` | Add Membrane Builder page, Ligand Builder page, launch cards |
| `lib/system_config.py` | Extend `build_constraint_prompt()` for membrane/ligand blocks |

### 2-4. Shared Dependency

Both modules depend on **AmberTools** (conda-only):
```
conda install -c conda-forge ambertools
```
`packmol-memgen` and `acpype` are both included in AmberTools. No pip package is available; `requirements.txt` gets a comment-only note.

### 2-5. system_config.json v1.2 Extensions

```json
{
  "build_type": "solution" | "membrane" | "ligand",
  "membrane": {
    "lipids_upper": [{"name": "POPC", "fraction": 0.6}, {"name": "CHL1", "fraction": 0.4}],
    "lipids_lower": [{"name": "POPC", "fraction": 0.6}, {"name": "CHL1", "fraction": 0.4}],
    "protein_pdb": "protein.pdb",
    "protein_orientation": "opm" | "auto" | "manual",
    "water_z_nm": 2.0,
    "salt_M": 0.15
  },
  "ligand": {
    "residue_name": "LIG",
    "net_charge": 0,
    "atom_type": "gaff2",
    "itp_file": "LIG.itp",
    "gro_file": "LIG.gro",
    "complex_gro": "complex.gro",
    "topol_top": "topol.top"
  }
}
```

---

## 3. Module A: Membrane Builder

### 3-1. UI — 4-Step Wizard

**Step 1: Protein (optional)**
- Toggle: "Membrane only" (default OFF → protein+membrane)
- When OFF: PDB upload or PDB ID fetch (reuses Phase 1 `_analyzePDBStructure` / `fetchPDBFromRCSB`)
- Protein orientation selector: `Pre-oriented (OPM DB — user uploads pre-oriented PDB)` / `Auto-orient (packmol-memgen --orient)` / `Manual (no reorientation)`
- When ON (membrane only): skip protein inputs

**Step 2: Membrane Composition**
- Upper leaflet table: rows of `[lipid dropdown] [fraction %] [remove]` + `[+ Add Lipid]`
- Lower leaflet table: same structure; "Copy from upper" button
- Supported lipids (8 species):

| ID | Full Name | Typical use |
|----|-----------|-------------|
| POPC | 1-palmitoyl-2-oleoyl-sn-glycero-3-phosphocholine | Generic PC bilayer |
| POPE | 1-palmitoyl-2-oleoyl-sn-glycero-3-phosphoethanolamine | PE component |
| POPS | 1-palmitoyl-2-oleoyl-sn-glycero-3-phospho-L-serine | Anionic, charge −1 |
| DPPC | 1,2-dipalmitoyl-sn-glycero-3-phosphocholine | Gel-phase studies |
| DPPE | 1,2-dipalmitoyl-sn-glycero-3-phosphoethanolamine | Saturated PE |
| DPPS | 1,2-dipalmitoyl-sn-glycero-3-phospho-L-serine | Saturated PS |
| CHL1 | Cholesterol | Raft, fluidity modulation |
| PSM | Palmitoyl sphingomyelin | Raft domains |

- Frontend validation: fractions per leaflet must sum to 100%; submit blocked otherwise
- Estimated bilayer thickness displayed (read-only, computed from lipid composition lookup table)

**Step 3: Box & Solvent**
- Protein–membrane minimum distance: default 1.0 nm
- Water layer thickness (z): default 2.0 nm
- Ion concentration: default 0.15 M NaCl

**Step 4: Simulation Parameters**
- Reuses existing Expert MDP rows from Solution Builder Step 5 (dt, cutoffs, PME, constraints)

### 3-2. Backend — `lib/membrane_builder.py`

```python
SUPPORTED_LIPIDS: list[dict]  # name, full_name, charge, description

def is_packmol_memgen_available() -> bool:
    """Check shutil.which('packmol-memgen')."""

def list_supported_lipids() -> list[dict]:
    """Return SUPPORTED_LIPIDS catalogue."""

def build_membrane(config: dict, workspace: Path) -> dict:
    """
    Run packmol-memgen. Returns:
      {"available": True, "gro": str, "top": str}   on success
      {"available": False, ...}                       when tool missing
      {"available": True, "error": str}               on tool failure
    config keys: lipids_upper, lipids_lower, protein_pdb (optional),
                 protein_orientation, water_z_nm, salt_M
    """
```

packmol-memgen invocation pattern:
```bash
packmol-memgen \
  [--pdb protein.pdb] \
  --lipids POPC:POPE:CHL1 \
  --ratio 60:30:10 \
  --dist 1.0 \
  --water_z 2.0 \
  --salt 0.15 \
  --notprotonate --nottrim \
  --output membrane_system
```

For membrane-only runs, `--pdb` is omitted.

### 3-3. API Endpoints

```
GET  /api/membrane/status
     → {"available": bool, "version": str | null}

GET  /api/membrane/lipids
     → [{"name": "POPC", "full_name": "...", "charge": 0, ...}, ...]

POST /api/membrane/build
     body (multipart): config_json (Form), protein_pdb (UploadFile, optional)
     → {"gro": "<content>", "top": "<content>"}   on success
     → HTTP 503 {"detail": "packmol-memgen not installed"}   when unavailable
     → HTTP 422 on validation error
```

### 3-4. LLM Prompt Injection

`build_constraint_prompt()` extended for `membrane` block:

```
[MEMBRANE BUILDER CONSTRAINTS — MUST FOLLOW EXACTLY]
- Build type: membrane
- Upper leaflet: POPC 60%, POPE 30%, CHL1 10%
- Lower leaflet: POPC 60%, POPE 30%, CHL1 10%
- Protein insertion: yes (orientation: opm)
- Water layer: 2.0 nm, Salt: 0.15 M NaCl
- Force field: CHARMM36 (required for membrane lipids)
Use the pre-built membrane topology; do NOT rebuild the bilayer.
```

---

## 4. Module B: Ligand Parameterization

### 4-1. UI — 3-Step Wizard

**Step 1: Protein + Ligand Input**
- Protein: PDB upload or PDB ID fetch (Phase 1 reuse)
- Ligand file upload: accepts `.pdb`, `.mol2`, `.sdf`
- Ligand net charge: integer input (default 0; required for ACPYPE)
- Ligand residue name: 3-char input (default "LIG")

**Step 2: Parameterization**
- Force field selector: `GAFF2` (default) / `GAFF`
- "Run ACPYPE" button → progress spinner
- Result panel (on success):
  - File list: `LIG.itp`, `LIG.gro`, `posre_LIG.itp`
  - Penalty score display
  - Warning badge if penalty > 10: "Parameter quality review recommended"
  - Error if penalty > 50: user must confirm to proceed

**Step 3: Complex Assembly**
- Summary panel: protein chain count, residue count, ligand atom count
- Box type / size / ions (reuses Solution Builder Step 3–4 components)
- "Assemble Complex" button → `complex.gro` + `topol.top` generated
- Download links for both files

### 4-2. Backend — `lib/ligand_params.py`

```python
def is_acpype_available() -> bool:
    """Check shutil.which('acpype')."""

def run_acpype(
    ligand_path: Path,
    charge: int = 0,
    atom_type: str = "gaff2",
    residue_name: str = "LIG",
) -> dict:
    """
    Run ACPYPE in a TemporaryDirectory.
    Returns:
      {"available": True, "itp": str, "gro": str, "posre": str, "penalty": float}
      {"available": False, "itp": "", "gro": "", "posre": "", "penalty": 0.0}
      {"available": True, "error": str, "penalty": float}
    """

def assemble_complex(
    protein_pdb: Path,
    ligand_gro: Path,
    ligand_itp: Path,
    workspace: Path,
) -> dict:
    """
    Assemble protein-ligand complex:
    1. gmx editconf: protein PDB → protein.gro
    2. Merge protein.gro + ligand.gro coordinate blocks (pure Python)
    3. Write topol.top with #include "LIG.itp" and updated [ molecules ]
    Returns {"complex_gro": str (content), "topol_top": str (content)}
    """
```

ACPYPE invocation:
```bash
acpype -i ligand.pdb -n 0 -a gaff2 -r LIG
```

### 4-3. API Endpoints

```
GET  /api/ligand/status
     → {"available": bool, "version": str | null}

POST /api/ligand/parameterize
     body (multipart): ligand (UploadFile), charge (Form int),
                       atom_type (Form str), residue_name (Form str)
     → {"itp": "...", "gro": "...", "posre": "...", "penalty": 4.2}
     → HTTP 503 when acpype unavailable
     → HTTP 422 on validation error

POST /api/ligand/assemble
     body (multipart): protein_pdb (UploadFile), ligand_gro (UploadFile),
                       ligand_itp (UploadFile), box_config (Form JSON)
     → {"complex_gro": "...", "topol_top": "..."}
```

### 4-4. LLM Prompt Injection

`build_constraint_prompt()` extended for `ligand` block:

```
[LIGAND CONSTRAINTS — MUST FOLLOW EXACTLY]
- Ligand: LIG (GAFF2, net charge 0)
- Pre-parameterized: LIG.itp provided
- Complex topology: protein + LIG pre-assembled
- Include LIG.itp via #include "LIG.itp" in topol.top
- Position restraints: posre_LIG.itp available
Do NOT re-run ACPYPE; use provided parameter files.
```

---

## 5. Error Handling

| Situation | Handling |
|-----------|----------|
| packmol-memgen / acpype not installed | `{"available": False, ...}` graceful fallback; HTTP 503 from API |
| packmol-memgen stderr non-empty | Save to `membrane_error.log`; return first 500 chars in response |
| ACPYPE penalty 10–50 | Return with `"warning": "high_penalty"`; user proceeds at own risk |
| ACPYPE penalty > 50 | Return with `"error": "penalty_too_high"`; UI requires confirmation |
| Lipid fractions ≠ 100% | Frontend validation blocks submit |
| Ligand file parse failure | HTTP 400 "Unsupported format or corrupt file" |
| Complex GRO atom overlap | Detected by `gmx check` post-assembly; returned as warning |

---

## 6. Testing Strategy (TDD)

### `tests/test_membrane_builder.py`
- `test_is_packmol_memgen_available_returns_bool`
- `test_list_supported_lipids_returns_8_species`
- `test_list_supported_lipids_all_have_required_keys` (name, full_name, charge)
- `test_build_membrane_graceful_when_unavailable` (monkeypatch)
- `test_lipid_ratio_validation_raises_on_invalid_sum`

### `tests/test_ligand_params.py`
- `test_is_acpype_available_returns_bool`
- `test_run_acpype_graceful_when_unavailable` (monkeypatch)
- `test_assemble_complex_merges_gro_coordinate_blocks`
- `test_assemble_complex_includes_itp_in_topol`
- `test_assemble_complex_updates_molecules_section`

### `tests/test_membrane_api.py`
- `TestStatusEndpoint`: GET /api/membrane/status → 200, has `available` key
- `TestLipidsEndpoint`: GET /api/membrane/lipids → 200, list of 8
- `TestBuildEndpoint`: POST with missing lipids → 422; POST with mock → 200

### `tests/test_ligand_api.py`
- `TestStatusEndpoint`: GET /api/ligand/status → 200, has `available` key
- `TestParameterizeEndpoint`: POST valid ligand → 200, penalty field present
- `TestAssembleEndpoint`: POST valid files → 200, complex_gro field present

---

## 7. system_config.py v1.2 Changes

### `validate_solution_config()` additions
- `config["membrane"]["lipids_upper"]`: each entry `{"name": str, "fraction": float}`, fraction 0.0–1.0, sum of fractions == 1.0 (±0.001 tolerance)
- `config["membrane"]["lipids_lower"]`: same validation rules
- `config["membrane"]["water_z_nm"]`: 0.5–5.0
- `config["membrane"]["salt_M"]`: 0.0–2.0
- `config["ligand"]["net_charge"]`: integer −10 to +10
- `config["ligand"]["residue_name"]`: 1–3 alphanumeric chars

### `build_constraint_prompt()` additions
- Membrane block: emitted when `config["build_type"] == "membrane"`
- Ligand block: emitted when `config["build_type"] == "ligand"`

---

## 8. Implementation Order

1. `lib/membrane_builder.py` + `tests/test_membrane_builder.py`
2. Membrane API endpoints + `tests/test_membrane_api.py`
3. Membrane Builder UI page
4. `lib/ligand_params.py` + `tests/test_ligand_params.py`
5. Ligand API endpoints + `tests/test_ligand_api.py`
6. Ligand Builder UI page
7. `lib/system_config.py` v1.2 (membrane + ligand validation + prompt)
8. Launch screen cards (Membrane Builder, Protein-Ligand)
