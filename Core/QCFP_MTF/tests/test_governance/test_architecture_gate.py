# coding: utf-8
"""Architecture Conformance Gate 测试（新 20 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.architecture_conformance import \
    FORBIDDEN_IMPORT_EDGES, architecture_conformance_gate


def test_clean_edges_pass():
    r = architecture_conformance_gate([
        ("report", "contract"),
        ("production", "WaveSignal"),
        ("research", "canonical_replay")])
    assert r["ci_verdict"] == "PASS"
    assert r["blocked"] is False


def test_forbidden_edges_fail():
    r = architecture_conformance_gate([
        ("report", "position_sizing"),
        ("production", "WaveOutcomeLabel")])
    assert r["ci_verdict"] == "FAIL"
    assert r["blocked"] is True
    assert len(r["violations"]) == 2


def test_forbidden_edges_defined():
    assert ("report", "position_sizing") in FORBIDDEN_IMPORT_EDGES
    assert ("execution", "uncertified_decision") in \
        FORBIDDEN_IMPORT_EDGES
