# coding: utf-8
"""Simplification Release Gate 测试（50 号：收尾/证明/减法）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.simplification_release import \
    release_verdict, simplification_ledger_entry, simplification_metrics, \
    simplification_release_check


def _before():
    return {
        "execution_paths": 120, "production_modules": 45,
        "decision_loc": 4200, "duplicate_rules": 18,
        "canonical_coverage": 0.82, "replay_coverage": 0.90,
        "invariant_coverage": 0.85,
    }


def _after():
    return {
        "execution_paths": 96, "production_modules": 40,
        "decision_loc": 3800, "duplicate_rules": 9,
        "canonical_coverage": 0.90, "replay_coverage": 0.95,
        "invariant_coverage": 0.92,
    }


def _validation(sharpe_after=0.84, replay=0.98):
    return {
        "oos_sharpe_before": 0.85, "oos_sharpe_after": sharpe_after,
        "ablation_delta": 0.01, "replay_match_ratio": replay,
    }


def test_simplification_metrics_down():
    m = simplification_metrics(_before(), _after())
    assert m["complexity_down"] is True
    assert m["coverage_not_down"] is True
    assert m["deltas"]["execution_paths"] < 0
    assert m["deltas"]["duplicate_rules"] < 0
    assert m["deltas"]["canonical_coverage"] > 0


def test_approved_when_proven():
    m = simplification_metrics(_before(), _after())
    c = simplification_release_check(m, _validation())
    assert c["verdict"] == "APPROVED"
    assert c["failures"] == []
    assert release_verdict(c) == "APPROVED"


def test_rejected_when_no_real_simplification():
    m = simplification_metrics(_before(), _before())
    c = simplification_release_check(m, _validation(sharpe_after=0.85))
    assert c["verdict"] == "REVIEW"
    assert release_verdict(c) == "REJECTED"


def test_review_when_oos_loss():
    m = simplification_metrics(_before(), _after())
    c = simplification_release_check(m, _validation(sharpe_after=0.60))
    assert c["verdict"] == "REVIEW"
    assert "oos_not_worse" in c["failures"]
    assert release_verdict(c) == "REVIEW"


def test_review_when_replay_not_preserved():
    m = simplification_metrics(_before(), _after())
    c = simplification_release_check(m, _validation(replay=0.90))
    assert "replay_preserved" in c["failures"]
    assert c["auto_approve_forbidden"] is True


def test_ledger_entry_immutable():
    entry = simplification_ledger_entry(
        "REL-50-001", _before(), _after(), _validation())
    assert entry["ledger_immutable"] is True
    assert entry["verdict"] == "APPROVED"
    assert entry["metrics"]["execution_paths_delta"] < 0
