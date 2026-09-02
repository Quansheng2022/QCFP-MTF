# coding: utf-8
"""One-Page Canonical Architecture Contract 测试（新 99 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.one_page_canonical import architecture_contract_check


def test_mapped_to_stage_allowed():
    r = architecture_contract_check("PermissionModule", "PERMISSION")
    assert r["verdict"] == "PRODUCTION_MAPPED"
    assert r["production_allowed"] is True


def test_unmapped_research_only():
    r = architecture_contract_check("NewAlphaScore", "")
    assert r["verdict"] == "RESEARCH_ONLY"
    assert r["production_allowed"] is False


def test_explicit_non_production_stage():
    r = architecture_contract_check("ShadowTool", "SHADOW_ONLY")
    assert r["verdict"] == "SHADOW_ONLY"
    assert r["production_allowed"] is False
