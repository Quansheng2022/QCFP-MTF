# coding: utf-8
"""Opportunity Funnel 测试（67 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.opportunity_funnel import funnel_verdict, \
    opportunity_funnel


def _funnel():
    return opportunity_funnel({
        "universe": 500, "pit_valid": 470, "permission_eligible": 160,
        "wave_candidate": 42, "fsm_eligible": 18,
        "risk_eligible": 12, "liquidity_eligible": 10,
        "final_trade": 6})


def test_funnel_counts_and_wave_bottleneck():
    f = _funnel()
    assert f["counts"]["universe"] == 500
    assert f["counts"]["final_trade"] == 6
    # 示例数据中 160→42 的相对降幅（73.75%）最大
    assert f["bottleneck"] == "wave_candidate"
    assert len(f["drops"]) == 7


def test_funnel_verdict_wave_for_example():
    v = funnel_verdict(_funnel())
    assert v["verdict"] == "WAVE_TOO_NARROW"


def test_funnel_verdict_permission():
    f = opportunity_funnel({
        "universe": 500, "pit_valid": 470, "permission_eligible": 100,
        "wave_candidate": 80, "fsm_eligible": 60,
        "risk_eligible": 40, "liquidity_eligible": 30,
        "final_trade": 20})
    assert f["bottleneck"] == "permission_eligible"
    assert funnel_verdict(f)["verdict"] == "PERMISSION_TOO_STRICT"


def test_funnel_no_data():
    assert funnel_verdict(opportunity_funnel({}))["verdict"] == "NO_DATA"
