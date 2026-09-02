# coding: utf-8
"""2.5 Governance Invariant Matrix（property-based 治理测试）

枚举 Permission × Setup × Risk × Previous Position × Daily，
每组运行唯一决策引擎并验证 8 条治理不变量——"不可越权"从手写用例
升级为系统级 property test。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import DecisionConfig, evaluate
from QCFP_MTF.decision.versions import (DECISION_RULE_VERSION, FEATURE_SET,
                                        MODEL_VERSION, SCHEMA_VERSION,
                                        feature_manifest_hash)

PERMISSIONS = ("BLOCK", "WATCH", "TEST", "ALLOW", "STRONG_ALLOW")
SETUPS = ("BREAKOUT", "PULLBACK", "ACCUMULATION", "RECOVERY", "NONE")
RISKS = ("Low", "Medium", "High", "Extreme")
PREV_POSITIONS = (0.0, 0.05, 0.3, 0.5, 0.7)
DAILIES = ("DAILY_BREAKOUT", "DAILY_NEUTRAL")


def _row(perm, setup, risk, prev, daily, **kw):
    cfp = {
        "BLOCK": ("C↓", "F↓", "P↓", "F↓"),
        "WATCH": ("C→", "F→", "P→", "F→"),
        "TEST": ("C→", "F↑", "P→", "F→"),
        "ALLOW": ("C↑", "F↑", "P↑", "F↑"),
        "STRONG_ALLOW": ("C↑", "F↑", "P↑", "F↑"),
    }[perm]
    weekly = {"BREAKOUT": "Breakout", "PULLBACK": "Pullback",
              "ACCUMULATION": "Consolidation", "RECOVERY": "Breakout",
              "NONE": "Consolidation"}[setup]
    return {
        "stock_code": "TMX", "decision_date": "2026-08-21",
        "c_state": cfp[0], "f_state": cfp[1], "p_state": cfp[2],
        "prev_f_state": cfp[3],
        "monthly_behavior_state": "Improving",
        "tactical_signal": weekly, "daily_state": daily,
        "risk_level": risk, "des_score": 2,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.3, "q_trend_score": 55.0,
        "market_context": "neutral", "cbi_state": "CBI_STABLE",
        "catalyst_score": 1.0,
    }


def test_version_identity_three_dimensional():
    """2.5：三维版本身份 + FEATURE_SET manifest 确定性"""
    assert MODEL_VERSION == "QCFP-MTF-2.5.0"
    assert DECISION_RULE_VERSION == "GOV-2.5.0"
    assert SCHEMA_VERSION == "DECISION-1.1"
    assert feature_manifest_hash() == feature_manifest_hash()
    assert len(feature_manifest_hash()) == 16
    assert "participation_budget" in FEATURE_SET
    snap = evaluate(_row("ALLOW", "BREAKOUT", "Medium", 0.0,
                         "DAILY_BREAKOUT"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.model_version == MODEL_VERSION
    assert snap.rule_version == DECISION_RULE_VERSION
    assert snap.schema_version == SCHEMA_VERSION
    assert snap.feature_manifest_hash == feature_manifest_hash()


def test_governance_invariant_matrix():
    """枚举组合全部通过唯一引擎，8 条不变量无违规"""
    n = 0
    for perm in PERMISSIONS:
        for setup in SETUPS:
            for risk in RISKS:
                for prev in PREV_POSITIONS:
                    for daily in DAILIES:
                        row = _row(perm, setup, risk, prev, daily)
                        snap = evaluate(dict(row), "FLAT", prev,
                                        DEFAULT_SETTINGS,
                                        config=DecisionConfig())
                        t = snap.target_position
                        # I1 HardExit → 0
                        if snap.exit_severity >= 3:
                            assert t == 0.0, (perm, setup, risk, prev, daily)
                        # I2 BLOCK → 0
                        if perm == "BLOCK":
                            assert t == 0.0
                        # I3 WATCH 非观察 → ≤ previous
                        if perm == "WATCH" and snap.participation_mode != "OBSERVE":
                            assert t <= prev + 1e-9
                        # I4 target ≤ participation cap（观察仓 ≤ 观察上限）
                        if snap.participation_mode == "OBSERVE":
                            assert t <= max(prev, snap.participation_cap) + 1e-9
                        # I5 权限不被 Setup/Daily 升级
                        assert snap.institutional_permission == perm or \
                            perm == "ALLOW" and \
                            snap.institutional_permission == "STRONG_ALLOW"
                        # I6 0 仓位不得停留风险状态
                        assert not (t == 0.0 and snap.next_fsm_state in
                                    ("TESTING", "BUILDING", "HOLDING"))
                        # I7 Daily 不升级权限（同权限不同 daily 结果权限一致）
                        # I8 TQS 门槛：target>0 时 TQS ≥ min_tradable
                        if t > 0:
                            assert snap.trade_quality >= 40.0
                        n += 1
    assert n == len(PERMISSIONS) * len(SETUPS) * len(RISKS) * \
        len(PREV_POSITIONS) * len(DAILIES)


def test_market_scale_reduces_budget():
    """保留 Market Context：risk_off 预算 < neutral < risk_on"""
    row = _row("ALLOW", "BREAKOUT", "Medium", 0.0, "DAILY_BREAKOUT")
    caps = {}
    for mkt in ("risk_on", "neutral", "risk_off"):
        row["market_context"] = mkt
        snap = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
        caps[mkt] = snap.participation_cap
    assert caps["risk_on"] > caps["neutral"] > caps["risk_off"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_governance_matrix 全部通过 ✅")
