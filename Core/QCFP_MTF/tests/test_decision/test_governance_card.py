# coding: utf-8
"""Governance Decision Card 真实证明测试（新 12 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.decision.governance_card import governance_card_lines, \
    governance_card_proofs


def _snap():
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.08,
        raw_target_position=0.10, pit_grade="B",
        run_id="run_1",
        binding_constraint="portfolio_cap",
        primary_reason="WAVE_CONFIRM",
        context={"governance_proof": {"proof": "PASS"}})


def test_proofs_from_real_fields():
    proofs = governance_card_proofs(_snap())
    by_label = {p["label"]: p for p in proofs}
    assert by_label["FinalTarget 已过 Governance Proof"]["ok"] is True
    assert by_label["PIT Certificate（B）"]["ok"] is True
    assert by_label["Governance 约束拦截"]["value"] == "portfolio_cap"
    assert by_label["FinalTarget 单调不增（raw→final）"]["ok"] is True
    assert by_label["Ledger Verified"]["value"] == "run_1"
    # 每个 ✓ 都有可反查的 evidence_ref
    for p in proofs:
        assert p["evidence_ref"]


def test_card_renders_lines():
    out = governance_card_lines(_snap())
    assert "Governance Proof" in out
    assert "context.governance_proof.proof" in out
    assert all(p["evidence_ref"] for p in governance_card_proofs(_snap()))


def test_fake_conditions_removed():
    """不再出现恒真伪证明。"""
    proofs = governance_card_proofs(_snap())
    labels = [p["label"] for p in proofs]
    assert not any("未升级权限" in l for l in labels)
    assert not any("PIT Valid" == l for l in labels)
