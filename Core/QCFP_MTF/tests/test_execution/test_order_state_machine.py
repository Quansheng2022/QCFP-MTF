# coding: utf-8
"""Order State Machine + Position Reconciliation 测试（Release 2：新 16 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.execution.order_state_machine import OrderStateMachine, \
    position_reconciliation


def test_duplicate_order_blocked():
    m = OrderStateMachine()
    m.send("O1", 100)
    r = m.send("O1", 100)
    assert r["state"] == "DUPLICATE_BLOCKED"


def test_timeout_blocks_new_order():
    m = OrderStateMachine()
    m.send("O1", 100)
    r = m.timeout("O1")
    assert r["state"] == "UNKNOWN"
    assert r["block_new_order"] is True
    assert r["action"] == "QUERY_BROKER_AND_RECONCILE"


def test_partial_fill():
    m = OrderStateMachine()
    m.send("O1", 100)
    assert m.ack("O1", fill=40)["state"] == "PARTIAL"
    assert m.ack("O1", fill=100)["state"] == "FILLED"


def test_reject_and_cancel():
    m = OrderStateMachine()
    m.send("O1", 100)
    assert m.ack("O1", fill=0)["state"] == "REJECTED"
    m2 = OrderStateMachine()
    m2.send("O2", 100)
    assert m2.cancel("O2")["state"] == "CANCELLED"


def test_reconnect_unknown_state():
    m = OrderStateMachine()
    m.send("O1", 100)
    m.timeout("O1")
    r = m.ack("O1", fill=100)
    assert r["state"] == "UNKNOWN"
    assert "先查询 broker" in r["reason"]


def test_position_mismatch_no_new_risk():
    assert position_reconciliation(0.2, 0.2, 0.1)["status"] == "MISMATCH"
    assert position_reconciliation(0.2, 0.2, None)["status"] == "UNKNOWN"
    assert position_reconciliation(0.2, 0.2, None)["no_new_risk"] is True


def test_position_in_sync():
    r = position_reconciliation(0.2, 0.2, 0.2)
    assert r["status"] == "IN_SYNC"
    assert r["no_new_risk"] is False
