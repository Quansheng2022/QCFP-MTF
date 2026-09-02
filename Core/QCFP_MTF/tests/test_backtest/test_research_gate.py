# coding: utf-8
"""2.5 Research Gate（G0–G7）与 PIT 真实披露覆盖测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.research_gate import evaluate_research_gate
from QCFP_MTF.common.asof import (apply_disclosure_overrides,
                                  load_disclosure_overrides)


def _summary(sharpe=0.5, pf=1.5, oos=0.3, status="PASS", pit="C"):
    return {
        "overall": {"sharpe": sharpe, "profit_factor": pf,
                    "annualized_return": 0.05, "max_drawdown": -0.1},
        "rolling_oos_evaluation": [{"sharpe": oos}] * 5,
        "run_status": {"status": status, "pit_grade": pit},
        "pit_grade": pit, "pit_disclosure_mode": "ESTIMATED",
    }


def test_research_gate_all_pass_with_pit_ab():
    g = evaluate_research_gate(
        _summary(pit="A"), {"cost_stress_breakeven": 2.5,
                            "t_plus_1_verified": True, "ledger_ok": True,
                            "model_version": "m", "rule_version": "r",
                            "schema_version": "s"})
    assert g["overall"] == "PASS"
    assert g["status_label"] == "Research Validated"


def test_research_gate_pit_c_is_conditional():
    g = evaluate_research_gate(_summary(pit="C"), {"ledger_ok": True,
                                                   "model_version": "m",
                                                   "rule_version": "r",
                                                   "schema_version": "s"})
    assert g["overall"] == "WARN"
    assert g["status_label"] == "Conditional（研究探索）"


def test_research_gate_fail_on_negative_sharpe():
    g = evaluate_research_gate(_summary(sharpe=-0.2, pf=0.8, oos=-0.1),
                               {"model_version": "m", "rule_version": "r",
                                "schema_version": "s"})
    assert g["overall"] == "FAIL"
    assert g["status_label"] == "Not Validated"


def test_disclosure_override_applies_real_dates():
    """PIT 真实披露日覆盖：匹配 (stock, period_end) 时使用真实日期"""
    df = pd.DataFrame({
        "stock_code": ["00700", "01951"],
        "period_end": ["2025-12-31", "2025-12-31"],
        "available_date_dt": pd.to_datetime(["2026-02-14", "2026-02-14"]),
    })
    overrides = {("00700", "2025-12-31"): "2026-03-20"}
    out = apply_disclosure_overrides(df, overrides)
    assert out.loc[out["stock_code"] == "00700",
                   "available_date_dt"].iloc[0] == pd.Timestamp("2026-03-20")
    assert out.loc[out["stock_code"] == "01951",
                   "available_date_dt"].iloc[0] == pd.Timestamp("2026-02-14")
    # 模板文件存在（无覆盖表时为 ESTIMATED）
    from QCFP_MTF.common.paths import get_config_dir
    assert (get_config_dir() / "qcfp_disclosure_dates.template.csv").exists()
    assert load_disclosure_overrides() == {} or isinstance(
        load_disclosure_overrides(), dict)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_research_gate 全部通过 ✅")
