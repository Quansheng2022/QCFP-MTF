# coding: utf-8
"""Dead Authority Removal 测试（40 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.dead_authority import (dead_authority_audit,
                                                executable_path_reduction)


def test_clean_retirement():
    r = dead_authority_audit(
        "legacy_sizing", retired=True,
        production_imports=[], default_config=[], entry_points=[],
        report_display=[], frozen_artifact="frozen_v1.json")
    assert r["clean_retirement"] is True
    assert r["frozen_artifact_preserved"] is True


def test_retirement_violations():
    r = dead_authority_audit(
        "legacy_sizing", retired=True,
        production_imports=["legacy_sizing"], default_config=[],
        entry_points=["run_legacy"], report_display=["legacy card"],
        frozen_artifact="frozen_v1.json")
    assert r["clean_retirement"] is False
    assert any("PRODUCTION_IMPORT" in v for v in r["violations"])
    assert any("ENTRY_POINT" in v for v in r["violations"])


def test_path_reduction():
    r = executable_path_reduction(removed_imports=["a", "b"],
                                  removed_entries=["c"],
                                  total_paths_before=10)
    assert r["paths_after"] == 7
    assert r["complexity_reduced"] is True
