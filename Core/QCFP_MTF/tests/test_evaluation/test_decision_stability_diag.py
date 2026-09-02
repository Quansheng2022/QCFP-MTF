# coding: utf-8
"""Decision Stability Diagnostics 测试（25 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.decision_stability_diag import \
    decision_stability_diag


def test_stable():
    d = [
        {"action": "BUY", "target_position": 0.05, "fsm_state": "TESTING",
         "holding_days": 1},
        {"action": "HOLD", "target_position": 0.05, "fsm_state": "HOLDING",
         "holding_days": 5},
        {"action": "HOLD", "target_position": 0.05, "fsm_state": "HOLDING",
         "holding_days": 10},
        {"action": "REDUCE", "target_position": 0.02,
         "fsm_state": "TRIMMING", "holding_days": 15},
    ]
    r = decision_stability_diag(d)
    assert r["flapping_suspect"] is False
    assert r["diagnostic_only"] is True


def test_flapping_detected():
    d = [
        {"action": a, "target_position": t, "fsm_state": "HOLDING",
         "holding_days": 1}
        for a, t in [("BUY", 0.05), ("REDUCE", 0.04), ("BUY", 0.05),
                     ("REDUCE", 0.04), ("BUY", 0.05), ("REDUCE", 0.04)]]
    r = decision_stability_diag(d)
    assert r["flapping_suspect"] is True
    assert r["decision_flip_rate"] > 0.5
