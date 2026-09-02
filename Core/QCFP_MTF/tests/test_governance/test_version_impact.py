# coding: utf-8
"""Version Impact Analysis 测试（37 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.version_impact import impact_to_md, version_impact


def _snap(target=0.0, perm="ALLOW", setup="BREAKOUT", fsm="FLAT",
          next_fsm="TESTING", exit_ev="NONE", reason="SETUP_ABSENT"):
    return {"target_position": target, "institutional_permission": perm,
            "setup_type": setup, "prev_fsm_state": fsm,
            "next_fsm_state": next_fsm, "exit_event_kind": exit_ev,
            "primary_reason": reason}


def test_no_flip_identical():
    old = {"d1": _snap(target=0.1)}
    new = {"d1": _snap(target=0.1)}
    imp = version_impact(old, new, "v1", "v2")
    assert imp.flip_rate == 0.0
    assert imp.n_decisions == 1


def test_flip_detected():
    old = {"d1": _snap(target=0.1, perm="ALLOW")}
    new = {"d1": _snap(target=0.0, perm="BLOCK")}
    imp = version_impact(old, new, "v1", "v2")
    assert imp.flip_rate == 1.0
    assert len(imp.flips) == 1
    assert imp.field_flip_counts["permission"] == 1
    assert imp.field_flip_counts["position"] == 1


def test_pnl_and_risk_diff():
    old = {"d1": _snap(target=0.1)}
    new = {"d1": _snap(target=0.2)}
    imp = version_impact(old, new, pnl_map={"d1": (0.05, 0.08)},
                         risk_map={"d1": (0.1, 0.15)})
    assert imp.pnl_diff == 0.03
    assert imp.risk_diff == 0.05


def test_impact_to_md():
    old = {"d1": _snap(target=0.1)}
    new = {"d1": _snap(target=0.2)}
    md = impact_to_md(version_impact(old, new, "v1", "v2"))
    assert "Version Impact" in md
