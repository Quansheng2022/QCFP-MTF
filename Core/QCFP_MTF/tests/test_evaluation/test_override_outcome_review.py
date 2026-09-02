# coding: utf-8
"""Override Outcome Review 测试（62 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.override_outcome_review import \
    override_outcome_review, override_value_verdict


def _records():
    return [
        {"class": "avoided_loss", "canonical_return": -0.08,
         "actual_return": -0.02},
        {"class": "avoided_loss", "canonical_return": -0.05,
         "actual_return": 0.00},
        {"class": "avoided_loss", "canonical_return": -0.12,
         "actual_return": -0.03},
        {"class": "missed_gain", "canonical_return": 0.10,
         "actual_return": 0.02},
    ]


def test_review_counts_and_delta():
    r = override_outcome_review(_records())
    assert r["counts"]["avoided_loss"] == 3
    assert r["counts"]["missed_gain"] == 1
    assert r["total_overrides"] == 4
    assert r["mean_actual_minus_canonical"] is not None
    assert r["auto_production_modify_forbidden"] is True


def test_helpful_verdict():
    r = override_outcome_review(_records())
    v = override_value_verdict(r)
    assert v["verdict"] == "HELPFUL"


def test_harmful_verdict():
    records = [{"class": "wrong_intervention"},
               {"class": "wrong_intervention"},
               {"class": "premature_exit"},
               {"class": "avoided_loss"}]
    r = override_outcome_review(records)
    v = override_value_verdict(r)
    assert v["verdict"] == "HARMFUL"


def test_inconclusive_when_no_samples():
    r = override_outcome_review([])
    assert override_value_verdict(r)["verdict"] == "INCONCLUSIVE"
