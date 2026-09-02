#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P5 —— DSS 决策展示投影器（MTR Closure：Ledger Projection Adapter）

本脚本不再拥有任何决策权威，也不再执行第二次 Canonical 计算。
正式决策真值唯一存放在 qcfp_decision_ledger（由 decision.engine.evaluate
→ decision.decision_ledger.record_snapshot 产生）。

本脚本只做：
    qcfp_mtf_decision（展示表）
        → 读取 qcfp_decision_ledger 最新 ACTIVE Canonical DecisionSnapshot
        → project_display_fields() 纯投影（不重新 evaluate）
        → 回写展示字段

关键约束：
    * 禁止 evaluate() / FSM / Sizing / Governance 的任何重算；
    * 缺失 Ledger 决策的行不投影、不伪造，标记 ledger_status=LEDGER_MISSING；
    * canonical_action 只是 PreviousPosition→FinalTarget 的确定性展示标签
      （decision.canonical_action），不是第二次决策。

用法：
    python Core/QCFP_MTF/scripts/decision_engine.py [--stock 00700] [--dry-run]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import get, load_qcfp_settings


def load_canonical_snapshot(conn, stock, date, settings_hash=None):
    """Ledger ONLY 读取：qcfp_decision_ledger 最新 ACTIVE 决策。

    正式语义与报告层一致：settings_hash/model/rule 必须严格匹配；
    缺失即返回 None（不重算、不伪造、不降级到 Shadow）。
    """
    from QCFP_MTF.decision.decision_ledger import load_ledger_snapshot
    from QCFP_MTF.decision.decision_snapshot import _snapshot_from_dict
    s = load_ledger_snapshot(conn, stock, date,
                             settings_hash=settings_hash)
    return _snapshot_from_dict(s) if s else None


