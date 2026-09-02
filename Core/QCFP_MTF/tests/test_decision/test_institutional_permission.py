# coding: utf-8
"""Institutional Permission Engine 正式接口测试（QCFP-MTF 2.2）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.institutional_permission import evaluate_institutional_permission


def _perm(state, pressure, persistence, **kw):
    return evaluate_institutional_permission(
        institutional_state_name=state, pressure=pressure,
        persistence=persistence, settings=DEFAULT_SETTINGS, **kw).permission


def test_permission_matrix():
    assert _perm("ACCUMULATION", 1, 2) == "ALLOW"
    assert _perm("ACCUMULATION", 2, 2) == "STRONG_ALLOW"
    assert _perm("NEUTRAL", 0, 0) == "WATCH"
    assert _perm("RECOVERY", 1, 1) == "TEST"
    assert _perm("DISTRIBUTION", -1, 2) == "BLOCK"
    assert _perm("DISTRIBUTION_STRONG", -2, 2) == "BLOCK"
    assert _perm("CAPITULATION", -2, 1) == "BLOCK"
    assert _perm("UNKNOWN", 0, 0) == "WATCH"


def test_downgrade_rules():
    assert _perm("ACCUMULATION", 2, 2, divergence=True) == "WATCH"
    assert _perm("ACCUMULATION", 2, 2, confidence="Low") == "WATCH"
    assert _perm("ACCUMULATION", 2, 2, data_quality="D") == "BLOCK"
    assert _perm("ACCUMULATION", 2, 2, market_risk=True) == "TEST"
    # 降级不升级：BLOCK 保持 BLOCK
    assert _perm("CAPITULATION", -2, 1, divergence=False, confidence="High") == "BLOCK"


def test_block_cannot_be_upgraded_by_daily_breakout():
    # 权限是交易上限：BLOCK + DAILY_BREAKOUT → 仍 BLOCK
    from QCFP_MTF.decision.retail_position_fsm import RetailDecisionContext, next_state
    ctx = RetailDecisionContext(
        institutional_permission="BLOCK", daily_state="DAILY_BREAKOUT",
        risk_level="Medium", des_score=1)
    assert next_state("FLAT", ctx) == "FLAT"   # 不进入 TESTING


def test_allow_but_no_setup_stays_flat():
    # 有交易资格 ≠ 当前存在交易机会
    from QCFP_MTF.decision.retail_position_fsm import RetailDecisionContext, next_state
    ctx = RetailDecisionContext(
        institutional_permission="ALLOW", daily_state="DAILY_NEUTRAL",
        risk_level="Medium", des_score=0)
    assert next_state("FLAT", ctx) == "FLAT"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_institutional_permission 全部通过 ✅")
