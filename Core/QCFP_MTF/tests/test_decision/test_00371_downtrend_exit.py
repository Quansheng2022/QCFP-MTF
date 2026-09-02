# coding: utf-8
"""00371 北控水务金标准回归（V18 下行风险层）

目标：不是"事后预测 00371"，而是防止系统再次出现：
    1) 周线 Breakdown 时仍输出 HOLD；
    2) 连续破位时仓位不下降；
    3) 下跌越深、风险评分反而越低（8/21 的 risk=Low / target=0.75 漏洞）。
"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.action_generator import generate_action
from QCFP_MTF.decision.downside_risk import apply_downside_risk
from QCFP_MTF.fusion.mtf_alignment import align_mtf


def _declining_weekly(n=30):
    dates = pd.date_range("2026-02-01", periods=n, freq="W-FRI")
    return pd.DataFrame({
        "stock_code": ["00371"] * n,
        "date": dates,
        "close": [3.0 - 0.03 * i for i in range(n)],
    })


def test_alignment_breakdown_now_warns():
    # P0-A：BULLISH + Stable + Breakdown → BULLISH_WARNING（此前兜底为 BULLISH_STABLE/HOLD）
    mtf, method = align_mtf("STRUCTURAL_BULLISH", "Stable", "Breakdown")
    assert mtf == "BULLISH_WARNING"
    action = generate_action(mtf, "STRUCTURAL_BULLISH", "High", DEFAULT_SETTINGS)
    assert action == "REDUCE"


def test_00371_first_breakdown_derisk():
    # 6/19、6/26：周线 Breakdown + close<MA20 → action != HOLD，target <= 0.5
    signals = pd.DataFrame({
        "stock_code": ["00371", "00371"],
        "decision_date": ["2026-06-19", "2026-06-26"],
        "tactical_signal": ["Breakdown", "Breakdown"],
        "catalyst_score": [0.0, 0.0],
        "action_signal": ["REDUCE", "REDUCE"],
        "risk_level": ["High", "High"],
        "target": [0.5, 0.5],
    })
    out = apply_downside_risk(signals, _declining_weekly(), DEFAULT_SETTINGS)
    r = out.iloc[-1]
    assert r["action_signal"] != "HOLD"
    assert r["target"] <= 0.5
    assert r["risk_level"] == "Extreme"
    # 连续两周 Breakdown → target <= 0.25（风险下限 Extreme 上限 0.2）
    assert r["target"] <= 0.25
    assert r["des_score"] >= 5


def test_00371_late_downtrend_risk_not_relaxed():
    # 8/21 情形：持续下跌中 dq 改善/市场中性/无背离 → 风险不得降回 Low，仓位不得上升
    rows = [
        ["2026-06-19", "Breakdown", "High", 0.5],
        ["2026-06-26", "Breakdown", "High", 0.5],
        ["2026-07-31", "Consolidation", "Medium", 0.75],
        ["2026-08-21", "Breakdown", "Low", 0.75],   # 旧系统此处 risk=Low/target=0.75
    ]
    signals = pd.DataFrame({
        "stock_code": ["00371"] * 4,
        "decision_date": [r[0] for r in rows],
        "tactical_signal": [r[1] for r in rows],
        "catalyst_score": [0.0, 0.0, -1.0, 1.0],
        "action_signal": ["REDUCE", "REDUCE", "HOLD", "HOLD"],
        "risk_level": [r[2] for r in rows],
        "target": [r[3] for r in rows],
    })
    out = apply_downside_risk(signals, _declining_weekly(), DEFAULT_SETTINGS)
    r = out.iloc[-1]
    assert r["risk_level"] != "Low"
    assert r["risk_level"] == "Extreme"        # 风险下限保持
    assert r["target"] <= out.iloc[-2]["target"]  # 仓位单调性：不得上升
    assert r["target"] <= 0.25
    assert r["action_signal"] != "HOLD"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_00371_downtrend_exit 全部通过 ✅")
