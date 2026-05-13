# Molecular Dynamics Simulation Architecture: GROMACS Harness

This document is the **pipeline map** for the LLM agent (see `AGENTS.md`) to autonomously operate GROMACS.
Based on a protein-aqueous solution system, it defines the commands/inputs/outputs/state changes for each Step, and the agent uses this document as a compass to proceed through the stages.

> **Harness Integration Rule:** Upon executing each Step, you must call `GmxExecutor` from `skills/gmx-executor/SKILL.md`,
> and after the Step is completed, you must verify the results using `SystemValidator` from `skills/system-validator/SKILL.md`.

## 1. System Workflow Overview

The core objective of this architecture is to **perfectly replicate the system automation setup capabilities provided by the CHARMM-GUI web service using purely GROMACS native command-line codes**.

The complex system preparation processes performed by CHARMM-GUI (applying force fields, creating simulation boxes, solvation, adding ions, etc.) essentially match the functions provided by GROMACS built-in tools (`gmx` commands). Therefore, rather than relying on external web tools, the overview of this system is to build a pipeline of GROMACS commands to automatically generate the same outcomes (`.gro`, `.top`, `.mdp`) as CHARMM-GUI.

### Core System Setup Pipeline (GROMACS Native Automation)

The steps from inputting the PDB file to completing the simulation preparation are mapped and implemented with GROMACS commands as follows:

1. **Topology Generation (`gmx pdb2gmx`):**
   - Role: Converts the input PDB structure into a GROMACS structure file (`.gro`) and a topology file (`.top`) containing physicochemical properties, and applies the force field.
2. **Box Definition (`gmx editconf`):**
   - Role: Defines the shape of the virtual 3D space (Box) where the simulation will take place and the size of the margin around the protein.
3. **Solvation (`gmx solvate`):**
   - Role: Automatically fills the empty space within the defined simulation box with solvent (water molecules).
4. **Ionization (`gmx grompp` & `gmx genion`):**
   - Role: Replaces a proper number of water molecules with ions (e.g., Na+, Cl-) so that the overall system charge becomes 0 (Neutral).
5. **Execution Preparation:**
   - Role: Just as CHARMM-GUI generates, this prepares the simulation by providing an optimized set of `.mdp` files for energy minimization and equilibration.

This chain of GROMACS commands perfectly replaces the existing "System Builder" process of CHARMM-GUI, establishing an independent, code-controllable simulation preparation infrastructure.

---

## 2. Data Flow & Core Files

The simulation system operates with the following core files interacting organically with each other.

### 2.1 Input & System Definition Files
*   **`.pdb` (Protein Data Bank):** The initial 3D atomic coordinates file of the protein.
*   **`.top` (Topology):** Defines the physical/chemical rules of the system. It contains information about bonds, angles, charges, and the force field to use between atoms. It is updated in real-time whenever water or ions are added to the system.
*   **`.mdp` (Molecular Dynamics Parameters):** The configuration file for 'how' the simulation will be run. (e.g., temperature, pressure, step size, simulation time, etc.)
*   **`.gro` (GROMACS Coordinates):** The GROMACS standard coordinate file. A new state's `.gro` file is output at the end of every step to be used as input for the next step.

### 2.2 Execution Files
*   **`.tpr` (Portable Binary Run Input):** A **run-only binary file** that combines three files: `.gro` (structure), `.top` (rules), and `.mdp` (settings) through the `gmx grompp` command. The `gmx mdrun` engine reads only this `.tpr` file to perform calculations.

### 2.3 Output Files
When the `gmx mdrun` engine finishes calculating, the following result files are generated:
*   **`.xtc` / `.trr` (Trajectory):** Files recording the movement (trajectory) of atoms over time. (Core for visualization and analysis)
*   **`.edr` (Energy):** Records the system's energy changes (temperature, pressure, potential energy, etc.) over time.
*   **`.log` (Log):** The text log file of the simulation progress.

---

## 3. Execution Pipeline Specification (LLM-Readable)

This section defines the workflow in a structured YAML format so that the LLM agent can clearly parse and understand the execution flow of the GROMACS system. The agent must refer to the schema below to track the commands, required inputs, generated outputs, and state changes (side-effects) of each step.

