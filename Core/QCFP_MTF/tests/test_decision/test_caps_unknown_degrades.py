# coding: utf-8
"""Production Caps 缺失 → UNKNOWN/degrade 测试（Convergence 新 5 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.governance_caps import caps_governance_check


def test_production_missing_required_no_new_risk():
    r = caps_governance_check({"portfolio_cap": 0.2},
                              mode="production")
    assert r["unknown"] is True
    assert r["degrade"] == "NO_NEW_RISK"
    assert r["certifiable"] is False
    assert "liquidity_cap" in r["missing_required"]


def test_production_all_caps_normal():
    r = caps_governance_check({"portfolio_cap": 0.2, "liquidity_cap": 0.3,
                               "execution_cap": 0.4},
                              mode="production")
    assert r["unknown"] is False
    assert r["certifiable"] is True


def test_exploration_assumed_non_certifiable():
    r = caps_governance_check({}, mode="research_exploration")
    assert r["degrade"] == "ASSUMED"
    assert r["certifiable"] is False
