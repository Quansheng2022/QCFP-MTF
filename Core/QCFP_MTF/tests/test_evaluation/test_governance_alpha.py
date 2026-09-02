# coding: utf-8
"""Governance Alpha / Loss Avoidance 测试（P1-8 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.governance_alpha import avoided_loss, \
    governance_alpha


def test_governance_alpha():
    g = {"return": 0.10, "mdd": -0.08, "turnover": 1.0,
         "capital_efficiency": 0.5}
    u = {"return": 0.12, "mdd": -0.20, "turnover": 2.5,
         "capital_efficiency": 0.3}
    r = governance_alpha(g, u)
    assert r["governance_alpha"] == -0.02       # 治理略降收益
    assert r["drawdown_reduction"] == 0.12      # 但回撤大幅下降
    assert r["turnover_reduction"] == 1.5


def test_avoided_loss():
    blocked = [{"net_return": -0.15}, {"net_return": -0.08},
               {"net_return": 0.10}]
    r = avoided_loss(blocked)
    assert r["blocked_count"] == 3
    assert r["would_lose"] == 2
    assert r["avoided_loss"] == 0.23
    assert r["foregone_gain"] == 0.10
