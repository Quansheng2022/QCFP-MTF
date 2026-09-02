# coding: utf-8
"""Research/Production 隔离零容忍测试（新 88 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.research_production_leakage import \
    leakage_ci_zero_tolerance, research_only_nodes_reachable


def _nodes():
    return {
        "WaveSignal": {"research_only": False,
                       "reachable_from_production": True},
        "WaveOutcomeLabel": {"research_only": True,
                             "reachable_from_production": True},
        "future_mfe": {"research_only": True,
                       "reachable_from_production": False},
    }


def test_zero_tolerance_fail():
    r = leakage_ci_zero_tolerance(_nodes())
    assert r["ci_verdict"] == "FAIL"
    assert r["research_only_nodes_reachable_from_production"] == 1
    assert "WaveOutcomeLabel" in r["leaked_nodes"]


def test_reachable_research_only_list():
    assert research_only_nodes_reachable(_nodes()) == \
        ["WaveOutcomeLabel"]


def test_clean_passes():
    r = leakage_ci_zero_tolerance({
        "WaveSignal": {"research_only": False,
                       "reachable_from_production": True}})
    assert r["ci_verdict"] == "PASS"
