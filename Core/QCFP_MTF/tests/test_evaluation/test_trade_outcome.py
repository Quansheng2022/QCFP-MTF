# coding: utf-8
"""Trade Outcome Attribution 测试（26 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.trade_outcome import trade_outcome_attribution


def test_trade_outcome():
    r = trade_outcome_attribution({
        "raw_opportunity": 0.18, "entry_delay_cost": 0.022,
        "early_exit_cost": 0.035, "slippage_cost": 0.008,
        "position_cap_cost": 0.014, "permission_cost": 0.0})
    assert r["raw_opportunity"] == 0.18
    assert r["early_exit"] == -0.035
    assert abs(r["realized_contribution"] - 0.101) < 1e-4
    assert r["biggest_leak"] == "early_exit"
