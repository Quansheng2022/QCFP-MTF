# coding: utf-8
"""Golden Dataset 回归（MTR Closure 迁移）：关键历史案例的输入→输出。

V21（MTR Closure Sprint D）：Golden 测试全面迁移到 Canonical-only——
禁止引用 legacy 决策权威（action_generator / position_sizing）。
Golden 期望值随 Canonical 语义更新，变更原因见各 JSON 的
change_reason（Golden Hash 变化必须经 Change Impact Review 批准）。
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.fusion.mtf_alignment import align_mtf
from QCFP_MTF.scripts.dss_report import trade_intent, \
    trade_interpretation

GOLDEN_DIR = PROJECT_ROOT / "Core" / "QCFP_MTF" / "tests" / "golden"


def _load(name):
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def _evaluate(g, prev_state="FLAT", prev_pos=0.0):
    row = dict(g["inputs"])
    row.update({"risk_level": "High", "data_quality": "B",
                "chip_stability_confidence": "Medium",
                "market_context": "Sideway",
                "decision_date": "2026-08-21"})
    return evaluate(row, prev_state, prev_pos, DEFAULT_SETTINGS)


def test_00371_breakdown_golden_canonical():
    """北控水务 2026 阴跌：周线 Breakdown + DES>=12 → Canonical
    Hard Exit，风险归零（NO_TRADE from FLAT；绝不产生新仓）。"""
    g = _load("00371_2026_breakdown.json")
    inp, exp = g["inputs"], g["expected"]
    assert g.get("change_reason"), "Golden 变更必须有批准的 change_reason"
    mtf, _ = align_mtf(inp["structural_regime"],
                       inp["monthly_behavior_state"], inp["tactical_signal"])
    assert mtf == exp["mtf_regime"]                       # BULLISH_WARNING
    snap = _evaluate(g)
    assert inp["des_score"] >= 7
    # Canonical：HARD_EXIT → 目标 0、无新风险（FLAT 起算为 NO_TRADE）
    assert snap.primary_reason == "HARD_EXIT"
    assert snap.target_position == 0.0
    assert snap.canonical_action == exp["canonical_action"]
    assert exp["final_target"] == 0.0
    assert trade_intent({"action_signal": exp["canonical_action"]}) == \
        exp["canonical_action"]


def test_01951_recovery_golden_canonical():
    """锦欣生殖 2024：空头结构 + 52W 低位 + 盘整 → Canonical 空仓判断
    NO_TRADE；战术试多只存在于解释层，不得进入决策层（P0-C）。"""
    g = _load("01951_2024_recovery.json")
    inp, exp = g["inputs"], g["expected"]
    assert g.get("change_reason"), "Golden 变更必须有批准的 change_reason"
    mtf, _ = align_mtf(inp["structural_regime"],
                       inp["monthly_behavior_state"], inp["tactical_signal"])
    assert mtf == exp["mtf_regime"]                       # BEARISH_CONFIRMED
    snap = _evaluate(g)
    assert snap.canonical_action == exp["canonical_action"]  # NO_TRADE
    assert snap.target_position == 0.0
    # 决策层不得出现未经治理的战术试多仓位
    assert snap.target_position <= 0.0
    assert trade_intent({"action_signal": "NO_TRADE"}) == "NO_TRADE"
    # 解释层（非决策）可说明战术试多背景
    assert trade_interpretation(
        {"align_method": "tactical_override"}) != ""


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_golden_cases 全部通过 ✅")
