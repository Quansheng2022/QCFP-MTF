# coding: utf-8
"""Binding Constraint Attribution → 规则去留测试（Release 3：新 25 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.binding_constraint_frequency import \
    constraint_keep_verdict


def test_keep_with_evidence():
    r = constraint_keep_verdict("Permission", {
        "triggered_frequency": 0.35, "binding_frequency": 0.18,
        "independent_impact_frequency": 0.16}, ablation_value=0.02)
    assert r["verdict"] == "KEEP"


def test_retire_zero_binding_zero_ablation():
    r = constraint_keep_verdict("ExecutionCap", {
        "triggered_frequency": 0.02, "binding_frequency": 0.0,
        "independent_impact_frequency": 0.0}, ablation_value=0.0)
    assert r["verdict"] == "RETIRE"


def test_merge_frequent_trigger_never_binding():
    r = constraint_keep_verdict("ThemeCap", {
        "triggered_frequency": 0.2, "binding_frequency": 0.0,
        "independent_impact_frequency": 0.0}, ablation_value=0.01)
    assert r["verdict"] == "MERGE"


def test_constitutional_kept():
    r = constraint_keep_verdict("Permission", {}, constitutional=True)
    assert r["verdict"] == "KEEP"
