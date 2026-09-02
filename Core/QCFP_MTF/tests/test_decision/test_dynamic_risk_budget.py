# coding: utf-8
"""Dynamic Risk Budget 测试（43 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.dynamic_risk_budget import dynamic_risk_budget


def test_dynamic_budget_scales_down():
    b = dynamic_risk_budget(
        base_budget=0.10, permission="ALLOW", wave_quality="STRONG",
        regime="Bull", portfolio_state="NORMAL",
        governance_hard_cap=0.10)
    assert b.dynamic_budget > 0
    assert b.final_budget == b.dynamic_budget
    assert b.capped is False


def test_dynamic_budget_never_exceeds_cap():
    b = dynamic_risk_budget(
        base_budget=0.10, permission="STRONG_ALLOW", wave_quality="STRONG",
        regime="Bull", portfolio_state="NORMAL",
        governance_hard_cap=0.05)
    assert b.final_budget == 0.05
    assert b.capped is True


def test_dynamic_budget_crisis_shrinks():
    bull = dynamic_risk_budget(
        0.10, "ALLOW", "STRONG", "Bull", "NORMAL", governance_hard_cap=0.10)
    crisis = dynamic_risk_budget(
        0.10, "ALLOW", "STRONG", "Crisis", "NORMAL",
        governance_hard_cap=0.10)
    assert crisis.final_budget < bull.final_budget


def test_block_zeros_budget():
    b = dynamic_risk_budget(
        0.10, "BLOCK", "STRONG", "Bull", "NORMAL")
    assert b.final_budget == 0.0
