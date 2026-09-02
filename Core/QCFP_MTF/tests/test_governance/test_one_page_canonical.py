# coding: utf-8
"""One-Page Canonical Specification 测试（99 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.one_page_canonical import AUTHORITY_ROLES, \
    canonical_chain_completeness, one_page_canonical_spec


def test_spec_one_page():
    s = one_page_canonical_spec()
    assert len(s["stages"]) == 8
    assert s["stages"]["INPUT"] == "PIT Evidence"
    assert s["stages"]["FACT"] == "Ledger"


def test_authority_roles():
    assert "仅 Governance" in AUTHORITY_ROLES["can_increase_risk"]
    assert AUTHORITY_ROLES["produces_decision"] == "Governance（唯一）"
    assert "Append-only Ledger" in AUTHORITY_ROLES["saves_fact"]


def test_chain_complete():
    r = canonical_chain_completeness(
        ["INPUT", "PERMISSION", "OPPORTUNITY", "LIFECYCLE",
         "GOVERNANCE", "OUTPUT", "FACT", "VALIDATION"])
    assert r["complete"] is True
    assert r["verdict"] == "COMPLETE"


def test_chain_missing():
    r = canonical_chain_completeness(["INPUT", "PERMISSION"])
    assert r["complete"] is False
    assert "FACT" in r["missing"]
    assert r["verdict"] == "SIMPLIFY_OR_FIX"
