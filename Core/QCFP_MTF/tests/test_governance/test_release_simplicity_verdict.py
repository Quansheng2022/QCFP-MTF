# coding: utf-8
"""Production Simplicity KPI Release 判定测试（新 79 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.production_simplicity_kpi import \
    release_simplicity_verdict


def _prev():
    return {"active_decision_modules": 31, "duplicate_authorities": 4,
            "decision_critical_parameters": 47, "canonical_path_length": 12,
            "report_decision_logic_count": 6,
            "legacy_production_imports": 11}


def _cur():
    return {"active_decision_modules": 24, "duplicate_authorities": 0,
            "decision_critical_parameters": 32, "canonical_path_length": 9,
            "report_decision_logic_count": 0,
            "legacy_production_imports": 0}


def test_simplify_required_when_complexity_up_no_improvement():
    prev = _prev()
    cur = dict(_prev())
    cur["active_decision_modules"] = 45
    r = release_simplicity_verdict(prev, cur)
    assert r["verdict"] == "SIMPLIFY_REQUIRED"
    assert r["simplify"] is True


def test_ok_when_improving():
    r = release_simplicity_verdict(_prev(), _cur())
    assert r["verdict"] == "OK"


def test_complexity_up_but_improvements_ok():
    prev = _prev()
    cur = dict(_prev())
    cur["active_decision_modules"] = 45
    r = release_simplicity_verdict(prev, cur, oos_improved=True)
    assert r["verdict"] == "OK"
