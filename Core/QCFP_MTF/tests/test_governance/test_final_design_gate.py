# coding: utf-8
"""Final Design Principles 停止规则测试（新 100 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.final_design_principles import \
    FINAL_DESIGN_PRINCIPLES, final_design_principle_gate


def test_ten_principles_frozen():
    assert len(FINAL_DESIGN_PRINCIPLES) == 10


def test_conformant_allows_promotion():
    checks = {i: True for i in range(1, 11)}
    r = final_design_principle_gate(checks, {"sharpe": 0.8})
    assert r["verdict"] == "PROMOTION_OK"
    assert r["allowed"] is True


def test_violation_rejects_regardless_of_performance():
    checks = {i: True for i in range(1, 11)}
    checks[3] = False  # Risk > Return
    r = final_design_principle_gate(checks, {"sharpe": 3.0})
    assert r["verdict"] == "PROMOTION_REJECTED"
    assert r["allowed"] is False
    assert r["stop_rule"] is True
