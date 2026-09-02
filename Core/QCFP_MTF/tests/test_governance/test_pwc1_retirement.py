# coding: utf-8
"""PWC-1 Retirement Table + 验收矩阵测试（PWC-1 第 10 项）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.convergence_release import PWC1_ACCEPTANCE_QUESTIONS, \
    pwc1_acceptance_matrix, retirement_table


def _modules():
    return {
        "canonical_engine": {"production_imported": True,
                             "formal_research_imported": True,
                             "unique_authority": True,
                             "marginal_value": 1.0},
        "legacy_action_generator": {"production_imported": False,
                                    "formal_research_imported": False,
                                    "unique_authority": False,
                                    "marginal_value": 0.0},
        "old_wave_stage": {"production_imported": False,
                           "formal_research_imported": True,
                           "unique_authority": False,
                           "marginal_value": 0.01},
        "duplicate_report_logic": {"production_imported": False,
                                   "formal_research_imported": False,
                                   "unique_authority": False,
                                   "marginal_value": 0.0},
    }


def test_retirement_table():
    r = retirement_table(_modules())
    assert r["retirements"]["canonical_engine"]["decision"] == "KEEP"
    assert r["retirements"]["legacy_action_generator"]["decision"] == "DELETE"
    assert r["retirements"]["old_wave_stage"]["decision"] == "RESEARCH_ONLY"
    assert r["retirements"]["duplicate_report_logic"]["decision"] == "DELETE"
    assert set(r["delete"]) == {"legacy_action_generator",
                                "duplicate_report_logic"}


def test_merge_non_authority():
    r = retirement_table({
        "dup": {"production_imported": True, "formal_research_imported": False,
                "unique_authority": False, "marginal_value": 0.0}})
    assert r["retirements"]["dup"]["decision"] == "MERGE"


def test_pwc1_matrix_pass():
    checks = {q: True for q in PWC1_ACCEPTANCE_QUESTIONS}
    r = pwc1_acceptance_matrix(checks)
    assert r["verdict"] == "PWC1_PASS"
    assert r["failures"] == []


def test_pwc1_matrix_blocked():
    checks = {q: True for q in PWC1_ACCEPTANCE_QUESTIONS}
    checks["critical_data_missing_cannot_pass"] = False
    r = pwc1_acceptance_matrix(checks)
    assert r["verdict"] == "PWC1_BLOCKED"
    assert r["failures"] == ["critical_data_missing_cannot_pass"]
