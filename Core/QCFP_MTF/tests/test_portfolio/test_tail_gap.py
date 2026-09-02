# coding: utf-8
"""Tail-Risk / Gap-Risk Engine 测试（78 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.tail_gap import tail_adjusted_position, tail_gap_risk


def test_gap_risk_increases_tail():
    normal = tail_gap_risk(0.03)
    with_gap = tail_gap_risk(0.03, gap_p99=0.15)
    assert with_gap.tail_risk > normal.tail_risk
    assert with_gap.gap_risk == 0.15
    assert any("GAP_RISK" in r for r in with_gap.reasons)


def test_trading_halt_premium():
    halt = tail_gap_risk(0.03, trading_halt=True)
    assert any("TRADING_HALT" in r for r in halt.reasons)
    assert halt.tail_risk > tail_gap_risk(0.03).tail_risk


def test_tail_adjusted_position():
    r = tail_adjusted_position(0.10, 0.03, gap_p99=0.15,
                               liquidity_collapse_pct=0.05)
    assert r["adjusted_target"] < r["original_target"]
    assert r["tail_position_scale"] < 1.0
