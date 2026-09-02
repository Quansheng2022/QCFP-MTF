# coding: utf-8
"""Zero-Trust Certification 测试（P0-4 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.zero_trust import HARD_GATES, zero_trust_certification


def _gates():
    return {g: True for g in HARD_GATES}


def test_all_hard_gates_pass():
    r = zero_trust_certification(_gates(),
                                 {"data_quality": 85, "retail": 70})
    assert r["certified"] is True
    assert r["status"] == "CERTIFIED"
    assert r["quality_score"] == 77.5


def test_single_hard_gate_fail_blocks():
    gates = _gates()
    gates["C3_pit"] = False
    r = zero_trust_certification(gates, {"data_quality": 95})
    assert r["certified"] is False
    assert r["status"] == "NOT_CERTIFIED"
    assert "C3_pit" in r["failed_hard_gates"]
    assert r["quality_score"] == 0.0


def test_hard_gates_constant():
    assert HARD_GATES == ("C1_permission", "C2_risk", "C3_pit",
                          "C4_replay", "C5_oos", "C6_version")