def project_display_fields(snap) -> dict:
    """纯投影：把已认证的 Ledger DecisionSnapshot 映射为展示字段。

    禁止任何决策链计算（evaluate / FSM / Sizing / Governance / Caps）。
    canonical_action 由 PreviousPosition→FinalTarget 确定性派生，
    只做展示标签，不产生新决策。
    """
    from QCFP_MTF.decision.canonical_action import canonical_action
    action = canonical_action(snap.previous_position, snap.target_position)
    return {
        "action_signal": action,
        "base_action": action,
        "base_target": float(snap.raw_target_position or 0.0),
        "final_action": action,
        "final_target": float(snap.target_position or 0.0),
        "risk_level": (snap.context or {}).get("risk_level") or "Medium",
        "qcfp_score": 0.0,          # DISPLAY_ONLY：不参与任何决策
        "risk_reasons": snap.primary_reason,
        "engine_source": "ledger",
        "authority": "LEDGER_PROJECTION_ONLY",
        "ledger_run_id": snap.run_id,
        "ledger_decision_id": snap.decision_id,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="QCFP-MTF DSS 决策展示投影器（Ledger Projection Adapter）")
    parser.add_argument("--stock", help="只处理指定股票代码")
    parser.add_argument("--dry-run", action="store_true", help="不写库，仅打印结果")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    from QCFP_MTF.decision.decision_snapshot import _settings_hash
    from QCFP_MTF.decision.versions import MODEL_VERSION
    settings_hash = _settings_hash(settings)
    model_version = get(settings, "model.version", MODEL_VERSION)
    log_name = f"decision_engine_{args.stock}" if args.stock else "decision_engine"
    logger = setup_logger("decision_engine", log_file=f"{log_name}.log", mode="w")
    logger.info("=== DSS 决策展示投影器启动（Ledger Projection Adapter）===")

    read_conn = connect()
    try:
        df = pd.read_sql_query(
            """SELECT stock_code, stock_name, decision_date, structural_regime,
                      monthly_behavior_state, tactical_signal,
                      chip_stability_confidence, mtf_regime, qcfp_score,
                      structure_behavior_alignment, market_context, data_quality,
                      catalyst_score, align_method, des_score, des_band,
                      risk_override_active, alignment_override
               FROM qcfp_mtf_decision""", read_conn)
    finally:
        read_conn.close()

    try:
        if args.stock:
            df = df[df["stock_code"] == args.stock]
        if df.empty:
            logger.error("无可处理决策行（请先运行 mtf_fusion_engine）")
            return 1

        # 唯一事实源：qcfp_decision_ledger（settings_hash 严格匹配）
        projections = {}
        ledger_missing = []
        conn = connect()
        try:
            for _, r in df.iterrows():
                snap = load_canonical_snapshot(
                    conn, r["stock_code"], r["decision_date"],
                    settings_hash=settings_hash)
                if snap is None:
                    ledger_missing.append(
                        f"{r['stock_code']}/{r['decision_date']}")
                    continue
                projections[(r["stock_code"], r["decision_date"])] = \
                    project_display_fields(snap)
        finally:
            conn.close()

        if ledger_missing:
            logger.warning(
                f"{len(ledger_missing)} 行无匹配 Ledger 决策，未投影："
                f"{', '.join(ledger_missing[:10])}"
                f"{'…' if len(ledger_missing) > 10 else ''}")

        rows = []
        for _, r in df.iterrows():
            p = projections.get((r["stock_code"], r["decision_date"]))
            if p is None:
                continue
            rows.append({**r.to_dict(), **p,
                         "ledger_status": "PROJECTED"})
        projected = pd.DataFrame(rows) if rows else df.iloc[0:0].copy()

        if not args.dry_run and not projected.empty:
            write_conn = connect()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            update_rows = []
            for _, r in df.iterrows():
                p = projections.get((r["stock_code"], r["decision_date"]))
                if p is None:
                    continue
                update_rows.append((
                    p["action_signal"], p["risk_level"], p["qcfp_score"],
                    r.get("des_score") or 0, r.get("des_band") or "NORMAL",
                    p["base_action"], p["final_action"], p["base_target"],
                    p["final_target"], int(r.get("risk_override_active") or 0),
                    int(r.get("alignment_override") or 0), now,
                    r["stock_code"], r["decision_date"]))
            write_conn.execute("BEGIN IMMEDIATE")
            for row in update_rows:
                write_conn.execute(
                    """UPDATE qcfp_mtf_decision
                       SET action_signal=?, risk_level=?, qcfp_score=?,
                           des_score=?, des_band=?, base_action=?,
                           final_action=?, base_target=?, final_target=?,
                           risk_override_active=?, alignment_override=?,
                           update_time=?
                       WHERE stock_code=? AND decision_date=?""",
                    row,
                )
            write_conn.commit()
            write_conn.close()
            logger.info(
                f"已投影回写 {len(update_rows)} 行 action/risk 到 "
                f"qcfp_mtf_decision")
        elif args.dry_run:
            logger.info("--dry-run 模式：未写库")

        latest = df.sort_values("decision_date").groupby("stock_code").tail(1)
        logger.info("=== 最新决策（仅展示投影）===")
        for _, r in latest.iterrows():
            p = projections.get((r["stock_code"], r["decision_date"]))
            action = p["action_signal"] if p else "LEDGER_MISSING"
            logger.info(
                f"  {r['stock_code']} {r['decision_date']}: {r['mtf_regime']} "
                f"→ {action}")

        report_root = get_report_root() / "fusion"
        report_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d")
        fname = f"decision_{args.stock}_{stamp}" if args.stock \
            else f"decision_{stamp}"
        export = projected.copy()
        export["ledger_status"] = "PROJECTED"
        csv_path = report_root / f"{fname}.csv"
        export.to_csv(csv_path, index=False, encoding="utf-8-sig")
        (report_root / f"{fname}.json").write_text(
            json.dumps({"generated_at": stamp, "model_version": model_version,
                        "settings_hash": settings_hash,
                        "projection_only": True,
                        "ledger_missing_count": len(ledger_missing),
                        "records": export.to_dict(orient="records")},
                       ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
        logger.info(f"报告已保存: {csv_path}")
    finally:
        pass  # 读/写连接均已在使用后立即关闭

    logger.info("decision_engine 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
