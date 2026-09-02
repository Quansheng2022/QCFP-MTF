# coding: utf-8
"""Production Simplicity KPI 测试（79 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.production_simplicity_kpi import SIMPLICITY_KPIS, \
    production_simplicity_kpi


def _current():
    return {"active_decision_modules": 40, "duplicate_authorities": 1,
            "decision_critical_parameters": 30, "canonical_path_length": 8,
            "report_decision_logic_count": 2,
            "legacy_production_imports": 1}


def test_improving_trend():
    prev = dict(_current())
    prev["active_decision_modules"] = 45
    prev["duplicate_authorities"] = 3
    r = production_simplicity_kpi(_current(), prev)
    assert r["overall_trend"] == "IMPROVING"
    assert r["kpis"]["active_decision_modules"]["direction"] == "DOWN"
    assert r["deltas"]["active_decision_modules"] == -5


def test_regressing_trend():
    prev = dict(_current())
    r = production_simplicity_kpi(
        {k: v + 5 for k, v in _current().items()}, prev)
    assert r["overall_trend"] == "REGRESSING"


def test_baseline_without_previous():
    r = production_simplicity_kpi(_current())
    assert r["overall_trend"] == "BASELINE"
    assert len(r["kpis"]) == len(SIMPLICITY_KPIS)


def test_stable_trend():
    r = production_simplicity_kpi(_current(), _current())
    assert r["overall_trend"] == "STABLE"
