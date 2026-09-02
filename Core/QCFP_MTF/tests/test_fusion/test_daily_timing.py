# coding: utf-8
"""日线时机门（Model B）单元测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import _deep_merge, DEFAULT_SETTINGS
from QCFP_MTF.fusion.daily_timing import apply_daily_timing_gate


def _signals():
    return pd.DataFrame({
        "stock_code": ["00700"] * 4,
        "decision_date": ["2024-03-08", "2024-03-15", "2024-03-22", "2024-03-29"],
        "mtf_regime": ["BULLISH_STABLE", "BEARISH_RECOVERY_CANDIDATE",
                       "BULLISH_STABLE", "BULLISH_WARNING"],
        "action_signal": ["HOLD", "WAIT", "HOLD", "REDUCE"],
        "risk_level": ["Low", "Medium", "Low", "High"],
        "is_override": [False, False, False, True],
        "target": [0.75, 0.2, 0.75, 0.2],
    })


def _daily(states):
    return pd.DataFrame({
        "stock_code": ["00700"] * 4,
        "trade_date": ["2024-03-08", "2024-03-15", "2024-03-22", "2024-03-29"],
        "daily_state": states,
    })


def test_gate_disabled_returns_unchanged():
    s = _signals()
    out = apply_daily_timing_gate(s, _daily(["DAILY_BREAKOUT"] * 4), DEFAULT_SETTINGS)
    assert (out["target"] == s["target"]).all()
    assert (out["timing_action"] == s["action_signal"]).all()


def test_gate_enabled_rules():
    settings = _deep_merge(DEFAULT_SETTINGS, {
        "daily": {"timing": {"enabled": True}}})
    s = _signals()
    d = _daily(["DAILY_BREAKOUT", "DAILY_DISTRIBUTION",
                "DAILY_PULLBACK", "DAILY_ACCUMULATION"])
    out = apply_daily_timing_gate(s, d, settings)
    # HOLD + BREAKOUT → 战术加仓（0.75×1.25=0.9375）
    assert abs(out.iloc[0]["target"] - 0.9375) < 1e-9
    assert out.iloc[0]["timing_action"] == "ADD"
    # WAIT + DISTRIBUTION（RECOVERY）→ 不减仓（非 BUY/ADD/HOLD），保持 0.2
    assert abs(out.iloc[1]["target"] - 0.2) < 1e-9
    # HOLD + PULLBACK → 持有不减
    assert abs(out.iloc[2]["target"] - 0.75) < 1e-9
    assert out.iloc[2]["timing_action"] == "HOLD"
    # 试多 + ACCUMULATION → 战术加仓（0.2×1.25=0.25）
    assert abs(out.iloc[3]["target"] - 0.25) < 1e-9


def test_early_entry_on_breakout():
    settings = _deep_merge(DEFAULT_SETTINGS, {
        "daily": {"timing": {"enabled": True}}})
    s = _signals()
    s.loc[1, "action_signal"] = "WAIT"
    s.loc[1, "target"] = 0.0
    s.loc[1, "mtf_regime"] = "BEARISH_RECOVERY_CANDIDATE"
    out = apply_daily_timing_gate(s, _daily(["DAILY_NEUTRAL", "DAILY_BREAKOUT",
                                             "DAILY_NEUTRAL", "DAILY_NEUTRAL"]), settings)
    assert out.iloc[1]["target"] > 0
    assert out.iloc[1]["timing_action"] == "ENTER"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_daily_timing 全部通过 ✅")
