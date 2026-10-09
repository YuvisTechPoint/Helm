"""Run both engines end-to-end — pipeline + HTTP surface validation."""

import json
import sys

from scripts._bootstrap import ensure_sqlite_dev, install


def main() -> int:
    install()
    ensure_sqlite_dev()

    from core.e2e_harness import run_full_e2e
    from fastapi.testclient import TestClient

    from api.main import create_app

    client = TestClient(create_app())
    report = run_full_e2e(client)

    # Print pipeline payload when present for operator visibility
    for step in report.steps:
        if step.name == "pipeline" and step.payload:
            print(json.dumps(step.payload, indent=2, default=str))
            break

    summary = report.to_dict()
    print(json.dumps(summary, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
