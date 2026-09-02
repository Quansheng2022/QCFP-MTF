# coding: utf-8
"""Risk Constraint Attribution 测试（P1-7 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.constraint_trace import binding_constraint, \
    build_constraint_trace
from QCFP_MTF.decision.governance import finalize_target


def test_binding_constraint_identifies_cap():
    steps = [
        ("raw_target", 0.30, 0.30, "初始", "1.0"),
        ("permission_cap", 0.30, 0.20, "PERMISSION_ALLOWED", "1.0"),
        ("risk_cap", 0.20, 0.12, "RISK_LIMIT", "1.0"),
        ("portfolio_cap", 0.12, 0.08, "PORTFOLIO_LIMIT", "1.0"),
        ("liquidity_cap", 0.08, 0.05, "LIQUIDITY_LIMIT", "1.0"),
        ("execution_cap", 0.05, 0.04, "EXECUTION_LIMIT", "1.0"),
    ]
    trace = build_constraint_trace(steps)
    r = binding_constraint(trace)
    assert r["binding_constraint"] == "execution_cap"
    assert r["final_target"] == 0.04
    assert r["reduction_attribution"]["permission_cap"] == 0.10
    assert r["total_reduction"] == 0.26


def test_finalize_target_binding():
    fin = finalize_target("ALLOW", "TRADE", 0.5, raw_target=0.30,
                          previous_position=0.0, risk_budget=0.02,
                          stop_distance=0.10, portfolio_cap=0.08,
                          liquidity_cap=0.05, execution_cap=0.04)
    r = binding_constraint(fin["constraint_trace"])
    assert r["binding_constraint"] in ("execution_cap", "liquidity_cap")
    assert r["final_target"] == fin["target"]
