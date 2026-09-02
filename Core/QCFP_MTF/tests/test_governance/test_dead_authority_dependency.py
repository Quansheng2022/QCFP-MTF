# coding: utf-8
"""Dead Authority Dependency Graph 测试（新 40 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.dead_authority import \
    dead_authority_dependency_check


def test_removed_from_graph():
    r = dead_authority_dependency_check(
        "LegacyScore", ["governance", "engine", "ledger"])
    assert r["verdict"] == "REMOVED_FROM_GRAPH"
    assert r["removed"] is True


def test_still_in_graph():
    r = dead_authority_dependency_check(
        "LegacyScore", ["governance", "legacy.score", "ledger"])
    assert r["verdict"] == "STILL_IN_GRAPH"
    assert r["removed"] is False
    assert "legacy.score" in r["still_in_graph"]
