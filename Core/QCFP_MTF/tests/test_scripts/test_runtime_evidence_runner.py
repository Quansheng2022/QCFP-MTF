# coding: utf-8
"""Daily Runtime Evidence Runner 测试（Closure 5）"""

import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.scripts.runtime_evidence_runner import (
    RUNNER_VERSION, _closure_check, _universe_hash,
    calibration_from_ledger, paper_eod_reconciliation_from_ledger,
    run_daily_replay)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE qcfp_runtime_event_ledger (event_seq INTEGER "
        "PRIMARY KEY AUTOINCREMENT, event_id TEXT, event_type TEXT, "
        "event_time TEXT, release_id TEXT, stock_code TEXT, "
        "broker_order_id TEXT, internal_position REAL, "
        "broker_position REAL, reconciliation_status TEXT, payload TEXT)")
    conn.execute(
        "CREATE TABLE qcfp_decision_ledger (id INTEGER PRIMARY KEY "
        "AUTOINCREMENT, stock_code TEXT, final_target REAL, release_id "
        "TEXT, decision_date TEXT, status TEXT)")
    return conn


def test_eod_reconciliation_from_ledger():
    """EOD 从 Runtime Event + Decision Ledger 两个独立事实集合计算。"""
    conn = _conn()
    conn.execute(
        "INSERT INTO qcfp_runtime_event_ledger (event_id, event_type, "
        "event_time, release_id, stock_code, broker_order_id, "
        "internal_position, broker_position) VALUES "
        "('E1','FILL','2026-08-29 10:00','REL-A','00700','B-1',0.2,0.2),"
        "('E2','FILL','2026-08-29 10:05','REL-A','01951','B-2',0.1,NULL)")
    conn.execute(
        "INSERT INTO qcfp_decision_ledger (stock_code, final_target, "
        "release_id, decision_date, status) VALUES "
        "('00700',0.2,'REL-A','2026-08-29','ACTIVE'),"
        "('01951',0.1,'REL-A','2026-08-29','ACTIVE')")
    r = paper_eod_reconciliation_from_ledger(conn, "REL-A", "2026-08-29")
    assert r["expected_reconciliations"] == 2
    assert r["actual_reconciliations"] == 2
    assert r["reconciliation_coverage"] == 1.0
    # 缺 broker_position → UNKNOWN（不能拿 internal 伪装一致）
    assert r["results"]["01951"]["status"] == "UNKNOWN"
    assert r["unresolved_unknown"] == 1


def test_calibration_from_ledger():
    conn = _conn()
    cal = {"calibration": {
        "estimated_slippage": 10.0, "realized_slippage": 12.0,
        "estimated_fill_ratio": 1.0, "realized_fill_ratio": 0.8,
        "estimated_exit_days": 1.0, "realized_exit_days": 2.0,
        "estimated_participation": 0.1, "realized_participation": 0.8}}
    conn.execute(
        "INSERT INTO qcfp_runtime_event_ledger (event_id, event_type, "
        "event_time, release_id, payload) VALUES "
        "('E1','FILL','2026-08-29','REL-A',?)",
        (json.dumps(cal),))
    r = calibration_from_ledger(conn, "REL-A", "2026-08-29")
    assert r["dimensions"]
    assert r["auto_param_modify_forbidden"] is True


def test_closure_check_full_universe():
    """P0-1：UniverseCount == Certified+NoTrade+Abstain+SafeMode+Halted。"""
    shadow = {"universe_count": 17,
              "state_counts": {"CERTIFIED": 1, "NO_TRADE": 15,
                               "ABSTAIN": 1, "SAFE_MODE": 0,
                               "HALTED": 0},
              "missing_stocks": [], "duplicate_decisions": 0}
    c = _closure_check(shadow)
    assert c["ok"] is True
    assert c["verdict"] == "SHADOW_COVERAGE_OK"
    assert c["terminal_count"] == 17


def test_closure_check_incomplete_when_terminal_missing():
    """ABSTAIN/SAFE_MODE/HALTED 未持久化 → 终态计数不闭合。"""
    shadow = {"universe_count": 17,
              "state_counts": {"CERTIFIED": 1, "NO_TRADE": 15},
              "missing_stocks": [], "duplicate_decisions": 0}
    c = _closure_check(shadow)
    assert c["ok"] is False
    assert c["verdict"] == "SHADOW_COVERAGE_INCOMPLETE"


def test_closure_check_duplicate_detected():
    shadow = {"universe_count": 17,
              "state_counts": {"CERTIFIED": 2, "NO_TRADE": 14,
                               "ABSTAIN": 1, "SAFE_MODE": 0,
                               "HALTED": 0},
              "missing_stocks": [], "duplicate_decisions": 1}
    c = _closure_check(shadow)
    assert c["ok"] is False
    assert c["duplicate_decisions"] == 1


def test_runner_identity_hash():
    h1 = _universe_hash(["00700", "01951", "00268"])
    h2 = _universe_hash(["00268", "01951", "00700"])
    assert h1 == h2
    assert RUNNER_VERSION


def test_replay_evidence_status_mapping():
    """P0-3：每日 Replay 只允许四种状态。"""
    from QCFP_MTF.scripts.minimal_trusted_release import \
        replay_evidence_status
    assert replay_evidence_status({}) == "REPLAY_NOT_PROVEN"
    assert replay_evidence_status({"error": "x"}) == "REPLAY_NOT_PROVEN"
    assert replay_evidence_status(
        {"n_current_release": 0}) == "REPLAY_NOT_PROVEN"
    ok = {"n_current_release": 16, "n_eligible": 16, "n_exact": 16,
          "n_mismatch": 0, "n_ineligible": 0, "n_replay_exception": 0,
          "eligible_rate": 1.0, "exact_rate": 1.0,
          "critical_mismatch": 0}
    assert replay_evidence_status(ok) == "REPLAY_PASS"
    assert replay_evidence_status({**ok, "n_ineligible": 1,
                                   "eligible_rate": 0.9375}) \
        == "REPLAY_NOT_PROVEN"
    assert replay_evidence_status({**ok, "n_exact": 15,
                                   "n_mismatch": 1,
                                   "exact_rate": 0.9375,
                                   "critical_mismatch": 1}) \
        == "REPLAY_MISMATCH"
    assert replay_evidence_status({**ok, "n_replay_exception": 1}) \
        == "REPLAY_EXCEPTION"


def test_daily_replay_real_date_passes():
    """P0-3 集成：真实 DB 2026-08-21 Current Release 全量重放 = PASS。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    r = run_daily_replay(conn, "2026-08-21", "MTR-CLOSURE-1",
                         dry_run=True)
    assert r["status"] == "REPLAY_PASS"
    assert r["n_exact"] == r["n_eligible"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_runtime_evidence_runner 全部通过 ✅")
