# coding: utf-8
"""Research Debt 实验功能老化报告测试（新 78 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.research_debt_register import \
    experimental_feature_aging_report


def _features():
    return {
        "A": {"state": "EXPERIMENTAL", "cycles_in_state": 1},
        "B": {"state": "EXPERIMENTAL", "cycles_in_state": 3},
        "C": {"state": "VALIDATED", "cycles_in_state": 2},
        "D": {"state": "RETIRED", "cycles_in_state": 5},
    }


def test_aging_report_actions():
    r = experimental_feature_aging_report(_features())
    assert r["report"]["A"]["action"] == "KEEP_EXPERIMENTAL"
    assert r["report"]["B"]["action"] == "DELETE_REVIEW"
    assert r["report"]["C"]["action"] == "VALIDATED"
    assert r["report"]["D"]["action"] == "RETIRED"
    assert r["delete_review"] == ["B"]


def test_oos_failure_rejected():
    r = experimental_feature_aging_report(
        {"A": {"state": "EXPERIMENTAL", "cycles_in_state": 1}},
        oos_results={"A": False})
    assert r["report"]["A"]["action"] == "REJECTED"
