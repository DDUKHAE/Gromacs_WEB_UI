"""CLI wrapper — runs one skill against a workspace.

Usage:
    python web/runner.py --skill env --workspace runs/aki_20260608_120000 --pdb inputs/input.pdb
    python web/runner.py --skill md  --workspace runs/aki_20260608_120000
    python web/runner.py --skill viz --workspace runs/aki_20260608_120000
    python web/runner.py --skill all --workspace runs/aki_20260608_120000 --pdb inputs/input.pdb
"""
import argparse
import json
import sys
from pathlib import Path

_HARNESS = Path(__file__).parent.parent
sys.path.insert(0, str(_HARNESS))


def _run_env(workspace: Path, pdb: Path) -> dict:
    from skills.env_builder.env_builder import build_environment
    return build_environment(pdb_path=pdb, prompt="", workspace_dir=workspace, interactive=False)


def _run_md(workspace: Path) -> dict:
    from skills.md_runner.md_runner import run_simulation
    return run_simulation(workspace_dir=workspace, interactive=False)


def _run_viz(workspace: Path) -> dict:
    from skills.illustrator.illustrator import run_core_analyses
    from lib import state
    result = run_core_analyses(workspace_dir=workspace)
    s = state.read(workspace)
    s["last_completed_stage"] = "viz"
    state.write(workspace, s)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a GROMACS skill or full pipeline")
    parser.add_argument("--skill", choices=["env", "md", "viz", "all"], required=True)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--pdb", type=Path, help="PDB path (env and all only)")
    args = parser.parse_args()

    ws = args.workspace.resolve()
    (ws / "runner.skill").write_text(args.skill)
    exit_file = ws / "runner.exit"

    try:
        if args.skill == "env":
            if not args.pdb:
                print("ERROR: --pdb required for env skill", flush=True)
                exit_file.write_text("1")
                return 1
            result = _run_env(ws, args.pdb.resolve())
        elif args.skill == "md":
            result = _run_md(ws)
        elif args.skill == "viz":
            result = _run_viz(ws)
        else:  # "all"
            if not args.pdb:
                print("ERROR: --pdb required for all skill", flush=True)
                exit_file.write_text("1")
                return 1
            result = _run_env(ws, args.pdb.resolve())
            result = _run_md(ws)
            result = _run_viz(ws)

        print(json.dumps(result, indent=2, default=str), flush=True)
        exit_file.write_text("0")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        exit_file.write_text("1")
        return 1


if __name__ == "__main__":
    sys.exit(main())
