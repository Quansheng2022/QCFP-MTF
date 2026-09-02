# coding: utf-8
"""Evidence Accumulation 测试（P0-1/2/3/5）"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.evidence_freeze_contract import (
    build_freeze_contract, freeze_id, window_identity_break)
from QCFP_MTF.monitoring.evidence_daily_gate import (
    evaluate_daily_evidence_gate, verify_evidence_hash)
from QCFP_MTF.monitoring.replay_accumulation import (
    evaluate_replay_accumulation, replay_accumulation_stats)
from QCFP_MTF.monitoring.runtime_evidence_store import (
    rolling_windows_summary)


def _artifact(verdict="DECISION_SUPPORT_EVIDENCE_READY", coverage=1.0):
    import hashlib
    import json
    art = {
        "verdict": verdict, "evidence_hash": "H-1",
        "evidence": {
            "decision": {"expected_decisions": 16,
                         "actual_decisions": 16, "coverage": coverage,
                         "pit_violations": 0, "permission_violations": 0,
                         "uncertified_executions": 0,
                         "safe_mode_count": 0, "halted_count": 0},
            "replay": {"replay_total": 16, "replay_eligible": 16,
                       "replay_exact": 16, "critical_replay_mismatch": 0,
                       "replay_status": "REPLAY_PASS"},
            "outcome": {"outcome_count": 16, "outcome_coverage": 1.0,
                        "outcome_maturity_5d": 16,
                        "outcome_maturity_20d": 16,
                        "outcome_maturity_60d": 16},
            "stability": {"decision_flip_rate": 0.1,
                          "duplicate_decisions": 0},
        },
        "ledger_bindings": {},
    }
    raw = json.dumps({"evidence": art["evidence"],
                      "ledger_bindings": art["ledger_bindings"]},
                     sort_keys=True, ensure_ascii=False, default=str)
    art["evidence_hash"] = hashlib.sha256(
        raw.encode("utf-8")).hexdigest()[:16]
    return art


def test_freeze_contract_identity_and_break():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    settings = {"a": 1}
    c1 = build_freeze_contract(conn, settings, release_id="REL-A",
                               window_start="2026-08-21",
                               runner_version="r1",
                               universe_hash="U", dataset_contract_hash="D")
    assert c1["evidence_freeze_id"]
    c2 = build_freeze_contract(conn, settings, release_id="REL-A",
                               window_start="2026-08-21",
                               runner_version="r1",
                               universe_hash="U", dataset_contract_hash="D")
    assert freeze_id(c1) == freeze_id(c2)
    breaks = window_identity_break(c1, {**c2, "config_hash": "CHANGED"})
    assert "config_hash" in breaks
    assert window_identity_break(c1, c2) == []
    conn.close()


def test_daily_gate_ready_and_incomplete():
    art = _artifact()
    from QCFP_MTF.governance.evidence_freeze_contract import \
        build_freeze_contract
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    freeze = build_freeze_contract(conn, {"a": 1}, release_id="REL-A",
                                   window_start="2026-08-21",
                                   runner_version="r1",
                                   universe_hash="U",
                                   dataset_contract_hash="D")
    conn.close()
    r = evaluate_daily_evidence_gate(
        art, replay={"replay_eligible": 16, "replay_exact": 16,
                     "critical_replay_mismatch": 0},
        outcome_backfill={"errors": 0},
        persisted={"evidence_id": "E1"},
        freeze_contract=freeze, day_identity=freeze)
    assert r["state"] == "DAILY_EVIDENCE_READY"
    assert r["qualified"] is True
    # Replay 缺失 → INCOMPLETE（不是 PASS）
    r2 = evaluate_daily_evidence_gate(
        art, replay=None, outcome_backfill={"errors": 0})
    assert r2["state"] == "DAILY_EVIDENCE_INCOMPLETE"
    assert r2["qualified"] is False


def test_daily_gate_invalid_on_identity_break():
    art = _artifact()
    from QCFP_MTF.governance.evidence_freeze_contract import \
        build_freeze_contract
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    freeze = build_freeze_contract(conn, {"a": 1}, release_id="REL-A",
                                   window_start="2026-08-21",
                                   runner_version="r1",
                                   universe_hash="U",
                                   dataset_contract_hash="D")
    conn.close()
    day_identity = dict(freeze)
    day_identity["config_hash"] = "CHANGED"
    r = evaluate_daily_evidence_gate(
        art, replay={"replay_eligible": 16, "replay_exact": 16,
                     "critical_replay_mismatch": 0},
        outcome_backfill={"errors": 0},
        persisted={"evidence_id": "E1"},
        freeze_contract=freeze, day_identity=day_identity)
    assert r["state"] == "DAILY_EVIDENCE_INVALID"
    assert any("EVIDENCE_WINDOW_IDENTITY_BREAK" in x
               for x in r["invalid_reasons"])


def test_verify_evidence_hash_roundtrip():
    import hashlib
    import json
    art = _artifact()
    raw = json.dumps({"evidence": art["evidence"],
                      "ledger_bindings": art["ledger_bindings"]},
                     sort_keys=True, ensure_ascii=False, default=str)
    art["evidence_hash"] = hashlib.sha256(
        raw.encode("utf-8")).hexdigest()[:16]
    assert verify_evidence_hash(art) is True


def test_replay_accumulation_gap_and_drift():
    rows = [
        {"trade_date": "2026-08-01", "status": "",
         "replay_eligible": 16, "replay_exact": 16,
         "critical_replay_mismatch": 0, "n_ineligible": 0,
         "n_replay_exception": 0, "actual_decisions": 16},
        {"trade_date": "2026-08-04", "status": "",
         "replay_eligible": 0, "replay_exact": 0,
         "critical_replay_mismatch": 0, "n_ineligible": 0,
         "n_replay_exception": 0, "actual_decisions": 16},
    ]
    r = evaluate_replay_accumulation(rows)
    assert r["state"] == "REPLAY_GAP"
    assert r["stats"]["replay_gap_days"] == ["2026-08-04"]
    rows2 = [{"trade_date": "2026-08-01", "status": "",
              "replay_eligible": 16, "replay_exact": 16,
              "critical_replay_mismatch": 0, "n_ineligible": 0,
              "n_replay_exception": 0, "actual_decisions": 16}]
    assert evaluate_replay_accumulation(rows2)["state"] == \
        "REPLAY_ACCUMULATION_OK"


def test_rolling_windows_supported():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE qcfp_runtime_evidence_daily (evidence_id TEXT, "
        "release_id TEXT, execution_mode TEXT, trade_date TEXT, "
        "status TEXT, verdict TEXT, evidence_hash TEXT, coverage REAL, "
        "replay_eligible INTEGER, replay_exact INTEGER, "
        "critical_replay_mismatch INTEGER, permission_violations INTEGER, "
        "pit_violations INTEGER, uncertified_executions INTEGER, "
        "outcome_coverage REAL, outcome_maturity_5d INTEGER)")
    for i in range(1, 25):
        conn.execute(
            "INSERT INTO qcfp_runtime_evidence_daily VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"E{i}", "REL-A", "SHADOW", f"2026-08-{i:02d}", "",
             "EVIDENCE_READY", "H", 1.0, 16, 16, 0, 0, 0, 0, 1.0, 16))
    rows = conn.execute(
        "SELECT * FROM qcfp_runtime_evidence_daily ORDER BY trade_date"
    ).fetchall()
    w = rolling_windows_summary([dict(r) for r in rows])
    assert w["5d"]["qualified_days"] == 5
    assert w["20d"]["qualified_days"] == 20
    assert w["60d"]["qualified_days"] == 24
    assert w["120d"]["qualified_days"] == 24
    conn.close()
