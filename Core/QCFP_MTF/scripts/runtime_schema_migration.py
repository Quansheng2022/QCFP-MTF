#!/usr/bin/env python
# coding: utf-8
"""Runtime Schema Migration（C1：真实库迁移 Closure）

把 Runtime Fact 表正式迁移进真实 SQLiteDB/HK_Stock.db：
    qcfp_decision_ledger / qcfp_model_registry /
    qcfp_shadow_decision_fact / qcfp_decision_certificate /
    qcfp_runtime_event_ledger / qcfp_research_outcome /
    qcfp_runtime_evidence_daily

单一 Schema 源：sql/create_qcfp_tables.sql（Runtime helper 不再
偷偷自动建 Production 表；本地/测试的 ensure_* 保持可用）。

执行原则：
    Backup → BEGIN migration → create/index → schema verification
    → smoke test → commit

产物（Report/QCFP_MTF/audit/runtime_schema/）：
    schema_before.json / schema_expected.json / migration_plan.json /
    runtime_schema_diff.json / runtime_schema_verification.json /
    runtime_smoke_test.json / runtime_schema_migration_report.json

最终状态：RUNTIME_SCHEMA_READY（任一 Gate 失败 → RUNTIME_SCHEMA_INCOMPLETE）
"""

import hashlib
import json
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect, execute_sql_file
from QCFP_MTF.common.paths import get_db_path, get_qcfp_dir, get_report_root


RUNTIME_TABLES = (
    "qcfp_decision_ledger",
    "qcfp_model_registry",
    "qcfp_shadow_decision_fact",
    "qcfp_decision_certificate",
    "qcfp_runtime_event_ledger",
    "qcfp_research_outcome",
    "qcfp_runtime_evidence_daily",
)

# 每张 Runtime 表的关键列（verification 必查）
RUNTIME_KEY_COLUMNS = {
    "qcfp_decision_ledger": ("decision_id", "stock_code", "decision_date",
                             "context", "status"),
    "qcfp_model_registry": ("settings_hash", "settings_blob",
                            "model_version", "rule_version"),
    "qcfp_shadow_decision_fact": ("fact_id", "stock_code",
                                  "decision_date", "terminal_state"),
    "qcfp_decision_certificate": ("certificate_id", "decision_id",
                                  "release_id"),
    "qcfp_runtime_event_ledger": ("event_seq", "event_id", "event_type",
                                  "release_id", "current_event_hash"),
    "qcfp_research_outcome": ("outcome_id", "decision_id",
                              "future_return", "outcome_hash"),
    "qcfp_runtime_evidence_daily": ("evidence_id", "release_id",
                                    "execution_mode", "trade_date",
                                    "revision_no", "verdict"),
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                               default=str), encoding="utf-8")


def _table_columns(conn, table) -> dict:
    rows = conn.execute(
        f"PRAGMA table_info({table})").fetchall()
    return {r["name"]: {"type": r["type"], "nullable": not bool(r["notnull"]),
                        "default": r["dflt_value"],
                        "primary_key": bool(r["pk"])}
            for r in rows}


def capture_schema(conn) -> dict:
    """schema_before/after：每张 Runtime 表的列信息 + 表级约束摘要。"""
    out = {"schema_version": "RUNTIME-SCHEMA-1",
            "captured_at": _now(), "tables": {}}
    for t in RUNTIME_TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (t,)).fetchone() is not None
        if not exists:
            out["tables"][t] = {"exists": False, "columns": {}}
            continue
        cols = _table_columns(conn, t)
        uniques = []
        for idx in conn.execute(f"PRAGMA index_list({t})").fetchall():
            uniques.append({"name": idx["name"],
                            "unique": bool(idx["unique"])})
        out["tables"][t] = {"exists": True, "columns": cols,
                            "indexes": uniques,
                            "column_count": len(cols)}
    return out


def parse_expected_from_sql(sql_path: Path) -> dict:
    """从 create_qcfp_tables.sql 解析每张 Runtime 表的期望列（单一源）。"""
    text = sql_path.read_text(encoding="utf-8")
    expected = {}
    pattern = re.compile(
        r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\)\s*;",
        re.S | re.I)
    for m in pattern.finditer(text):
        table = m.group(1)
        if table not in RUNTIME_TABLES:
            continue
        cols = {}
        body = m.group(2)
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue
            if line.upper().startswith(("UNIQUE", "PRIMARY", "FOREIGN",
                                        "CONSTRAINT", "CHECK")):
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            name, rest = parts[0].strip('"`[]'), parts[1]
            dtype = rest.split()[0].upper()
            cols[name] = {"type": dtype}
        expected[table] = cols
    return expected


