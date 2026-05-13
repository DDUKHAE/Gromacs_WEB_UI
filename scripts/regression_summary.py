#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path


CASES = ("ubq", "crn", "aki")
OUT_PATH = Path("/tmp/harness_regression_summary.json")


def _read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "missing regression output"
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {exc.msg}"
    except Exception as exc:
        return None, f"read error: {exc}"


def _summarize_case(case: str):
    in_path = Path(f"/tmp/{case}_regression.json")
    obj, read_err = _read_json(in_path)
    if read_err is not None:
        return {
            "case": case,
            "path": str(in_path),
            "status": "missing",
            "phase": None,
            "reason": read_err,
        }

    status = obj.get("status")
    phase = obj.get("phase") or (obj.get("failed_command", {}) or {}).get("phase")
    reason = (
        (obj.get("validation", {}) or {}).get("reason")
        or (obj.get("result", {}) or {}).get("summary")
        or obj.get("message")
        or ("ok" if status == "success" else "no reason provided")
    )

    return {
        "case": case,
        "path": str(in_path),
        "status": status,
        "phase": phase,
        "reason": reason,
    }


def main():
    cases = [_summarize_case(case) for case in CASES]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output": str(OUT_PATH),
        "total_cases": len(cases),
        "cases": cases,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(str(OUT_PATH))


if __name__ == "__main__":
    main()
