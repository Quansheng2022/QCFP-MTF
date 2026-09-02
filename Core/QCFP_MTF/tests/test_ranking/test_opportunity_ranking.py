# coding: utf-8
"""Opportunity Ranking 测试（22 号：横截面排序 + BLOCK 不越权）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ranking.opportunity_ranking import (opportunity_score,
                                                  risk_adjusted_opportunity_score,
                                                  rank_opportunities,
                                                  select_top_n)


def _row(code, perm="ALLOW", setup="BREAKOUT", tqs=60, wave=0.8, mfe=0.2,
          mae=0.06, holding=4, cap_eff=0.0):
    return {"stock_code": code, "institutional_permission": perm,
            "setup_type": setup, "trade_quality": tqs, "risk_level": "Low",
            "wave_strength": wave, "mfe_potential": mfe, "mae_risk": mae,
            "permission_stable": True, "expected_holding_weeks": holding,
            "capital_efficiency": cap_eff}


def test_ranking_orders_by_score():
    rows = [_row("A", perm="STRONG_ALLOW", wave=0.9),
            _row("B", perm="ALLOW", wave=0.7)]
    ranked = rank_opportunities(rows)
    assert ranked[0]["stock_code"] == "A"
    assert ranked[0]["score"] > ranked[1]["score"]


def test_block_never_tradable_even_rank1():
    rows = [_row("BLK", perm="BLOCK", wave=1.0),
            _row("OK", perm="ALLOW", setup="NONE", tqs=0, wave=0.0,
                 mfe=0.0, mae=0.2)]
    ranked = rank_opportunities(rows)
    assert ranked[0]["stock_code"] == "BLK"     # 分数最高
    assert ranked[0]["tradable"] is False        # 但不能交易
    top = select_top_n(ranked, n=1)
    assert top[0]["stock_code"] == "OK"


def test_ranking_dimensions_holding_and_capital():
    a = _row("A", holding=12, cap_eff=0.0)
    b = _row("B", holding=4, cap_eff=3.0)
    assert opportunity_score(b) > opportunity_score(a)


def test_risk_adjusted_opportunity_score_52():
    good = {"expected_mfe": 0.25, "expected_mae": 0.05,
            "realized_mfe_ratio": 0.2, "entry_timing": "OPTIMAL",
            "expected_holding_weeks": 4, "execution_cost": 0.003}
    late = {"expected_mfe": 0.25, "expected_mae": 0.05,
            "realized_mfe_ratio": 0.9, "entry_timing": "LATE",
            "expected_holding_weeks": 8, "execution_cost": 0.01}
    assert risk_adjusted_opportunity_score(good) > \
        risk_adjusted_opportunity_score(late)
    # 低概率 → 评分下降
    assert risk_adjusted_opportunity_score(good, probability=0.3) < \
        risk_adjusted_opportunity_score(good, probability=1.0)
