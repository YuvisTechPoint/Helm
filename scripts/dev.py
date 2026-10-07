"""Start API and dashboard together for local development."""

import subprocess
import sys
import time
from pathlib import Path

from scripts._bootstrap import REPO_ROOT, ensure_sqlite_dev, install

DASHBOARD = REPO_ROOT / "apps" / "dashboard"


def main() -> None:
    install()
    ensure_sqlite_dev()

    api = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "run_api.py")],
        cwd=REPO_ROOT,
    )
    print("API starting on http://127.0.0.1:8000")

    if not (DASHBOARD / "package.json").exists():
        print(f"Dashboard not found at {DASHBOARD}")
        api.wait()
        return

    dash = subprocess.Popen(
        ["npm", "run", "dev", "--", "--hostname", "127.0.0.1"],
        cwd=DASHBOARD,
        shell=sys.platform == "win32",
    )
    print("Dashboard starting on http://127.0.0.1:3000")

    try:
        while True:
            if api.poll() is not None:
                raise SystemExit(api.returncode or 1)
            if dash.poll() is not None:
                raise SystemExit(dash.returncode or 1)
            time.sleep(1)
    except KeyboardInterrupt:
        api.terminate()
        dash.terminate()


if __name__ == "__main__":
    main()
