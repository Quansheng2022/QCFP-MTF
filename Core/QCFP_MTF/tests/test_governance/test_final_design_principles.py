# coding: utf-8
"""QCFP-MTF Final Design Principle 测试（100 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.final_design_principles import \
    FEATURE_PROPOSAL_FIELDS, FINAL_DESIGN_PRINCIPLES, \
    design_principle_check, feature_proposal_check


def _complete_proposal():
    return {f: f"value-{f}" for f in FEATURE_PROPOSAL_FIELDS}


def test_complete_proposal_accepted():
    r = feature_proposal_check(_complete_proposal())
    assert r["verdict"] == "PROPOSAL_ACCEPTED"
    assert r["production_allowed"] is True
    assert r["missing_fields"] == []


def test_incomplete_proposal_research_only():
    proposal = _complete_proposal()
    del proposal["ablation_plan"]
    r = feature_proposal_check(proposal)
    assert r["verdict"] == "RESEARCH_ONLY"
    assert r["production_allowed"] is False
    assert r["missing_fields"] == ["ablation_plan"]


def test_ten_principles_frozen():
    assert len(FINAL_DESIGN_PRINCIPLES) == 10
    assert "Permission > Signal" in FINAL_DESIGN_PRINCIPLES
    assert "Complexity must prove incremental practical value" in \
        FINAL_DESIGN_PRINCIPLES


def test_design_principle_check():
    checks = {i: True for i in range(1, 11)}
    assert design_principle_check(checks)["verdict"] == "CONFORMANT"
    checks[3] = False  # Risk > Return 被违反
    r = design_principle_check(checks)
    assert r["verdict"] == "PRINCIPLE_VIOLATION"
    assert "Risk > Return" in r["failures"]
