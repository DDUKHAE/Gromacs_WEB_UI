"""
Gromacs Harness — Web UI entry point

Usage:
    python main.py
    python main.py --port 8000
    python main.py --host 0.0.0.0 --port 8000
    python main.py --no-browser
"""
import argparse
import subprocess
import sys
import webbrowser
from pathlib import Path

HARNESS_DIR = Path(__file__).parent
REQUIRED = ["fastapi", "uvicorn", "multipart"]  # multipart = python-multipart


def check_dependencies() -> bool:
    missing = []
    for pkg in REQUIRED:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return True

    print("Missing dependencies detected. Installing...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(HARNESS_DIR)],
        capture_output=False,
    )
    if result.returncode != 0:
        print("\nAuto-install failed. Run manually:")
        print(f"  pip install -e {HARNESS_DIR}")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gromacs Harness Web UI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (development)")
    args = parser.parse_args()

    if not check_dependencies():
        sys.exit(1)

    try:
        import uvicorn
    except ImportError:
        print("uvicorn not found even after install attempt. Aborting.")
        sys.exit(1)

    # Add harness root to sys.path so web.server and skills are importable
    if str(HARNESS_DIR) not in sys.path:
        sys.path.insert(0, str(HARNESS_DIR))

    url = f"http://{args.host}:{args.port}"
    print(f"\nGromacs Harness Web UI")
    print(f"  URL : {url}")
    print(f"  Runs: {HARNESS_DIR / 'runs'}")
    print()

    if not args.no_browser:
        # Open after a brief delay so uvicorn is ready
        import threading
        def _open():
            import time
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(
        "web.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(HARNESS_DIR),
    )


if __name__ == "__main__":
    main()
