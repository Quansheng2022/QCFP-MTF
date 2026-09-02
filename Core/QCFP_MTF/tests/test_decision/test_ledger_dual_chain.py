# coding: utf-8
"""Ledger Global/Run 双链拆分测试（Convergence 新 6 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_ledger import verify_chain_records


def _chain_records():
    """Interleaved runs：R1-A, R2-B, R1-C, R3-D, R2-E。"""
    g = ["G1", "G2", "G3", "G4", "G5"]
    return [
        {"id": 1, "run_id": "R1", "prev_hash": "", "current_hash": g[0],
         "run_prev_hash": "", "run_current_hash": "R1-1"},
        {"id": 2, "run_id": "R2", "prev_hash": g[0], "current_hash": g[1],
         "run_prev_hash": "", "run_current_hash": "R2-1"},
        {"id": 3, "run_id": "R1", "prev_hash": g[1], "current_hash": g[2],
         "run_prev_hash": "R1-1", "run_current_hash": "R1-2"},
        {"id": 4, "run_id": "R3", "prev_hash": g[2], "current_hash": g[3],
         "run_prev_hash": "", "run_current_hash": "R3-1"},
        {"id": 5, "run_id": "R2", "prev_hash": g[3], "current_hash": g[4],
         "run_prev_hash": "R2-1", "run_current_hash": "R2-2"},
    ]


def test_interleaved_global_and_run_pass():
    records = _chain_records()
    g = verify_chain_records(records)
    assert g["global_verified"] is True
    for run in ("R1", "R2", "R3"):
        r = verify_chain_records(records, run_filter=run)
        assert r["run_verified"] is True


def test_tamper_r2_b_fails_global_and_run():
    records = _chain_records()
    records[1]["current_hash"] = "TAMPERED"   # R2-B 被篡改
    g = verify_chain_records(records)
    assert g["global_verified"] is False
    assert g["mismatch_location"][0]["location"] == "global,id=3"
    r2 = verify_chain_records(records, run_filter="R2")
    assert r2["run_verified"] is True          # run 链不受全局篡改影响


def test_run_tamper_fails_run_chain():
    records = _chain_records()
    records[4]["run_prev_hash"] = "WRONG"      # R2-E run_prev 被篡改
    r2 = verify_chain_records(records, run_filter="R2")
    assert r2["run_verified"] is False
    assert r2["mismatch_location"]