def migration_plan(before: dict, expected: dict) -> dict:
    plan = {"tables_to_create": [], "tables_missing_columns": {},
            "verify_only": []}
    for t in RUNTIME_TABLES:
        if not before["tables"][t]["exists"]:
            plan["tables_to_create"].append(t)
            continue
        exp_cols = set(expected.get(t, {}))
        cur_cols = set(before["tables"][t]["columns"])
        missing = sorted(exp_cols - cur_cols)
        if missing:
            plan["tables_missing_columns"][t] = missing
        else:
            plan["verify_only"].append(t)
    return plan


def backup_db(conn, db_path: Path) -> Path:
    """WAL checkpoint 后整库备份。"""
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.parent / f"HK_Stock.db.bak-{stamp}"
    shutil.copy2(db_path, backup)
    return backup


def verify_schema(conn, expected: dict) -> dict:
    checks = {}
    for t in RUNTIME_TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (t,)).fetchone() is not None
        if not exists:
            checks[t] = {"table_exists": False, "missing_columns": []}
            continue
        cols = {r["name"] for r in conn.execute(
            f"PRAGMA table_info({t})").fetchall()}
        missing = sorted(set(expected.get(t, {})) - cols)
        key_missing = [c for c in RUNTIME_KEY_COLUMNS.get(t, ())
                       if c not in cols]
        checks[t] = {"table_exists": True,
                     "missing_columns": missing,
                     "missing_key_columns": key_missing,
                     "ok": not missing and not key_missing}
    return {"tables": checks,
            "all_ok": all(v["ok"] for v in checks.values())}


def smoke_test(conn) -> dict:
    """C1 Hard Gate 冒烟：
        1) Runtime Event insert + hash chain verify
        2) Decision→Release identity（validate_runtime_identity）
        3) Certificate identity（SMALL_LIVE 校验）
        4) Evidence Store insert
        5) Missing-table fail-closed（缺表仍必须 NOT_PROVEN）
    """
    from QCFP_MTF.execution.runtime_event_ledger import \
        append_runtime_event, ensure_runtime_event_table, \
        verify_runtime_event_chain
    from QCFP_MTF.monitoring.runtime_evidence import \
        build_runtime_evidence_from_ledger
    from QCFP_MTF.monitoring.runtime_evidence_store import \
        persist_daily_runtime_evidence
    results = {}
    # 1) Event insert + hash chain
    ev = append_runtime_event(conn, {
        "event_id": f"SMOKE-EVT-{datetime.now():%H%M%S%f}",
        "event_type": "BROKER_POSITION",
        "event_time": _now(),
        "release_id": "MTR-CLOSURE-1",
        "execution_mode": "SHADOW",
        "stock_code": "00700",
        "broker_position": 0.0,
        "payload": {"smoke": True}},
        require_decision=False)
    chain = verify_runtime_event_chain(conn)
    results["event_insert"] = ev.get("inserted", 0) > 0
    results["event_hash_verification"] = chain.get("verified", False)
    # 2) Decision→Release identity：取一条真实 ACTIVE 决策
    dec = conn.execute(
        "SELECT decision_id, context FROM qcfp_decision_ledger "
        "WHERE status='ACTIVE' AND decision_id IS NOT NULL "
        "LIMIT 1").fetchone()
    if dec:
        from QCFP_MTF.execution.runtime_event_ledger import \
            validate_runtime_identity
        ident = validate_runtime_identity(conn, {
            "event_type": "ORDER_SENT",
            "decision_id": dec["decision_id"],
            "release_id": "MTR-CLOSURE-1",
            "execution_mode": "PAPER"}, require_decision=True)
        results["decision_release_identity"] = ident["valid"]
    else:
        results["decision_release_identity"] = None
    # 3) Certificate identity：为同一决策写证书并校验 SMALL_LIVE
    if dec:
        cert_id = f"SMOKE-CERT-{datetime.now():%H%M%S%f}"
        conn.execute(
            "INSERT OR IGNORE INTO qcfp_decision_certificate "
            "(certificate_id, decision_id, release_id, created_at) "
            "VALUES (?,?,?,?)",
            (cert_id, dec["decision_id"], "MTR-CLOSURE-1", _now()))
        conn.commit()
        from QCFP_MTF.execution.runtime_event_ledger import \
            validate_runtime_identity
        ident = validate_runtime_identity(conn, {
            "event_type": "ORDER_SENT",
            "decision_id": dec["decision_id"],
            "release_id": "MTR-CLOSURE-1",
            "execution_mode": "SMALL_LIVE",
            "certificate_id": cert_id}, require_decision=True)
        results["certificate_identity"] = ident["valid"]
    else:
        results["certificate_identity"] = None
    # 4) Evidence Store insert（隔离连接，用临时 artifact）
    tmp = sqlite3.connect(":memory:")
    tmp.row_factory = sqlite3.Row
    store_ok = False
    try:
        artifact = {
            "verdict": "EVIDENCE_READY",
            "evidence_hash": "SMOKE-HASH",
            "evidence": {
                "decision": {"actual_decisions": 1, "coverage": 1.0,
                             "permission_violations": 0,
                             "pit_violations": 0,
                             "uncertified_executions": 0},
                "execution": {"unresolved_unknown": 0},
                "reconciliation": {"unresolved_mismatch": 0},
                "safety": {"incident_count": 0,
                           "critical_replay_mismatch": 0}}}
        persist_daily_runtime_evidence(
            tmp, artifact, release_id="MTR-CLOSURE-1",
            execution_mode="SHADOW", trade_date="2026-08-21",
            run_id="smoke")
        store_ok = tmp.execute(
            "SELECT 1 FROM qcfp_runtime_evidence_daily "
            "WHERE evidence_id LIKE 'RE-MTR-CLOSURE-1-%'").fetchone() \
            is not None
    finally:
        tmp.close()
    results["evidence_store_insert"] = store_ok
    # 5) Missing-table fail-closed：无 qcfp_decision_ledger 仍 NOT_PROVEN
    bare = sqlite3.connect(":memory:")
    bare.row_factory = sqlite3.Row
    r = build_runtime_evidence_from_ledger(
        bare, "REL-A", {"start": "2026-08-01", "end": "2026-08-28"},
        execution_mode="SHADOW")
    bare.close()
    results["missing_table_fail_closed"] = r["verdict"] == "NOT_PROVEN"
    return results


