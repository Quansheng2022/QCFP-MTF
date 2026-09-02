# coding: utf-8
"""ValidationCertificate 唯一权威测试（新 11 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.validation_certificate import \
    certificate_display, research_validated_from_summary, \
    validation_certificate


def _valid_summary():
    return {
        "overall": {"sharpe": 0.8},
        "run_status": {"status": "PASS", "pit_grade": "B"},
        "rolling_oos_evaluation": [{"sharpe": 0.2}, {"sharpe": 0.3}],
        "ablation_ok": True, "cost_stress_ok": True,
        "execution_stress_ok": True, "regime_robustness_ok": True,
        "replay_ok": True, "shadow_ok": True,
    }


def test_validated_only_from_certificate():
    r = research_validated_from_summary(_valid_summary())
    assert r["display_status"] == "RESEARCH VALIDATED"
    assert r["certificate"]["overall_status"] == "CERTIFIED"


def test_missing_evidence_unknown_not_validated():
    s = _valid_summary()
    del s["replay_ok"]
    r = research_validated_from_summary(s)
    assert r["display_status"] == "UNKNOWN"
    assert "RESEARCH VALIDATED" not in r["display_status"]


def test_fail_closed_on_negative_oos():
    s = _valid_summary()
    s["rolling_oos_evaluation"] = [{"sharpe": -0.2}]
    r = research_validated_from_summary(s)
    assert r["display_status"] == "NOT CERTIFIED"


def test_certificate_display_no_certificate_unknown():
    assert certificate_display(None) == "UNKNOWN"
    c = validation_certificate({g: None for g in
                                ("pit", "oos", "ablation")})
    assert certificate_display(c) == "UNKNOWN"
