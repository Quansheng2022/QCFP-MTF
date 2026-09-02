# coding: utf-8
"""Override Outcome Review 季度汇总测试（新 62 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.override_outcome_review import \
    override_quarterly_review


def _records():
    return [
        {"class": "avoided_loss", "value_delta": 0.05},
        {"class": "avoided_loss", "value_delta": 0.03},
        {"class": "avoided_loss", "value_delta": 0.04},
        {"class": "missed_gain", "value_delta": -0.01},
    ]


def test_quarterly_review_net_value():
    r = override_quarterly_review(_records())
    assert r["override_count"] == 4
    assert r["counts"]["avoided_loss"] == 3
    assert r["net_override_value"] > 0
    assert r["verdict"] == "ADDING_VALUE"
    assert r["auto_permission_increase_forbidden"] is True
    assert r["evidence_store"] == "RESEARCH_EVIDENCE"


def test_noise_detected():
    r = override_quarterly_review([
        {"class": "wrong_intervention", "value_delta": -0.02},
        {"class": "wrong_intervention", "value_delta": -0.03},
        {"class": "wrong_intervention", "value_delta": -0.01}])
    assert r["verdict"] == "ADDING_NOISE"