```yaml
Pipeline_Steps:
  - Step: 0
    Action: "Pre-flight Hardware Check & State Init"
    Command: "gmx hardware / nvidia-smi"
    Inputs:
      - None
    Outputs:
      - State_File: "simulation_state.json"
    State_Change: "Identifies available CPU cores and GPU status of the system, and initializes the simulation state tracking file in the current working directory by calling StateManager. This information is used for subsequent mdrun optimization."

  - Step: 1
    Action: "Topology Generation"
    Command: "gmx pdb2gmx"
    Inputs:
      - Coordinate: "{target}.pdb"
    Outputs:
      - Coordinate: "{target}_processed.gro"
      - Topology: "topol.top"
    State_Change: "Applies the specified Force Field to the protein structure and generates the initial topology file."

  - Step: 2
    Action: "Box Definition"
    Command: "gmx editconf"
    Inputs:
      - Coordinate: "{target}_processed.gro"
    Outputs:
      - Coordinate: "{target}_box.gro"
    State_Change: "Records the margin around the protein (distance) and the size of the virtual simulation box (box type) into the structure file."

  - Step: 3
    Action: "Solvation"
    Command: "gmx solvate"
    Inputs:
      - Coordinate: "{target}_box.gro"
      - Topology: "topol.top"
    Outputs:
      - Coordinate: "{target}_solv.gro"
    State_Change: "Fills the inside of the box with water molecules. (Side-effect: The number of solvent molecules (SOL) is automatically added to the [ molecules ] section of the topol.top file.)"

  - Step: 4
    Action: "Ionization Preparation"
    Command: "gmx grompp"
    Inputs:
      - Coordinate: "{target}_solv.gro"
      - Topology: "topol.top"
      - Parameters: "ions.mdp"
    Outputs:
      - Run_Input: "ions.tpr"
    State_Change: "Compiles the temporary system state for adding ions into a binary file (.tpr)."

  - Step: 5
    Action: "Ionization"
    Command: "gmx genion"
    Inputs:
      - Run_Input: "ions.tpr"
      - Topology: "topol.top"
    Outputs:
      - Coordinate: "{target}_solv_ions.gro"
    State_Change: "Replaces some water molecules with ions (NA, CL, etc.) to set the Net Charge of the system to 0. (Side-effect: The number of SOL decreases and the number of ions is recorded in the topol.top file.)"

  - Step: 6
    Action: "Execution Preparation (Loop for minim, nvt, npt, md)"
    Command: "gmx grompp"
    Inputs:
      - Coordinate: "{previous_step}.gro"
      - Topology: "topol.top"
      - Parameters: "{current_phase}.mdp"
    Outputs:
      - Run_Input: "{current_phase}.tpr"
    State_Change: "Generates the final execution file by applying parameters (.mdp) for energy minimization or equilibration/main simulation."

  - Step: 7
    Action: "Simulation Execution"
    Command: "gmx mdrun"
    Inputs:
      - Run_Input: "{current_phase}.tpr"
    Outputs:
      - Coordinate: "{current_phase}.gro"
      - Trajectory: "{current_phase}.xtc", "{current_phase}.trr"
      - Energy: "{current_phase}.edr"
      - Log: "{current_phase}.log"
    State_Change: "Runs the MD engine to perform physical calculations. The generated .gro file is cycled as input for the next simulation phase (Step 6)."

  - Step: 8
    Action: "Trajectory Analysis"
    Command: "gmx energy / gmx rms / gmx rmsf / gmx gyrate"
    Inputs:
      - Trajectory: "{production_phase}.xtc"
      - Energy: "{production_phase}.edr"
      - Run_Input: "{production_phase}.tpr"
    Outputs:
      - Energy_Data: "energy.xvg"
      - RMSD_Data: "rmsd.xvg"
      - RMSF_Data: "rmsf.xvg"
      - Gyration_Data: "gyrate.xvg"
    State_Change: "Verifies system stability (RMSD), flexibility (RMSF), and energy convergence by analyzing the simulation results (.xtc, .edr). Makes a final judgment on simulation quality by comparing with the reference values in docs/simulation_criteria.md."
```

---

## 4. Harness Integration Summary

| Step | Action | Used Skill | Reference Doc |
|---|---|---|---|
| 0 | Pre-flight | `GmxExecutor` + `StateManager` | - |
| 1 | Topology Generation | `GmxExecutor` + `StateManager` | `force_field_guide.md` |
| 2 | Box Definition | `GmxExecutor` + `StateManager` | - |
| 3 | Solvation | `GmxExecutor` + `StateManager` | - |
| 4 | Ionization Prep | `GmxExecutor` + `MdpComposer` | `mdp_parameter_reference.md` |
| 5 | Ionization | `GmxExecutor` + `StateManager` | `error_troubleshooting.md` |
| 6 | Execution Prep | `GmxExecutor` + `MdpComposer` | `mdp_parameter_reference.md` |
| 7 | Simulation Run | `GmxExecutor` + `SystemValidator` + `StateManager`| `validation_criteria.md` |
| 8 | Analysis | `GmxExecutor` + `TrajectoryAnalyzer` | `xvg_analysis_guide.md` |

---

## 5. Tutorial-Guided Autonomy Layer

To support prompt-aware autonomous execution, this harness adds a tutorial-guided layer on top of Step 0-8.

### 5.1 Routing and Planning Chain

1. `TutorialRouter`:
   Selects the tutorial family from user prompt + input PDB context.
2. `TutorialPlanner`:
   Maps selected tutorial to Step 0-8 workflow.
3. `ProtocolCompiler`:
   Compiles workflow into `GmxExecutor`-ready command specs.

### 5.2 Runtime Contract

1. Step numbering remains fixed to Step 0-8 in this architecture.
2. Tutorial-specific differences are represented as `pipeline_variant` and manifest metadata.
3. Topology-mutating steps (`solvate`, `genion`) must set backup/rollback flags in compiled command specs.
4. Retry behavior must mutate command parameters or flags for each attempt (max 3).

### 5.3 Manifest-Driven Execution

Each tutorial folder can include `tutorial.manifest.json` as runtime truth:

- Example: `docs/tutorial/Lysozyme_in_water/tutorial.manifest.json`
- Required fields: `id`, `pipeline_variant`, `required_inputs`, `defaults`, `architecture_steps`, `documents`, `validation_profile`

This keeps `ARCHITECTURE.md` stable while enabling safe extension to membrane, ligand, umbrella sampling, and free-energy workflows.
