# coding: utf-8
"""Minimal Governed Core 测试（90 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.minimal_governed_core import \
    MINIMAL_GOVERNED_CORE, minimal_governed_core_check


def _modules():
    return {
        "pit_evidence": {"classification": "CORE"},
        "institutional_permission": {"classification": "CORE"},
        "wave_opportunity": {"classification": "CORE"},
        "fsm_position_proposal": {"classification": "CORE"},
        "risk_portfolio_liquidity_governance": {
            "classification": "CORE"},
        "canonical_final_target": {"classification": "CORE"},
        "execution_plan": {"classification": "CORE"},
        "decision_snapshot": {"classification": "CORE"},
        "append_only_ledger": {"classification": "CORE"},
        "research_validation": {"classification": "CORE"},
        "binding_constraint_trace": {
            "classification": "SUB_CAPABILITY",
            "subcapability_of": "canonical_final_target"},
        "ablation_studio": {"classification": "RESEARCH_ONLY"},
        "shadow_comparator": {"classification": "SHADOW_ONLY"},
    }


def test_aligned_core():
    r = minimal_governed_core_check(_modules())
    assert r["aligned"] is True
    assert r["verdict"] == "ALIGNED"
    assert r["missing_core"] == []
    assert r["violations"] == []


def test_missing_core_detected():
    modules = _modules()
    del modules["append_only_ledger"]
    r = minimal_governed_core_check(modules)
    assert r["aligned"] is False
    assert "append_only_ledger" in r["missing_core"]


def test_orphan_production_module_violation():
    modules = _modules()
    modules["extra_alpha_scorer"] = {"classification": "PRODUCTION"}
    r = minimal_governed_core_check(modules)
    assert r["aligned"] is False
    assert any("extra_alpha_scorer" in v for v in r["violations"])


def test_subcapability_of_non_core_violation():
    modules = _modules()
    modules["mystery"] = {"classification": "SUB_CAPABILITY",
                          "subcapability_of": "not_a_core"}
    r = minimal_governed_core_check(modules)
    assert r["aligned"] is False


def test_core_components_count():
    assert len(MINIMAL_GOVERNED_CORE) == 10
    labels = [label for _, label in MINIMAL_GOVERNED_CORE]
    assert "PIT Evidence" in labels
    assert "Append-only Ledger" in labels
