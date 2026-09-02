# coding: utf-8
"""CanonicalAction = FinalTarget Delta 测试（Convergence 新 4 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.canonical_action import assert_canonical_action_invariant, \
    canonical_action


def test_action_derivation():
    assert canonical_action(0.0, 0.0) == "NO_TRADE"
    assert canonical_action(0.0, 0.05) == "ENTRY"
    assert canonical_action(0.05, 0.10) == "ADD"
    assert canonical_action(0.10, 0.10) == "HOLD"
    assert canonical_action(0.10, 0.05) == "REDUCE"
    assert canonical_action(0.10, 0.0) == "EXIT"


def test_invariant_pass():
    r = assert_canonical_action_invariant(0.0, 0.05, "ENTRY")
    assert r["verdict"] == "OK"


def test_invariant_fail_blocks():
    r = assert_canonical_action_invariant(0.0, 0.0, "ENTRY")
    assert r["verdict"] == "CANONICAL_ACTION_INVARIANT_FAIL"
    assert r["ok"] is False
