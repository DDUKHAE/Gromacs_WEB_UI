import json
import os
import sys
from datetime import datetime, timezone


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_state():
    return {
        "current_step": 0,
        "latest_gro": None,
        "top_file": None,
        "topol_molecules": {},
        "hardware_specs": {},
        "retry_history": {},
        "topology_backup": None,
        "last_command_fingerprint": None,
        "last_updated": utc_now_iso(),
        "warning_flag": False,
    }


def validate_state_schema(state):
    required_keys = {
        "current_step": int,
        "retry_history": dict,
        "last_updated": str,
    }
    for key, expected_type in required_keys.items():
        if key not in state:
            return False, f"Missing required key: {key}"
        if not isinstance(state[key], expected_type):
            return (
                False,
                f"Invalid type for {key}: expected {expected_type.__name__}, got {type(state[key]).__name__}",
            )
    return True, None


def load_state(state_path):
    if not os.path.exists(state_path):
        return default_state()
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    default = default_state()
    updated = False
    for k, v in default.items():
        if k not in state:
            state[k] = v
            updated = True

    if updated:
        save_state(state_path, state)
    return state


def save_state(state_path, state):
    state["last_updated"] = utc_now_iso()
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def run_state_manager(input_data):
    action = input_data.get("action", "read")
    data = input_data.get("data", {})
    cwd = input_data.get("cwd", os.getcwd())
    state_file = input_data.get("state_file", "simulation_state.json")
    state_path = os.path.join(cwd, state_file) if not os.path.isabs(state_file) else state_file

    os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)

    try:
        if action == "read":
            state = load_state(state_path)
            ok, err = validate_state_schema(state)
            if not ok:
                return {"status": "error", "message": f"Schema validation failed: {err}", "state_path": state_path}
            return {"status": "success", "state": state, "state_path": state_path}

        if action == "init":
            state = default_state()
            state.update(data or {})
            state["last_updated"] = utc_now_iso()
            ok, err = validate_state_schema(state)
            if not ok:
                return {"status": "error", "message": f"Schema validation failed: {err}", "state_path": state_path}
            save_state(state_path, state)
            return {"status": "success", "state": state, "state_path": state_path}

        if action == "update":
            state = load_state(state_path)
            state.update(data or {})
            state["last_updated"] = utc_now_iso()
            ok, err = validate_state_schema(state)
            if not ok:
                return {"status": "error", "message": f"Schema validation failed: {err}", "state_path": state_path}
            save_state(state_path, state)
            return {"status": "success", "state": state, "state_path": state_path}

        return {"status": "error", "message": f"Unsupported action: {action}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1].startswith("{"):
            payload = json.loads(sys.argv[1])
        else:
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                payload = json.load(f)
    else:
        payload = json.loads(sys.stdin.read())

    result = run_state_manager(payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))
