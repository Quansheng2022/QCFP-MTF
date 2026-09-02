# coding: utf-8
"""Governance Minimalism 组件判定测试（新 98 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.governance_minimalism import \
    governance_certificate_consolidation, governance_component_verdict


def test_keep_with_independent_value():
    r = governance_component_verdict("Ledger", duplicated_by=None,
                                     independent_value=0.1)
    assert r["verdict"] == "KEEP"


def test_merge_duplicate_no_value():
    r = governance_component_verdict("Cert2", duplicated_by="Cert1",
                                     independent_value=0.0)
    assert r["verdict"] == "MERGE"


def test_drop_no_value():
    r = governance_component_verdict("OrphanGate", independent_value=0.0)
    assert r["verdict"] == "DROP"


def test_certificate_consolidation():
    r = governance_certificate_consolidation(
        ["Validation", "Reactivation", "Release", "Acceptance"])
    assert r["verdict"] == "CONSOLIDATE_SCHEMA"
    r2 = governance_certificate_consolidation(["Validation"])
    assert r2["verdict"] == "MINIMAL"
