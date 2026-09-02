# coding: utf-8
"""战术覆盖全链路核查（P0-2）

用 01951 的真实场景（DECLINE + Improving + Consolidation + 52W=0.0272）
验证 align_mtf → action → position → 止损展示 的完整链路一致性；
并核对数据库中 01951 最新决策行与代码规则一致。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.action_generator import generate_action
from QCFP_MTF.decision.position_sizing import effective_position_cqs
from QCFP_MTF.decision.stop_loss import get_stop_loss_policy, stop_loss_display
from QCFP_MTF.fusion.mtf_alignment import align_mtf


def test_override_chain_01951_case():
    # 01951 2026-08-21：STRUCTURAL_DECLINE / Improving / Consolidation / 52W=0.0272
    mtf, method = align_mtf(
        "STRUCTURAL_DECLINE", "Improving", "Consolidation",
        tactical_override=True, position_52w=0.0272,
        max_52w_position=0.15,
        min_trigger=("Breakout", "Pullback", "Consolidation"))
    assert mtf == "BULLISH_WARNING"
    assert method == "tactical_override"

    action = generate_action(mtf, "STRUCTURAL_DECLINE", "High", DEFAULT_SETTINGS)
    assert action == "REDUCE"

    # CQS=1（中性偏强）→ 观察仓 20%；Risk High 上限 0.5 → min=0.2
    target = effective_position_cqs(mtf, "High", DEFAULT_SETTINGS,
                                    catalyst_score=1, tactical_override=True)
    assert abs(target - 0.2) < 1e-9

    pol = get_stop_loss_policy(DEFAULT_SETTINGS)
    display = stop_loss_display(pol)
    assert "建仓周最低价×(1-2%)" in display
    assert abs(float(pol["buffer_pct"]) - 0.02) < 1e-9


def test_db_row_consistent_with_code():
    """01951 最新展示行必须与 ACTIVE Ledger canonical 决策一致（Ledger-first）。

    展示表 qcfp_mtf_decision.action_signal 由 scripts/decision_engine.py 从
    qcfp_decision_ledger 的 ACTIVE DecisionSnapshot 纯投影得到
    （canonical_action = PreviousPosition→FinalTarget 确定性派生，不重算决策）。
    战术层 generate_action() 的 REDUCE 是战术意图层，不是展示真值：
    01951 最近 ACTIVE Ledger 决策处于 WATCH/空仓冷却路径（previous=0、
    final=0）→ canonical=NO_TRADE，展示行因此也必须为 NO_TRADE。
    """
    from QCFP_MTF.config.settings import load_qcfp_settings
    from QCFP_MTF.decision.canonical_action import canonical_action
    from QCFP_MTF.decision.decision_ledger import load_ledger_snapshot
    from QCFP_MTF.decision.decision_snapshot import _settings_hash

    conn = connect()
    try:
        r = conn.execute(
            "SELECT decision_date, mtf_regime, structural_regime, "
            "tactical_signal, action_signal, align_method, catalyst_score, "
            "catalyst_type "
            "FROM qcfp_mtf_decision WHERE stock_code='01951' "
            "ORDER BY decision_date DESC LIMIT 1").fetchone()
        assert r is not None
        assert r["mtf_regime"] == "BULLISH_WARNING"
        assert r["structural_regime"] == "STRUCTURAL_DECLINE"
        assert r["align_method"] == "tactical_override"
        assert r["catalyst_score"] is not None
        assert r["catalyst_type"] == "中性偏强"
        # Ledger-first：展示 action_signal 必须等于 ACTIVE Ledger 决策的
        # canonical action（与 scripts/decision_engine.py 投影口径一致）。
        settings_hash = _settings_hash(load_qcfp_settings())
        s = load_ledger_snapshot(conn, "01951", r["decision_date"],
                                 settings_hash=settings_hash)
        assert s is not None, \
            "01951 最新展示行缺少匹配的 ACTIVE Ledger 决策（投影缺失）"
        expected = canonical_action(
            float(s["previous_position"] or 0.0),
            float(s["target_position"] or 0.0))
        assert r["action_signal"] is not None
        assert r["action_signal"] == expected
    finally:
        conn.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_tactical_chain 全部通过 ✅")
