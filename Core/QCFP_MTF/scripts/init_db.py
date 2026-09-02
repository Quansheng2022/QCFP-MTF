#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P0.2 —— 初始化数据库
创建 qcfp_* 核心表与索引（SQLiteDB/HK_Stock.db）。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect, execute_sql_file, list_tables, table_exists
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_qcfp_dir

EXPECTED_TABLES = [
    "qcfp_quarterly_structural",
    "qcfp_monthly_behavior",
    "qcfp_weekly_tactical",
    "qcfp_mtf_decision",
    "qcfp_backtest_results",
    "qcfp_data_quality_audit",
    "qcfp_daily_tactical",
    "qcfp_decision_ledger",
    "qcfp_model_registry",
    "qcfp_strategy_lifecycle",
]


def main() -> int:
    logger = setup_logger("init_db", log_file="init_db.log", mode="w")
    sql_path = get_qcfp_dir() / "sql" / "create_qcfp_tables.sql"
    if not sql_path.exists():
        logger.error(f"建表脚本不存在: {sql_path}")
        return 1

    conn = connect()
    try:
        n = execute_sql_file(conn, sql_path)
        logger.info(f"已执行 {n} 条建表语句（幂等）")
        # 表结构迁移：为已存在的表补充新增列（幂等）
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(qcfp_quarterly_structural)").fetchall()}
        if "resolve_method" not in cols:
            conn.execute("ALTER TABLE qcfp_quarterly_structural ADD COLUMN resolve_method TEXT")
            conn.commit()
            logger.info("已为 qcfp_quarterly_structural 增加 resolve_method 列")
        mb_cols = {r["name"] for r in conn.execute("PRAGMA table_info(qcfp_monthly_behavior)").fetchall()}
        for col, ddl in [
            ("cbi_score", "REAL"),
            ("cbi_state", "TEXT"),
            ("cost_position", "TEXT"),
            ("cost_vs_weekly_vwap", "REAL"),
            ("cost_vs_monthly_vwap", "REAL"),
            ("cost_vs_quarterly_vwap", "REAL"),
        ]:
            if col not in mb_cols:
                conn.execute(f"ALTER TABLE qcfp_monthly_behavior ADD COLUMN {col} {ddl}")
                conn.commit()
                logger.info(f"已为 qcfp_monthly_behavior 增加 {col} 列")
        wt_cols = {r["name"] for r in conn.execute("PRAGMA table_info(qcfp_weekly_tactical)").fetchall()}
        if "w_volume_shrink" not in wt_cols:
            conn.execute("ALTER TABLE qcfp_weekly_tactical ADD COLUMN w_volume_shrink INTEGER DEFAULT 0")
            conn.commit()
            logger.info("已为 qcfp_weekly_tactical 增加 w_volume_shrink 列")
        dt_cols = {r["name"] for r in conn.execute("PRAGMA table_info(qcfp_daily_tactical)").fetchall()}
        if "d_decline" not in dt_cols:
            conn.execute("ALTER TABLE qcfp_daily_tactical ADD COLUMN d_decline INTEGER DEFAULT 0")
            conn.commit()
            logger.info("已为 qcfp_daily_tactical 增加 d_decline 列")
        mtf_cols = {r["name"] for r in conn.execute("PRAGMA table_info(qcfp_mtf_decision)").fetchall()}
        if "structure_behavior_alignment" not in mtf_cols:
            conn.execute("ALTER TABLE qcfp_mtf_decision ADD COLUMN structure_behavior_alignment TEXT")
            conn.commit()
            logger.info("已为 qcfp_mtf_decision 增加 structure_behavior_alignment 列")
        if "catalyst_score" not in mtf_cols:
            conn.execute("ALTER TABLE qcfp_mtf_decision ADD COLUMN catalyst_score REAL")
            conn.execute("ALTER TABLE qcfp_mtf_decision ADD COLUMN catalyst_type TEXT")
            conn.commit()
            logger.info("已为 qcfp_mtf_decision 增加 catalyst_score/catalyst_type 列")
        if "align_method" not in mtf_cols:
            conn.execute("ALTER TABLE qcfp_mtf_decision ADD COLUMN align_method TEXT")
            conn.commit()
            logger.info("已为 qcfp_mtf_decision 增加 align_method 列")
        if "des_score" not in mtf_cols:
            conn.execute("ALTER TABLE qcfp_mtf_decision ADD COLUMN des_score INTEGER")
            conn.execute("ALTER TABLE qcfp_mtf_decision ADD COLUMN des_band TEXT")
            conn.commit()
            logger.info("已为 qcfp_mtf_decision 增加 des_score/des_band 列")
        for col, ddl in [("alignment_override", "INTEGER DEFAULT 0"),
                         ("base_action", "TEXT"),
                         ("final_action", "TEXT"),
                         ("base_target", "REAL"),
                         ("final_target", "REAL"),
                         ("risk_override_active", "INTEGER DEFAULT 0")]:
            if col not in mtf_cols:
                conn.execute(f"ALTER TABLE qcfp_mtf_decision ADD COLUMN {col} {ddl}")
                conn.commit()
                logger.info(f"已为 qcfp_mtf_decision 增加 {col} 列")
        dl_cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(qcfp_decision_ledger)").fetchall()}
        for col, ddl in [("status", "TEXT DEFAULT 'ACTIVE'"),
                         ("superseded_by", "TEXT")]:
            if col not in dl_cols:
                conn.execute(
                    f"ALTER TABLE qcfp_decision_ledger ADD COLUMN {col} {ddl}")
                conn.commit()
                logger.info(f"已为 qcfp_decision_ledger 增加 {col} 列")
        for col, ddl in [("participation_mode", "TEXT"),
                         ("participation_cap", "REAL"),
                         ("position_class", "TEXT"),
                         ("exit_severity", "INTEGER DEFAULT 0"),
                         ("feature_manifest_hash", "TEXT"),
                         ("trade_quality", "REAL"),
                         ("trade_quality_band", "TEXT"),
                         ("data_snapshot_id", "TEXT"),
                         ("data_version", "TEXT")]:
            if col not in dl_cols:
                conn.execute(
                    f"ALTER TABLE qcfp_decision_ledger ADD COLUMN {col} {ddl}")
                conn.commit()
                logger.info(f"已为 qcfp_decision_ledger 增加 {col} 列")
        # 2.3：重建七元审计身份唯一索引（幂等）
        conn.execute("DROP INDEX IF EXISTS idx_qcfp_dl_identity")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_dl_identity "
            "ON qcfp_decision_ledger(decision_id, run_id, input_fingerprint, "
            "data_snapshot_id, data_version, settings_hash, model_version, "
            "rule_version, schema_version)")
        conn.execute(
            "UPDATE qcfp_decision_ledger SET status='ACTIVE' "
            "WHERE status IS NULL")
        conn.commit()
        missing = [t for t in EXPECTED_TABLES if not table_exists(conn, t)]
        if missing:
            logger.error(f"以下表创建失败或缺失: {missing}")
            return 1
        tables = list_tables(conn, prefix="qcfp_")
        logger.info("QCFP 表验证通过:")
        for t in tables:
            logger.info(f"  - {t}")
    finally:
        conn.close()
    logger.info("init_db 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
