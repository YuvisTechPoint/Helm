"""Start API, optional worker, and dashboard together for local development."""

import os
import subprocess
import sys
import time
from pathlib import Path

from scripts._bootstrap import REPO_ROOT, ensure_sqlite_dev, install

DASHBOARD = REPO_ROOT / "apps" / "dashboard"


def main() -> None:
    install()
    ensure_sqlite_dev()

    procs: list[subprocess.Popen] = []

    api = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "run_api.py")],
        cwd=REPO_ROOT,
    )
    procs.append(api)
    print("API starting on http://127.0.0.1:8000")

    if os.environ.get("START_WORKER", "1").lower() not in {"0", "false", "no"}:
        worker = subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "run_worker.py")],
            cwd=REPO_ROOT,
        )
        procs.append(worker)
        print("Worker starting (Temporal task queue: youtube-engine)")

    if not (DASHBOARD / "package.json").exists():
        print(f"Dashboard not found at {DASHBOARD}")
        api.wait()
        return

    dash = subprocess.Popen(
        ["npm", "run", "dev", "--", "--hostname", "127.0.0.1"],
        cwd=DASHBOARD,
        shell=sys.platform == "win32",
    )
    procs.append(dash)
    print("Dashboard starting on http://127.0.0.1:3000")
    print("Set START_WORKER=0 to skip the Temporal worker")

    try:
        while True:
            for proc in procs:
                if proc.poll() is not None:
                    raise SystemExit(proc.returncode or 1)
            time.sleep(1)
    except KeyboardInterrupt:
        for proc in procs:
            proc.terminate()


if __name__ == "__main__":
    main()
