# coding: utf-8
"""Research-to-Production Leakage Test 测试（88 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.research_production_leakage import \
    RESEARCH_ONLY_OBJECTS, research_production_leakage, tag_research_only


def _nodes():
    return {
        "WaveSignal": {"research_only": False,
                       "in_production_graph": True},
        "WaveOutcomeLabel": {"research_only": True,
                             "in_production_graph": True},
        "future_mfe": {"research_only": True,
                       "in_production_graph": False},
        "diagnostic_score": {"research_only": True,
                             "in_production_graph": True},
    }


def test_leakage_detected():
    r = research_production_leakage(_nodes())
    assert "WaveOutcomeLabel" in r["leaked_nodes"]
    assert "diagnostic_score" in r["leaked_nodes"]
    assert "future_mfe" not in r["leaked_nodes"]
    assert r["leakage_count"] == 2
    assert r["ci_verdict"] == "FAIL"


def test_clean_graph_passes():
    nodes = {n: {"research_only": False,
                 "in_production_graph": True}
             for n in ("WaveSignal", "Permission", "Governance")}
    r = research_production_leakage(nodes)
    assert r["leakage_count"] == 0
    assert r["ci_verdict"] == "PASS"


def test_research_only_objects_registered():
    assert "WaveOutcomeLabel" in RESEARCH_ONLY_OBJECTS
    assert "shadow_alpha" in RESEARCH_ONLY_OBJECTS
    t = tag_research_only("future_mae")
    assert t["research_only"] is True
    assert t["production_allowed"] is False
