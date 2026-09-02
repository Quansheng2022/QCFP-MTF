# coding: utf-8
"""Certification Scope 测试（92 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.certification_scope import certification_scope


def _scope():
    return {"component": "weekly_decision", "strategy_version": "v2.5",
            "config_hash": "cfg1", "dataset_snapshot": "ds-2026Q2",
            "universe": "HK", "time_range": "2021-01..2026-06",
            "market": "HK", "frequency": "weekly",
            "feature_manifest": "fm-abc"}


def test_scope_covered():
    r = certification_scope(_scope(), _scope())
    assert r["covers"] is True
    assert r["verdict"] == "CERTIFIED"
    assert r["mismatches"] == []


def test_market_mismatch_not_inherited():
    claim = _scope()
    claim["market"] = "US"
    r = certification_scope(_scope(), claim)
    assert r["covers"] is False
    assert r["verdict"] == "NOT_COVERED"
    assert r["mismatches"][0]["field"] == "market"


def test_frequency_mismatch_not_inherited():
    claim = _scope()
    claim["frequency"] = "intraday"
    r = certification_scope(_scope(), claim)
    assert r["verdict"] == "NOT_COVERED"
    assert any(m["field"] == "frequency" for m in r["mismatches"])
