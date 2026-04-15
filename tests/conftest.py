from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _configure_test_runtime(runtime_root: Path) -> None:
    import paths

    paths.USER_DATA_DIR = runtime_root
    paths.DB_PATH = runtime_root / "bsie.db"
    paths.INPUT_DIR = runtime_root / "data" / "input"
    paths.EVIDENCE_DIR = runtime_root / "data" / "evidence"
    paths.OUTPUT_DIR = runtime_root / "data" / "output"
    paths.EXPORTS_DIR = runtime_root / "data" / "exports"
    paths.BACKUPS_DIR = runtime_root / "data" / "backups"
    paths.OVERRIDES_DIR = runtime_root / "overrides"
    paths.PROFILES_DIR = runtime_root / "mapping_profiles"

    for directory in (
        paths.INPUT_DIR,
        paths.EVIDENCE_DIR,
        paths.OUTPUT_DIR,
        paths.EXPORTS_DIR,
        paths.BACKUPS_DIR,
        paths.OVERRIDES_DIR,
        paths.PROFILES_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


TEST_RUNTIME_ROOT = Path(tempfile.mkdtemp(prefix="bsie-test-runtime-"))
os.environ["BSIE_TEST_RUNTIME_DIR"] = str(TEST_RUNTIME_ROOT)
_configure_test_runtime(TEST_RUNTIME_ROOT)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TEST_RUNTIME_ROOT, ignore_errors=True)
