# coding: utf-8
"""Runtime Schema Migration 测试（C1）"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.paths import get_qcfp_dir
from QCFP_MTF.scripts.runtime_schema_migration import (
    RUNTIME_KEY_COLUMNS, RUNTIME_TABLES, capture_schema,
    migration_plan, parse_expected_from_sql, verify_schema)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_expected_schema_parsed_from_sql():
    expected = parse_expected_from_sql(
        get_qcfp_dir() / "sql" / "create_qcfp_tables.sql")
    for t in RUNTIME_TABLES:
        assert t in expected, t
        assert "decision_id" in expected["qcfp_decision_ledger"]
        assert "event_id" in expected["qcfp_runtime_event_ledger"]
        assert "evidence_id" in expected["qcfp_runtime_evidence_daily"]


def test_migration_plan_and_verify():
    conn = _conn()
    before = capture_schema(conn)
    expected = parse_expected_from_sql(
        get_qcfp_dir() / "sql" / "create_qcfp_tables.sql")
    plan = migration_plan(before, expected)
    assert set(plan["tables_to_create"]) == set(RUNTIME_TABLES)
    # 应用核心 runtime DDL 后验证
    from QCFP_MTF.execution.runtime_event_ledger import \
        ensure_runtime_event_table
    from QCFP_MTF.monitoring.runtime_evidence_store import \
        ensure_runtime_evidence_daily_table
    from QCFP_MTF.research.research_outcome import \
        ensure_research_outcome_table
    conn.execute(
        "CREATE TABLE qcfp_decision_ledger (id INTEGER PRIMARY KEY, "
        "decision_id TEXT, stock_code TEXT, decision_date TEXT, "
        "context TEXT, status TEXT)")
    ensure_runtime_event_table(conn)
    ensure_runtime_evidence_daily_table(conn)
    ensure_research_outcome_table(conn)
    conn.execute(
        "CREATE TABLE qcfp_shadow_decision_fact (fact_id TEXT PRIMARY "
        "KEY, stock_code TEXT, decision_date TEXT, terminal_state TEXT)")
    conn.execute(
        "CREATE TABLE qcfp_decision_certificate (certificate_id TEXT "
        "PRIMARY KEY, decision_id TEXT, release_id TEXT)")
    conn.execute(
        "CREATE TABLE qcfp_model_registry (settings_hash TEXT, "
        "settings_blob TEXT, model_version TEXT, rule_version TEXT)")
    v = verify_schema(conn, expected)
    # mini fixture 只保证关键列齐全（全量列校验由真实 migration 承担）
    assert all(v["tables"][t]["missing_key_columns"] == []
               for t in RUNTIME_TABLES)
    # 缺关键列 → 不 ok
    conn.execute("ALTER TABLE qcfp_decision_certificate "
                 "DROP COLUMN release_id")
    v2 = verify_schema(conn, expected)
    assert v2["tables"]["qcfp_decision_certificate"][
        "missing_key_columns"] == ["release_id"]


def test_key_columns_defined_for_all_runtime_tables():
    for t in RUNTIME_TABLES:
        assert RUNTIME_KEY_COLUMNS[t], t
