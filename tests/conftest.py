"""Use a throwaway SQLite file so tests never share data/engine.db with dev runs."""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from core.paths import DATA_DIR, REPO_ROOT  # noqa: E402

_TEST_DB = DATA_DIR / "test_engine.db"
_TEST_DB.parent.mkdir(exist_ok=True)
if _TEST_DB.exists():
    _TEST_DB.unlink()

os.environ["USE_SQLITE"] = "true"
os.environ["SQLITE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.chdir(REPO_ROOT)


import pytest


@pytest.fixture
def session():
    from core.bootstrap import db_session

    return db_session()
