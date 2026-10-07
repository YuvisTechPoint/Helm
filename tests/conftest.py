"""Use a throwaway SQLite file so tests never share data/engine.db with dev runs."""

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TEST_DB = _ROOT / "data" / "test_engine.db"
_TEST_DB.parent.mkdir(exist_ok=True)
if _TEST_DB.exists():
    _TEST_DB.unlink()

os.environ["USE_SQLITE"] = "true"
os.environ["SQLITE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
