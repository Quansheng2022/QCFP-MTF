# coding: utf-8
"""Certification Scope 子集测试（新 92 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.certification_scope import claim_within_certified


def _scope():
    return {"component": "weekly_decision", "strategy_version": "v2.5",
            "config_hash": "cfg1", "dataset_snapshot": "ds-2026Q2",
            "universe": "HK_LARGE_CAP", "time_range": "2021-01..2026-06",
            "market": "HK", "frequency": "weekly",
            "feature_manifest": "fm-abc"}


def test_claim_within_certified():
    r = claim_within_certified(_scope(), _scope())
    assert r["verdict"] == "CERTIFIED"
    assert r["claim_within_certified"] is True


def test_small_cap_claim_not_certified():
    claim = _scope()
    claim["universe"] = "HK_SMALL_CAP"
    r = claim_within_certified(_scope(), claim)
    assert r["verdict"] == "NOT_CERTIFIED"
    assert r["mismatches"][0]["field"] == "universe"


def test_daily_frequency_not_certified():
    claim = _scope()
    claim["frequency"] = "daily"
    r = claim_within_certified(_scope(), claim)
    assert r["verdict"] == "NOT_CERTIFIED"
