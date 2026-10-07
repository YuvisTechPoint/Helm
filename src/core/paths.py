"""Canonical repository paths — never depend on process CWD."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
DATA_DIR = REPO_ROOT / "data"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
DASHBOARD_DIR = REPO_ROOT / "apps" / "dashboard"
