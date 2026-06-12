from __future__ import annotations
import json
from pathlib import Path

VALID_BOX_TYPES = {"cubic", "dodecahedron", "octahedron"}
VALID_THERMOSTATS = {"V-rescale", "Nosé-Hoover"}
VALID_BAROSTATS = {"Parrinello-Rahman", "Berendsen"}
VALID_HIS_STATES = {"HSD", "HSE", "HSP"}
VALID_COULOMB_TYPES = {"PME", "Cut-off", "Ewald"}
VALID_CONSTRAINTS = {"none", "h-bonds", "all-bonds"}
VALID_CONSTRAINT_ALGORITHMS = {"LINCS", "SETTLE"}


def validate_solution_config(config: dict) -> list[str]:
    """Validate a solution builder config dict (v1.1). Returns list of error strings."""
    errors: list[str] = []

    box = config.get("box", {})
    if box.get("type") and box["type"] not in VALID_BOX_TYPES:
        errors.append(
            f"Invalid box type '{box['type']}'. Must be one of: {', '.join(sorted(VALID_BOX_TYPES))}"
        )
    if "edge_distance_nm" in box and not (0.5 <= box["edge_distance_nm"] <= 5.0):
        errors.append("edge_distance_nm must be between 0.5 and 5.0")

    ions = config.get("ions", {})
    if "concentration_M" in ions and not (0.0 <= ions["concentration_M"] <= 2.0):
        errors.append("concentration_M must be between 0.0 and 2.0")

    sim = config.get("simulation", {})
    if sim.get("thermostat") and sim["thermostat"] not in VALID_THERMOSTATS:
        errors.append(
            f"Invalid thermostat '{sim['thermostat']}'. Must be one of: {', '.join(sorted(VALID_THERMOSTATS))}"
        )
    if sim.get("barostat") and sim["barostat"] not in VALID_BAROSTATS:
        errors.append(
            f"Invalid barostat '{sim['barostat']}'. Must be one of: {', '.join(sorted(VALID_BAROSTATS))}"
        )
    if "temperature_K" in sim and not (200 <= sim["temperature_K"] <= 500):
        errors.append("temperature_K must be between 200 and 500")
    if "pressure_bar" in sim and not (0.1 <= sim["pressure_bar"] <= 10.0):
        errors.append("pressure_bar must be between 0.1 and 10.0")
    if "sim_time_ns" in sim and not (0.001 <= sim["sim_time_ns"] <= 1000):
        errors.append("sim_time_ns must be between 0.001 and 1000")

    # Extended MDP (v1.1)
    if "dt_ps" in sim and not (0.0001 <= sim["dt_ps"] <= 0.004):
        errors.append("dt_ps must be between 0.0001 and 0.004")
    if "rcoulomb_nm" in sim and not (0.8 <= sim["rcoulomb_nm"] <= 2.0):
        errors.append("rcoulomb_nm must be between 0.8 and 2.0")
    if "rvdw_nm" in sim and not (0.8 <= sim["rvdw_nm"] <= 2.0):
        errors.append("rvdw_nm must be between 0.8 and 2.0")
    if sim.get("coulombtype") and sim["coulombtype"] not in VALID_COULOMB_TYPES:
        errors.append(
            f"Invalid coulombtype '{sim['coulombtype']}'. Must be one of: {', '.join(sorted(VALID_COULOMB_TYPES))}"
        )
    if sim.get("constraints") and sim["constraints"] not in VALID_CONSTRAINTS:
        errors.append(
            f"Invalid constraints '{sim['constraints']}'. Must be one of: {', '.join(sorted(VALID_CONSTRAINTS))}"
        )
    if sim.get("constraint_algorithm") and sim["constraint_algorithm"] not in VALID_CONSTRAINT_ALGORITHMS:
        errors.append(
            f"Invalid constraint_algorithm '{sim['constraint_algorithm']}'. Must be one of: {', '.join(sorted(VALID_CONSTRAINT_ALGORITHMS))}"
        )
    if "pme_order" in sim and sim["pme_order"] not in {4, 6, 8}:
        errors.append("pme_order must be 4, 6, or 8")
    if "fourierspacing_nm" in sim and not (0.1 <= sim["fourierspacing_nm"] <= 0.3):
        errors.append("fourierspacing_nm must be between 0.1 and 0.3")
    if "lincs_order" in sim and not (2 <= sim["lincs_order"] <= 8):
        errors.append("lincs_order must be between 2 and 8")

    # Protonation (v1.1)
    prot = config.get("protonation", {})
    if "ph" in prot and not (0.0 <= prot["ph"] <= 14.0):
        errors.append("ph must be between 0.0 and 14.0")
    for residue_key, state in prot.get("his_states", {}).items():
        if state not in VALID_HIS_STATES:
            errors.append(
                f"Invalid HIS state '{state}' for {residue_key}. Must be one of: {', '.join(sorted(VALID_HIS_STATES))}"
            )

    return errors


