# coding: utf-8
"""Opportunity Replacement 测试（23 号：换仓需覆盖切换成本）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.replacement.replacement_engine import (capital_rotation,
                                                     should_replace,
                                                     switching_cost)


def _row(code, perm="ALLOW", setup="BREAKOUT", tqs=70, wave=0.8,
         stage="ACTIVE"):
    return {"stock_code": code, "institutional_permission": perm,
            "setup_type": setup, "trade_quality": tqs, "risk_level": "Low",
            "wave_strength": wave, "mfe_potential": 0.2, "mae_risk": 0.06,
            "permission_stable": True, "wave_stage": stage}


def test_replace_requires_edge_over_cost():
    cand = _row("NEW", setup="BREAKOUT", wave=0.9)
    exist = _row("OLD", setup="BREAKOUT", wave=0.8, stage="MATURE")
    r = should_replace(cand, exist, position=0.3)
    assert r["edge"] > 0
    assert r["replace"] is True
    # 高成本下小优势不换
    r2 = should_replace(cand, exist, position=1.0)
    if r2["edge"] <= 0:
        assert r2["replace"] is False


def test_replace_stage_adjust():
    cand = _row("NEW", wave=0.7, stage="DISCOVERY")
    exist = _row("OLD", wave=0.8, stage="ACTIVE")
    r = should_replace(cand, exist)
    assert r["candidate_stage"] == "DISCOVERY"
    assert r["existing_stage"] == "ACTIVE"
    # 旧仓 MATURE 衰减 → 换仓更容易
    exist_mature = _row("OLD", wave=0.8, stage="MATURE")
    r2 = should_replace(cand, exist_mature)
    assert r2["existing_utility"] < r["existing_utility"]


def test_switching_cost_positive():
    assert switching_cost(position=0.3) > 0


def test_capital_rotation_65():
    # B 增量收益折算后超过 A 剩余收益 + 成本 → 换仓
    r = capital_rotation(existing_remaining_return=0.02,
                         existing_holding_days=20,
                         candidate_expected_return=0.12,
                         candidate_holding_days=15,
                         transaction_cost=0.01, risk_penalty=0.005)
    assert r["rotate"] is True
    # A 剩余收益高 + 成本高 → 不换
    r2 = capital_rotation(existing_remaining_return=0.10,
                          existing_holding_days=10,
                          candidate_expected_return=0.05,
                          candidate_holding_days=20,
                          transaction_cost=0.02, risk_penalty=0.01)
    assert r2["rotate"] is False
