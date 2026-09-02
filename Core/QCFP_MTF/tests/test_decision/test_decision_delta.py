# coding: utf-8
"""DecisionDelta 测试（24 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_delta import decision_delta


def _snap(target=0.4, perm="ALLOW", setup="ACTIVE", fsm="HOLDING",
          risk="Medium", exit_ev="NONE", reason="NONE"):
    return {"target_position": target, "permission": perm,
            "setup_type": setup, "next_fsm_state": fsm,
            "risk_level": risk, "exit_event_kind": exit_ev,
            "primary_reason": reason}


def test_delta_change():
    prev = _snap(target=0.4, setup="ACTIVE")
    curr = _snap(target=0.2, setup="MATURE", fsm="TRIMMING",
                 reason="WAVE_MATURE")
    d = decision_delta(prev, curr, binding_constraint="DRAWDOWN_CAP")
    assert d["target_delta"] == -0.2
    assert d["changed"] is True
    assert any("Wave" in c for c in d["what_changed"])
    assert d["binding_constraint"] == "DRAWDOWN_CAP"
    assert d["risk_increased"] is False


def test_delta_no_change():
    d = decision_delta(_snap(target=0.4), _snap(target=0.4))
    assert d["target_delta"] == 0.0
    assert d["changed"] is False
