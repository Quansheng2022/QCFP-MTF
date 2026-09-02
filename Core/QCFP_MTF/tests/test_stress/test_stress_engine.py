# coding: utf-8
"""Stress Scenario Engine 测试（26 号：极端行情生存能力）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.stress.engine import (full_stress_report,
                                    liquidity_stress_scenarios,
                                    market_shock, mdd, recovery_days,
                                    risk_budget_breach, stress_scenarios,
                                    tail_loss)


def _returns():
    return [0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03, 0.02,
            0.01, 0.00, -0.01, 0.02]


def test_market_shock():
    r = market_shock(_returns(), shock=-0.15)
    assert r[0] == -0.15


def test_stress_scenarios_include_all():
    rows = stress_scenarios(_returns())
    names = [r["name"] for r in rows]
    for n in ("market_20%", "vol_x3.0", "correlation_0.9"):
        assert n in names


def test_liquidity_stress_scenarios():
    rows = liquidity_stress_scenarios(_returns())
    assert len(rows) == 4
    assert rows[0]["name"].startswith("liq_adv")
    assert rows[-1]["cost_scale"] >= 4.0


def test_tail_loss_and_budget():
    assert tail_loss(_returns(), q=0.05) <= -0.02
    rb = risk_budget_breach(_returns(), budget=0.02)
    assert "breach" in rb


def test_full_stress_report():
    rep = full_stress_report(_returns())
    assert "scenarios" in rep
    assert "tail_loss" in rep
    assert "risk_budget" in rep
    assert "forced_exit_count" in rep
    assert "liquidity_risk_count" in rep
    assert rep["survivable"] is True
