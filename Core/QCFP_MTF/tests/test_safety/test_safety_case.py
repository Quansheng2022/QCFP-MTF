# coding: utf-8
"""System Safety Case 测试（99 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.safety_case import SAFETY_CLAIMS, safety_case_to_md, \
    system_safety_case


def _all_evidence():
    return {"permission_monotonicity": True, "risk_cap_respected": True,
            "pit_clean": True, "oos_reproducible": True,
            "ablation_complete": True, "version_matches": True}


def test_safety_case_pass():
    case = system_safety_case(_all_evidence())
    assert case["all_pass"] is True
    assert case["status"] == "SAFE_FOR_PRODUCTION"
    assert case["failed_claims"] == []


def test_safety_case_fail():
    ev = _all_evidence()
    ev["pit_clean"] = False
    case = system_safety_case(ev)
    assert case["status"] == "NOT_SAFE_FOR_PRODUCTION"
    assert "C3_pit_holds" in case["failed_claims"]


def test_claims_defined():
    assert len(SAFETY_CLAIMS) == 6
    assert "C1_permission_not_overridable" in SAFETY_CLAIMS


def test_safety_case_to_md():
    md = safety_case_to_md(system_safety_case(_all_evidence()))
    assert "System Safety Case" in md
    assert "SAFE_FOR_PRODUCTION" in md
