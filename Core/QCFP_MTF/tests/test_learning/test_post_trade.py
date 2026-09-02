# coding: utf-8
"""Post-trade Attribution / Closed-loop Learning 测试（60 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.learning.controlled_loop import ResearchSandbox
from QCFP_MTF.learning.post_trade import closed_loop_feedback, \
    post_trade_attribution


def _trade():
    return {"trade_id": "T1", "net_return": 0.12, "mfe": 0.20,
            "mfe_capture": 0.6, "entry_timing": "OPTIMAL",
            "exit_timing": "normal", "wave_hit": 1.0, "risk_saved": 0.02,
            "portfolio_right": 0.5, "execution_cost": 0.008}


def test_post_trade_attribution():
    a = post_trade_attribution(_trade())
    assert a.outcome == 0.12
    assert "wave" in a.modules and "entry" in a.modules
    assert a.modules["execution"] <= 0
    assert a.modules["wave"] > 0


def test_closed_loop_no_auto_promote():
    sb = ResearchSandbox()
    r = closed_loop_feedback(_trade(), sb, hypothesis="Wave 有效")
    assert r["hypothesis_created"] is True
    assert r["auto_promoted"] is False       # 候选不能自动晋升生产
    assert len(sb.read_evidence()) == 1
    assert len(sb.candidates) == 1


def test_closed_loop_outcome_only():
    sb = ResearchSandbox()
    r = closed_loop_feedback(_trade(), sb)
    assert r["hypothesis_created"] is False
    assert len(sb.read_evidence()) == 1