def build_constraint_prompt(config: dict) -> str:
    """Build LLM constraint block string from a system_config dict (v1.1)."""
    ff = config.get("forcefield", {})
    box = config.get("box", {})
    ions = config.get("ions", {})
    sim = config.get("simulation", {})
    prot = config.get("protonation", {})

    lines = [
        "",
        "[SYSTEM BUILDER CONSTRAINTS — MUST FOLLOW EXACTLY]",
        "The user has pre-configured this system via the System Builder.",
        "You MUST use these parameters without modification:",
        "",
    ]

    if ff.get("name"):
        lines.append(f"- Force field: {ff['name']}")
    if ff.get("water_model"):
        lines.append(f"- Water model: {ff['water_model']}")
    if box.get("type"):
        lines.append(
            f"- Box type: {box['type']}, edge distance: {box.get('edge_distance_nm', 1.0)} nm"
        )
    if ions.get("salt_type"):
        lines.append(
            f"- Ions: {ions['salt_type']} at {ions.get('concentration_M', 0.15)} M, "
            f"neutralize={str(ions.get('neutralize', True)).lower()}"
        )

    # Protonation
    if prot.get("ph") is not None:
        lines.append(f"- pH: {prot['ph']}")
    if prot.get("his_states"):
        his_str = ", ".join(f"{k}={v}" for k, v in prot["his_states"].items())
        lines.append(f"- Histidine states: {his_str}")
    if prot.get("disulfide_bridges"):
        bridges_str = ", ".join(f"{b[0]}-{b[1]}" for b in prot["disulfide_bridges"])
        lines.append(f"- Disulfide bridges: {bridges_str}")

    if sim.get("_expert_mode"):
        lines.append(f"- Temperature: {sim.get('temperature_K', 300)} K")
        lines.append(f"- Pressure: {sim.get('pressure_bar', 1.0)} bar")
        lines.append(f"- Simulation time: {sim.get('sim_time_ns', 1.0)} ns")
        if sim.get("thermostat"):
            lines.append(f"- Thermostat: {sim['thermostat']}")
        if sim.get("barostat"):
            lines.append(f"- Barostat: {sim['barostat']}")
        if sim.get("dt_ps") is not None:
            lines.append(f"- Time step: {sim['dt_ps']} ps")
        if sim.get("rcoulomb_nm") is not None:
            lines.append(
                f"- Cutoffs: rcoulomb={sim['rcoulomb_nm']} nm, rvdw={sim.get('rvdw_nm', sim['rcoulomb_nm'])} nm"
            )
        if sim.get("coulombtype"):
            lines.append(f"- Coulomb type: {sim['coulombtype']}")
        if sim.get("pme_order"):
            lines.append(f"- PME order: {sim['pme_order']}, fourier spacing: {sim.get('fourierspacing_nm', 0.16)} nm")
        if sim.get("constraints") and sim["constraints"] != "none":
            alg = sim.get("constraint_algorithm", "LINCS")
            order = sim.get("lincs_order", 4)
            lines.append(f"- Constraints: {sim['constraints']} ({alg} order {order})")

    lines += [
        "",
        "Do NOT override these settings based on tutorial defaults.",
        "These represent the user's explicit choices.",
        "",
    ]
    return "\n".join(lines)


def load_config(workspace: Path) -> dict | None:
    """Load system_config.json from workspace. Returns None if absent."""
    path = Path(workspace) / "system_config.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())
