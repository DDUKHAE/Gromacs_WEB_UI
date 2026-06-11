from __future__ import annotations
import json
from pathlib import Path

VALID_BOX_TYPES = {"cubic", "dodecahedron", "octahedron"}
VALID_THERMOSTATS = {"V-rescale", "Nosé-Hoover"}
VALID_BAROSTATS = {"Parrinello-Rahman", "Berendsen"}


def validate_solution_config(config: dict) -> list[str]:
    """Validate a solution builder config dict. Returns list of error strings."""
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

    return errors


def build_constraint_prompt(config: dict) -> str:
    """Build LLM constraint block string from a system_config dict."""
    ff = config.get("forcefield", {})
    box = config.get("box", {})
    ions = config.get("ions", {})
    sim = config.get("simulation", {})

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
    if sim.get("_expert_mode"):
        lines.append(f"- Temperature: {sim.get('temperature_K', 300)} K")
        lines.append(f"- Pressure: {sim.get('pressure_bar', 1.0)} bar")
        lines.append(f"- Simulation time: {sim.get('sim_time_ns', 1.0)} ns")
        if sim.get("thermostat"):
            lines.append(f"- Thermostat: {sim['thermostat']}")
        if sim.get("barostat"):
            lines.append(f"- Barostat: {sim['barostat']}")
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
