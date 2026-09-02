# coding: utf-8
"""Constraint Trace 测试（32 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.constraint_trace import build_constraint_trace, \
    trace_to_md
from QCFP_MTF.decision.governance import finalize_target


def test_constraint_trace_reductions():
    steps = [
        ("raw_target", 0.12, 0.12, "初始", "1.0"),
        ("permission_cap", 0.12, 0.08, "PERMISSION_ALLOWED", "1.0"),
        ("risk_cap", 0.08, 0.06, "RISK_LIMIT", "1.0"),
        ("portfolio_cap", 0.06, 0.04, "PORTFOLIO_LIMIT", "1.0"),
        ("liquidity_cap", 0.04, 0.03, "LIQUIDITY_LIMIT", "1.0"),
    ]
    t = build_constraint_trace(steps)
    assert t["final_target"] == 0.03
    assert t["reductions"]["permission_cap"] == 0.04
    assert t["reductions"]["liquidity_cap"] == 0.01
    assert len(t["steps"]) == 5


def test_finalize_target_produces_trace():
    fin = finalize_target(
        "ALLOW", "TRADE", 0.5, raw_target=0.12, previous_position=0.0,
        risk_budget=0.02, stop_distance=0.10, portfolio_cap=0.04,
        liquidity_cap=0.03)
    assert "constraint_trace" in fin
    assert fin["constraint_trace"]["final_target"] == fin["target"]
    assert fin["constraint_trace"]["steps"][0]["constraint"] == "raw_target"


def test_trace_to_md():
    steps = [("raw_target", 0.1, 0.1, "初始", "1.0"),
             ("permission_cap", 0.1, 0.08, "PERMISSION_ALLOWED", "1.0")]
    md = trace_to_md(build_constraint_trace(steps))
    assert "Constraint Trace" in md
