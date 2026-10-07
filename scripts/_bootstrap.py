"""Shared runtime bootstrap for CLI entrypoints."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


def install() -> Path:
    """Put src/ on sys.path and chdir to repo root."""
    src = str(SRC_ROOT)
    if src not in sys.path:
        sys.path.insert(0, src)
    os.chdir(REPO_ROOT)
    return REPO_ROOT


def ensure_sqlite_dev() -> None:
    import sys

    sys.path.insert(0, str(SRC_ROOT))
    from core.paths import ARTIFACTS_DIR, DATA_DIR

    os.environ.setdefault("USE_SQLITE", "true")
    DATA_DIR.mkdir(exist_ok=True)
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    os.environ.setdefault("SQLITE_URL", f"sqlite:///{(DATA_DIR / 'engine.db').as_posix()}")