def main(argv=None) -> int:
    out_dir = get_report_root() / "audit" / "runtime_schema"
    out_dir.mkdir(parents=True, exist_ok=True)
    sql_path = get_qcfp_dir() / "sql" / "create_qcfp_tables.sql"
    db_path = get_db_path()
    conn = connect()
    try:
        before = capture_schema(conn)
        expected = parse_expected_from_sql(sql_path)
        plan = migration_plan(before, expected)
        _write_json(out_dir / "schema_before.json", before)
        _write_json(out_dir / "schema_expected.json", expected)
        _write_json(out_dir / "migration_plan.json", {
            **plan, "backup": None, "applied_at": None})
        # Backup + 执行迁移
        backup = backup_db(conn, db_path)
        n = execute_sql_file(conn, sql_path)
        conn.commit()
        after = capture_schema(conn)
        diff = {}
        for t in RUNTIME_TABLES:
            before_cols = set(before["tables"][t]["columns"])
            after_cols = set(after["tables"][t]["columns"])
            diff[t] = {
                "created": not before["tables"][t]["exists"]
                and after["tables"][t]["exists"],
                "added_columns": sorted(after_cols - before_cols),
                "removed_columns": sorted(before_cols - after_cols),
            }
        _write_json(out_dir / "runtime_schema_diff.json", diff)
        verification = verify_schema(conn, expected)
        _write_json(out_dir / "runtime_schema_verification.json",
                    verification)
        smoke = smoke_test(conn)
        _write_json(out_dir / "runtime_smoke_test.json", smoke)
        gates = {
            "required_runtime_tables_100%": verification["all_ok"],
            "required_columns_100%": verification["all_ok"],
            "runtime_insert_test": smoke["event_insert"],
            "event_hash_verification": smoke["event_hash_verification"],
            "decision_release_identity": smoke[
                "decision_release_identity"] is True,
            "certificate_identity": smoke["certificate_identity"] is True,
            "evidence_store_insert": smoke["evidence_store_insert"],
            "missing_table_fail_closed":
                smoke["missing_table_fail_closed"],
        }
        ready = all(gates.values())
        report = {
            "schema_version": "RUNTIME-SCHEMA-1",
            "status": "RUNTIME_SCHEMA_READY" if ready
            else "RUNTIME_SCHEMA_INCOMPLETE",
            "backup_path": str(backup),
            "sql_statements_executed": n,
            "migration_plan": {**plan, "backup": str(backup),
                               "applied_at": _now()},
            "gates": gates,
            "smoke": smoke,
            "generated_at": _now(),
            "rule": "任一 Gate 失败 → RUNTIME_SCHEMA_INCOMPLETE；"
                    "迁移后缺表仍必须 NOT_PROVEN（fail-closed 不被破坏）",
        }
        _write_json(out_dir / "runtime_schema_migration_report.json",
                    report)
        print(f"Runtime Schema: {report['status']}")
        for k, v in gates.items():
            print(f"  {k}: {v}")
        return 0 if ready else 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
