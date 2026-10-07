"""Isolated in-memory SQLite for the full test suite — no shared engine.db pollution."""

import os

os.environ["USE_SQLITE"] = "true"
os.environ["SQLITE_URL"] = "sqlite://"
