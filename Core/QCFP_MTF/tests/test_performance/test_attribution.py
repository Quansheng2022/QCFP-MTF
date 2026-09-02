# coding: utf-8
"""P&L Attribution 测试（28 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.performance.attribution import (attribution_report,
                                              attribution_to_md,
                                              market_beta_contribution,
                                              portfolio_allocation_alpha,
                                              risk_avoidance_contribution,
                                              sizing_contribution,
                                              timing_contribution,
                                              wave_contribution)


def _trade(code="A", net=0.10, gross=0.11, exposure=0.3, delay=0,
           setup="BREAKOUT", regime="Bull"):
    return {"stock_code": code, "net_return": net, "gross_return": gross,
            "exposure": exposure, "entry_delay_weeks": delay,
            "exit_delay_weeks": 0, "setup_type": setup, "regime": regime}


def test_market_beta_contribution():
    p = [0.01, 0.02, -0.01, 0.03]
    b = [0.01, 0.02, -0.01, 0.03]
    assert abs(market_beta_contribution(p, b)) < 0.05


def test_timing_negative():
    trades = [_trade(delay=1, net=0.10)]
    assert timing_contribution(trades, "entry_delay_weeks") <= 0


def test_sizing_concentrates_good():
    trades = [_trade(net=0.20, exposure=0.5), _trade(net=0.02, exposure=0.05)]
    assert sizing_contribution(trades) > 0


def test_wave_contribution():
    trades = [_trade(setup="BREAKOUT", net=0.15), _trade(setup="NONE",
                                                         net=0.0)]
    assert wave_contribution(trades) > 0


def test_risk_avoidance_positive():
    blocked = [_trade(net=-0.10), _trade(net=-0.05)]
    assert risk_avoidance_contribution(blocked) > 0


def test_attribution_report_balanced():
    trades = [_trade(), _trade(net=0.05, exposure=0.2)]
    rep = attribution_report(
        portfolio_returns=[0.01, 0.02], benchmark_returns=[0.01, 0.02],
        trades=trades, blocked_trades=[],
        total_return=sum(t["net_return"] for t in trades))
    assert "decomposition" in rep and "buckets" in rep
    assert rep["n_trades"] == 2
    assert "Alpha" in rep["buckets"]


def test_attribution_to_md():
    rep = attribution_report(trades=[_trade()])
    md = attribution_to_md(rep)
    assert "P&L Attribution" in md
    assert "Alpha" in md


def test_portfolio_allocation_alpha_68():
    trades = [
        {"opportunity_score": 95, "net_return": 0.15},
        {"opportunity_score": 90, "net_return": 0.12},
        {"opportunity_score": 40, "net_return": -0.05},
        {"opportunity_score": 30, "net_return": -0.08},
    ]
    alpha = portfolio_allocation_alpha(trades)
    assert alpha > 0     # 高分机会实际收益高于低分 → 排名有价值
    assert portfolio_allocation_alpha(trades[:2]) == 0.0   # 样本不足
