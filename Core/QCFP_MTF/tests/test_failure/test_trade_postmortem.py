# coding: utf-8
"""Decision Error Taxonomy 接真实交易复盘测试（新 76 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.failure.decision_error_taxonomy import trade_postmortem


def test_exit_error_postmortem():
    r = trade_postmortem({"trade_id": "T1", "outcome": "loss",
                          "error": "exit 止损过晚"})
    assert r["error_classification"] == "EXIT_ERROR"
    assert r["corrective_layer"] == "exit_quality"
    assert r["root_cause"]


def test_pit_error_even_if_profitable():
    r = trade_postmortem({"trade_id": "T2", "outcome": "profit",
                          "error": "PIT 数据超前"})
    assert r["error_classification"] == "PIT_ERROR"
    assert "PIT 污染" in r["rule"]


def test_unclassified():
    r = trade_postmortem({"trade_id": "T3", "outcome": "loss",
                          "error": "完全未知原因"})
    assert r["classified"] is False
    assert r["corrective_layer"] == "架构责任边界不清"
