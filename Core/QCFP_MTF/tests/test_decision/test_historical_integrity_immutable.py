# coding: utf-8
"""Historical Decision Integrity 不可变测试（新 46 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.historical_integrity import \
    assert_historical_fact_immutable


def test_append_only_ok():
    ops = [{"kind": "INSERT", "decision_id": "d1"},
           {"kind": "INSERT", "decision_id": "d2"}]
    r = assert_historical_fact_immutable(ops)
    assert r["append_only"] is True
    assert r["verdict"] == "HISTORY_IMMUTABLE"


def test_update_violation():
    ops = [{"kind": "INSERT"}, {"kind": "UPDATE", "decision_id": "d1"}]
    r = assert_historical_fact_immutable(ops)
    assert r["append_only"] is False
    assert r["verdict"] == "HISTORY_MUTATED"
    assert len(r["violations"]) == 1


def test_delete_violation():
    ops = [{"kind": "DELETE", "decision_id": "d1"}]
    r = assert_historical_fact_immutable(ops)
    assert r["verdict"] == "HISTORY_MUTATED"
