# coding: utf-8
"""Physical Retirement Gate 测试（新 18 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.module_trim import physical_retirement_gate


def test_clean_retirement_reduces_paths():
    r = physical_retirement_gate(
        ["LegacyScore"],
        production_imports=[], entry_points=[], report_display=[],
        executable_paths_before=12, executable_paths_after=10)
    assert r["verdict"] == "RETIRED_CLEAN"
    assert r["paths_decreased"] is True


def test_incomplete_retirement_keeps_imports():
    r = physical_retirement_gate(
        ["LegacyScore"], production_imports=["legacy.score"],
        entry_points=[], report_display=[],
        executable_paths_before=12, executable_paths_after=11)
    assert r["verdict"] == "RETIRE_INCOMPLETE"
    assert any("PRODUCTION_IMPORT" in v for v in r["violations"])


def test_paths_must_decrease():
    r = physical_retirement_gate(
        ["X"], production_imports=[], entry_points=[], report_display=[],
        executable_paths_before=10, executable_paths_after=10)
    assert r["verdict"] == "RETIRE_INCOMPLETE"
    assert "EXECUTABLE_PATHS_NOT_DECREASED" in r["violations"]
