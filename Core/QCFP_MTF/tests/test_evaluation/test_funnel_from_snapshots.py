# coding: utf-8
"""Opportunity Funnel 接真实决策数据测试（新 19 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.evaluation.opportunity_funnel import \
    opportunity_funnel_from_snapshots


def _snap(perm="ALLOW", pit="B", wave="ACTIVE", fsm="TESTING",
          risk="Low", binding="", target=0.2, code="S"):
    return DecisionSnapshot(
        decision_id=f"{code}_1", stock_code=code, decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission=perm, permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state=fsm,
        previous_position=0.0, target_position=target, pit_grade=pit,
        binding_constraint=binding, wave_stage=wave)


def test_funnel_from_snapshots():
    snaps = [
        _snap(code="A"),                                    # 全通过
        _snap(perm="BLOCK", code="B"),                      # Permission 过滤
        _snap(wave="", code="C"),                           # Wave 过滤
        _snap(fsm="FLAT", code="D"),                        # FSM 过滤
        _snap(binding="liquidity_cap", target=0.05, code="E"),  # Liquidity 过滤
    ]
    f = opportunity_funnel_from_snapshots(snaps)
    assert f["counts"]["universe"] == 5
    assert f["counts"]["pit_valid"] == 5
    assert f["counts"]["permission_eligible"] == 4
    assert f["counts"]["final_trade"] == 1
    assert f["bottleneck"] is not None


def test_funnel_empty():
    f = opportunity_funnel_from_snapshots([])
    assert f["counts"]["universe"] == 0
