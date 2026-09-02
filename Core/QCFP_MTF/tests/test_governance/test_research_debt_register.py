# coding: utf-8
"""Research Debt Register 测试（78 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.research_debt_register import RESEARCH_STATES, \
    research_debt_register


def _features():
    return {
        "feature_a": {"state": "VALIDATED", "cycles_in_state": 3},
        "feature_b": {"state": "EXPERIMENTAL", "cycles_in_state": 2},
        "feature_c": {"state": "EXPERIMENTAL", "cycles_in_state": 1},
        "feature_d": {"state": "HALF_FINISHED", "cycles_in_state": 9},
    }


def test_expired_experimental_flagged():
    r = research_debt_register(_features())
    assert "feature_b" in r["expired_experimental"]
    assert "feature_c" not in r["expired_experimental"]
    assert r["results"]["feature_b"]["action"] == "DELETE_ARCHIVE_REVIEW"


def test_invalid_state_normalized():
    r = research_debt_register(_features())
    assert r["results"]["feature_d"]["state"] == "HYPOTHESIS"


def test_states_whitelist():
    assert set(RESEARCH_STATES) == {"HYPOTHESIS", "EXPERIMENTAL",
                                    "VALIDATED", "REJECTED", "RETIRED"}
