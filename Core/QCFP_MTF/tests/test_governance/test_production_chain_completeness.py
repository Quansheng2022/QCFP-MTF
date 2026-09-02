# coding: utf-8
"""Minimal Governed Core 十阶段链测试（新 90 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.minimal_governed_core import MINIMAL_GOVERNED_CORE, \
    production_chain_completeness, remap_to_core


def _full_chain():
    return [k for k, _ in MINIMAL_GOVERNED_CORE]


def test_single_authority_chain():
    r = production_chain_completeness(_full_chain())
    assert r["complete"] is True
    assert r["single_authority_chain"] is True
    assert r["verdict"] == "SINGLE_CHAIN"


def test_second_authority_chain_detected():
    r = production_chain_completeness(_full_chain() + ["ExtraAuthority"])
    assert r["verdict"] == "SECOND_AUTHORITY_CHAIN_DETECTED"
    assert "ExtraAuthority" in r["extra_non_core_stages"]


def test_incomplete_chain():
    r = production_chain_completeness(_full_chain()[:5])
    assert r["verdict"] == "INCOMPLETE"
    assert len(r["missing"]) == 5


def test_remap_to_core():
    r = remap_to_core({
        "pit_evidence": {},
        "binding_constraint_trace": {"subcapability_of":
                                     "canonical_final_target"},
        "orphan_module": {},
        "proven_module": {"necessity_proven": True}})
    assert r["remapped"]["pit_evidence"] == "CORE"
    assert r["remapped"]["binding_constraint_trace"] == \
        "SUB_CAPABILITY_OF_canonical_final_target"
    assert "orphan_module" in r["downgraded"]
