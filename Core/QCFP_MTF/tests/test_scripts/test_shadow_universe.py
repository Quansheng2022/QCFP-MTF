# coding: utf-8
"""Daily Full-Universe Shadow Runner 测试（Runtime Evidence Wiring：第 3 项）"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.scripts.shadow_universe import (
    build_coverage, classify_terminal_state, run_universe_shadow,
    universe_symbols)
from QCFP_MTF.scripts.backfill_research_outcomes import (
    _horizon_days, compute_outcome)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE hk_stock_info (stock_code TEXT, "
                 "is_active INTEGER)")
    conn.execute("CREATE TABLE qcfp_mtf_decision (stock_code TEXT, "
                 "decision_date TEXT)")
    conn.execute("CREATE TABLE qcfp_decision_ledger (id INTEGER PRIMARY "
                 "KEY AUTOINCREMENT, stock_code TEXT, decision_date TEXT, "
                 "next_fsm_state TEXT, final_target REAL, status TEXT)")
    conn.execute("INSERT INTO hk_stock_info VALUES ('00700', 1)")
    conn.execute("INSERT INTO hk_stock_info VALUES ('01951', 1)")
    conn.execute("INSERT INTO qcfp_mtf_decision VALUES ('00700', "
                 "'2026-08-21')")
    return conn


def _full_conn():
    """完整 Schema（无决策行）→ 全部 ABSTAIN（evidence missing）。"""
    conn = _conn()
    for table in ("qcfp_quarterly_structural", "qcfp_monthly_behavior",
                  "qcfp_weekly_tactical", "qcfp_daily_tactical"):
        conn.execute(f"CREATE TABLE {table} (stock_code TEXT, "
                     "available_date TEXT, month_end TEXT, week_end TEXT, "
                     "trade_date TEXT)")
    return conn


def test_universe_symbols_union():
    """上游没有 decision row 的股票不能从 Universe 消失。"""
    conn = _conn()
    symbols = universe_symbols(conn, "2026-08-21")
    assert "00700" in symbols
    assert "01951" in symbols


def test_build_coverage_gate():
    outcomes = {"00700": {"state": "CERTIFIED"},
                "01951": {"state": "NO_TRADE"}}
    r = build_coverage(outcomes, ["00700", "01951"], date="2026-08-21")
    assert r["coverage_ok"] is True
    assert r["state_counts"]["CERTIFIED"] == 1
    assert r["state_counts"]["NO_TRADE"] == 1
    # 缺股票 → 硬门失败
    r2 = build_coverage({"00700": {"state": "NO_TRADE"}},
                        ["00700", "01951"])
    assert r2["coverage_ok"] is False
    assert r2["missing_stocks"] == ["01951"]


def test_classify_terminal_state():
    assert classify_terminal_state(None, 0.0) == "ABSTAIN"
    assert classify_terminal_state(object(), 0.0) == "NO_TRADE"
    assert classify_terminal_state(object(), 0.2) == "CERTIFIED"


def test_run_universe_shadow_missing_evidence_abstains():
    """Closure 4：证据缺失 → ABSTAIN，且必须持久化为 Ledger Fact；
    覆盖率仍 100%。"""
    conn = _full_conn()
    conn.execute("DELETE FROM qcfp_mtf_decision")   # 无任何决策行 → 纯证据缺失
    r = run_universe_shadow(conn, "2026-08-21", DEFAULT_SETTINGS,
                            run_id="test-shadow")
    assert r["universe_count"] == 2
    assert r["decision_count"] == 2
    assert r["missing_stocks"] == []
    assert r["duplicate_decisions"] == 0
    assert r["coverage_ok"] is True
    assert all(v["state"] == "ABSTAIN" for v in r["per_stock"].values())
    assert all(v["recorded"] for v in r["per_stock"].values())
    n_facts = conn.execute(
        "SELECT COUNT(*) FROM qcfp_shadow_decision_fact").fetchone()[0]
    assert n_facts == 2


def test_run_universe_shadow_system_failure_halted():
    """Closure 4：必需表不存在 / SQL 故障 → HALTED（schema broken），
    不是普通证据缺失；且必须持久化为 Ledger Fact。"""
    conn = _conn()   # 缺 qcfp_quarterly_structural 等表
    r = run_universe_shadow(conn, "2026-08-21", DEFAULT_SETTINGS,
                            run_id="test-halt")
    assert r["coverage_ok"] is True
    # 00700 有 decision row 但表缺失 → HALTED；01951 无 row → ABSTAIN
    assert r["per_stock"]["00700"]["state"] == "HALTED"
    assert r["per_stock"]["01951"]["state"] == "ABSTAIN"
    assert r["per_stock"]["00700"]["recorded"] is True
    n_facts = conn.execute(
        "SELECT COUNT(*) FROM qcfp_shadow_decision_fact").fetchone()[0]
    assert n_facts == 2


def test_classify_safe_mode():
    """Closure 4：SAFE_MODE 必须从 Snapshot 语义识别，不只是三态。"""
    class FakeSnap:
        def __init__(self, context):
            self.context = context
    assert classify_terminal_state(FakeSnap({"safety_status": "SAFE_MODE"}),
                                   0.0) == "SAFE_MODE"
    assert classify_terminal_state(FakeSnap({}), 0.2) == "CERTIFIED"


def test_horizon_and_compute_outcome():
    assert _horizon_days("5D") == 5
    assert _horizon_days("2W") == 14
    rows = [{"trade_date": "2026-08-24", "close": 10.0, "high": 10.2,
             "low": 9.9},
            {"trade_date": "2026-08-25", "close": 10.3, "high": 10.5,
             "low": 10.1},
            {"trade_date": "2026-08-26", "close": 10.1, "high": 10.4,
             "low": 9.8}]
    o = compute_outcome(rows, 3)
    assert o is not None
    assert o["future_return"] > 0
    assert o["evaluation_time"] == "2026-08-26"
    assert compute_outcome(rows, 10) is None
