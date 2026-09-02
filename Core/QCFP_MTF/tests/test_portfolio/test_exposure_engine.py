# coding: utf-8
"""Correlation & Exposure Engine 测试（33 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.exposure_engine import (beta_exposure,
                                                correlation_clusters,
                                                effective_number_of_bets,
                                                effective_risk_exposure,
                                                exposure_report,
                                                group_exposure)


def _pos(code, sector, weight, beta=1.0, theme="t", factor_macro="m"):
    return {"stock_code": code, "sector": sector, "weight": weight,
            "beta": beta, "theme": theme, "factor_macro": factor_macro}


def test_effective_number_of_bets():
    assert effective_number_of_bets([0.5, 0.5]) == 2.0
    assert effective_number_of_bets([1.0]) == 1.0
    assert effective_number_of_bets([0.8, 0.1, 0.1]) > 1.5


def test_group_exposure():
    pos = [_pos("A", "Bank", 0.3), _pos("B", "Tech", 0.7)]
    g = group_exposure(pos, "sector")
    assert g["Tech"] == 0.7
    assert g["Bank"] == 0.3


def test_beta_exposure():
    pos = [_pos("A", "Bank", 0.5, beta=1.5), _pos("B", "Tech", 0.5, beta=0.5)]
    b = beta_exposure(pos)
    assert b["weighted_beta"] == 1.0


def test_correlation_clusters():
    corr = {"A": {"B": 0.9, "C": 0.2}, "B": {"A": 0.9, "C": 0.1},
            "C": {"A": 0.2, "B": 0.1}}
    clusters = correlation_clusters(corr, threshold=0.7)
    assert clusters[0] == ["A", "B"]


def test_exposure_report_flags_concentration():
    pos = [_pos("A", "Bank", 0.6), _pos("B", "Bank", 0.4)]
    rep = exposure_report(pos)
    assert rep["effective_number_of_bets"] < 2.0
    assert any("INDUSTRY_CONCENTRATED" in f for f in rep["flags"])


def test_effective_risk_exposure():
    pos = [_pos("A", "Tech", 0.04, theme="Tech"),
           _pos("B", "Tech", 0.04, theme="Tech"),
           _pos("C", "Bank", 0.04, theme="Bank")]
    corr = {"A": {"B": 0.9, "C": 0.2}, "B": {"A": 0.9, "C": 0.2},
            "C": {"A": 0.2, "B": 0.2}}
    e = effective_risk_exposure(pos, corr_matrix=corr)
    assert e["nominal_exposure"] == 0.12
    assert e["effective_risk_exposure"] < 0.12     # 相关性调整后下降
    assert e["reduction_pct"] > 0
    assert e["theme_equivalent_exposure"]["Tech"] == 0.6667
