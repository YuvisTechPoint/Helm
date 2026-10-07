"""Start API (and optionally owner-web). Kills stale listeners on :8000 first."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

for rel in ("packages/core", "apps/youtube", "apps/acquisition", "apps/api"):
    sys.path.insert(0, str(ROOT / rel))

os.environ.setdefault("USE_SQLITE", "true")
(ROOT / "data").mkdir(exist_ok=True)
os.environ.setdefault("SQLITE_URL", f"sqlite:///{(ROOT / 'data' / 'engine.db').as_posix()}")


def _kill_port(port: int) -> None:
    if sys.platform == "win32":
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False)
        for line in out.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                if pid.isdigit():
                    subprocess.run(["taskkill", "/PID", pid, "/F"], check=False)


if __name__ == "__main__":
    _kill_port(8000)
    import uvicorn

    uvicorn.run("api.main:create_app", factory=True, host="127.0.0.1", port=8000, reload=False)
