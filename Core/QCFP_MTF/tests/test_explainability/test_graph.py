# coding: utf-8
"""Decision Explainability Graph 测试（38 号：Threshold/Version 边属性）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.explainability.graph import build_explainability_graph, \
    graph_to_md, provenance_graph


def _snap():
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.04,
        rule_version="GOV-2.5.0",
        raw_target_position=0.08, participation_mode="EXPLORE",
        participation_cap=0.10,
        context={"trace": {"institutional": ("base",)}})


def test_graph_edges_have_threshold_and_version():
    g = build_explainability_graph(_snap())
    assert len(g["edges"]) == 7
    for e in g["edges"]:
        assert "threshold" in e
        assert "version" in e
        assert "rule" in e and "output" in e


def test_graph_to_md():
    md = graph_to_md(build_explainability_graph(_snap()))
    assert "Final Position" in md
    assert "GOV-2.5.0" in md


def test_provenance_graph_21():
    g = provenance_graph(_snap())
    assert g["decision_id"] == "d1"
    assert len(g["nodes"]) == 9
    for n in g["nodes"]:
        for k in ("value", "timestamp", "source", "version",
                  "evidence", "dependency", "decision_effect"):
            assert k in n
    assert any(n["node"] == "Final Target" for n in g["nodes"])
