"""Start the YouTube Channel Engine HTTP API."""

import subprocess
import sys

from scripts._bootstrap import ensure_sqlite_dev, install


def kill_port(port: int) -> None:
    if sys.platform == "win32":
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False)
        for line in out.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                if pid.isdigit():
                    subprocess.run(["taskkill", "/PID", pid, "/F"], check=False)


def main() -> None:
    install()
    ensure_sqlite_dev()
    kill_port(8000)
    import uvicorn

    uvicorn.run("api.main:create_app", factory=True, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
