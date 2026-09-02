# coding: utf-8
"""DSS 输出协议测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.dss_output import build_dss_json


def _row():
    return {
        "stock_code": "00700", "decision_date": "2026-08-14",
        "model_version": "QCFP-MTF-2.5.0",
        "structural_regime": "STRUCTURAL_BULLISH", "core_score": 85.0,
        "data_quality": "B", "evidence_level": "A-",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "monthly_behavior_state": "Improving", "turnover_liquidity_regime": "T3",
        "m_vp_regime": "VP_EXPANSION", "cbi_score": 68.0,
        "cost_position": "COST_ADVANTAGE",
        "cost_vs_weekly_vwap": 0.01, "cost_vs_monthly_vwap": 0.02,
        "cost_vs_quarterly_vwap": 0.03,
        "tactical_signal": "Breakout", "w_breakout": 1, "w_breakdown": 0,
        "w_turnover_spike": 0,
        "chip_stability_confidence": "High", "structure_behavior_alignment": "Aligned",
        "evidence_summary": "结构A; 阶段B; 触发C",
        "risk_level": "Low", "key_risks": [],
        "mtf_regime": "BULLISH_CONFIRMED", "action_signal": "BUY",
        "position_advice": "80%~100%", "stop_loss_trigger": "—",
    }


def test_dss_structure():
    dss = build_dss_json(_row())
    for section in ("structural", "stage", "cost_position", "trigger",
                    "confidence", "risk", "decision"):
        assert section in dss
    assert dss["decision"]["action"] == "BUY"
    assert dss["risk"]["anti_inference_check"] == "PASSED"
    assert dss["trigger"]["breakout"] is True
    # 证据等级与数据质量独立：质量 B ≠ 证据 A
    assert dss["structural"]["evidence_level"] == "A-"


def test_dss_defaults_on_missing():
    row = _row()
    row["w_breakout"] = None
    row["cbi_score"] = None
    dss = build_dss_json(row)
    assert dss["trigger"]["breakout"] is False  # None → False
    assert dss["stage"]["cbi_score"] is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_dss_output 全部通过 ✅")
