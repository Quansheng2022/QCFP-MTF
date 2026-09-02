# coding: utf-8
"""DecisionDelta 变化解释测试（新 24 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_delta import decision_delta, \
    delta_completeness


def test_delta_explains_change():
    prev = {"target_position": 0.30, "permission": "ALLOW",
            "wave_stage": "ACTIVE", "next_fsm_state": "HOLDING",
            "risk_level": "Low", "liquidity_cap": 0.30}
    cur = {"target_position": 0.10, "permission": "TEST",
           "wave_stage": "MATURE", "next_fsm_state": "TESTING",
           "risk_level": "Medium", "liquidity_cap": 0.20,
           "primary_reason": "WAVE_MATURED"}
    d = decision_delta(prev, cur, binding_constraint="risk_cap")
    assert d["target_delta"] == -0.20
    assert any("Permission: ALLOW → TEST" in c for c in d["what_changed"])
    assert any("Wave Stage: ACTIVE → MATURE" in c
               for c in d["what_changed"])
    assert any("Liquidity Cap: 0.3 → 0.2" in c
               for c in d["what_changed"])
    assert d["binding_constraint"] == "risk_cap"
    c = delta_completeness(d)
    assert c["complete"] is True
    assert c["missing"] == []


def test_delta_incomplete_without_binding():
    prev = {"target_position": 0.1}
    cur = {"target_position": 0.3, "primary_reason": "WAVE"}
    d = decision_delta(prev, cur)
    c = delta_completeness(d)
    assert c["target_changed"] is True
    assert "BINDING_CONSTRAINT" in c["missing"]
    assert c["complete"] is False
