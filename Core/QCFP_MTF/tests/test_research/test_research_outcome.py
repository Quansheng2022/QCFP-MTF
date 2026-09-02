# coding: utf-8
"""Research Outcome 物理隔离测试（Sprint 2 + Runtime Evidence Wiring）"""

import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.research_outcome import (
    assert_outcome_production_isolated, ensure_research_outcome_table,
    outcome_ledger_append, research_outcome, validate_research_outcome)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_research_outcome_table(conn)
    conn.execute(
        "CREATE TABLE qcfp_decision_ledger (id INTEGER PRIMARY KEY "
        "AUTOINCREMENT, decision_id TEXT, run_id TEXT, stock_code TEXT, "
        "decision_date TEXT, context TEXT, status TEXT DEFAULT 'ACTIVE')")
    conn.execute(
        "INSERT INTO qcfp_decision_ledger (decision_id, run_id, "
        "stock_code, decision_date, context, status) VALUES (?,?,?,?,?,?)",
        ("d1", "RUN-1", "00700", "2026-08-21",
         json.dumps({"release_identity": {"release_id": "REL-A"}}),
         "ACTIVE"))
    return conn


def test_outcome_creation():
    o = research_outcome("d1", "REL-A", "00700", "2026-08-28",
                         "20D", future_return=0.38, mfe=0.40, mae=-0.03)
    assert o["future_aware"] is True
    assert o["research_only"] is True
    assert o["outcome_hash"]
    r = assert_outcome_production_isolated(o)
    assert r["production_isolated"] is True
    assert r["can_affect_current_decision"] is False


def test_missed_opportunity_flag():
    o = research_outcome("d2", "REL-A", "00700", "2026-08-28",
                         "20D", future_return=0.38,
                         missed_opportunity=True)
    assert o["missed_opportunity"] is True


def test_outcome_append_to_ledger():
    conn = _conn()
    o = research_outcome("d1", "REL-A", "00700", "2026-08-21", "20D",
                         mfe=0.1, mae=-0.02,
                         evaluation_time="2026-09-10",
                         horizon_end="2026-09-10",
                         source_data_snapshot_id="SNAP-1",
                         created_at="2026-09-11")
    assert outcome_ledger_append(conn, o) == 1
    # 同 outcome_id 幂等
    assert outcome_ledger_append(conn, o) == 0
    n = conn.execute(
        "SELECT COUNT(*) FROM qcfp_research_outcome").fetchone()[0]
    assert n == 1


def test_outcome_append_rejected_when_invalid():
    """第 4 项：缺 evaluation_time / source snapshot / hash 不匹配 /
    future_aware=False → OUTCOME_APPEND_REJECTED（不可绕过）。"""
    conn = _conn()
    o = research_outcome("d1", "REL-A", "00700", "2026-08-21", "20D",
                         mfe=0.1, mae=-0.02)
    v = validate_research_outcome(conn, o)
    assert v["valid"] is False
    assert "EVALUATION_NOT_AFTER_DECISION" in v["reasons"] or \
        "SOURCE_DATA_SNAPSHOT_REQUIRED" in v["reasons"]
    try:
        outcome_ledger_append(conn, o)
        raise AssertionError("invalid outcome 不应写入")
    except ValueError as exc:
        assert "OUTCOME_APPEND_REJECTED" in str(exc)
    assert conn.execute(
        "SELECT COUNT(*) FROM qcfp_research_outcome").fetchone()[0] == 0


def test_outcome_release_mismatch_rejected():
    conn = _conn()
    o = research_outcome("d1", "REL-WRONG", "00700", "2026-08-21", "20D",
                         evaluation_time="2026-09-10",
                         horizon_end="2026-09-10",
                         source_data_snapshot_id="SNAP-1")
    v = validate_research_outcome(conn, o)
    assert v["valid"] is False
    assert "RELEASE_ID_MISMATCH_WITH_DECISION" in v["reasons"]
