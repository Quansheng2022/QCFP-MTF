#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P4 —— 多周期融合引擎

流程：读取三层 qcfp_* 表 → 按决策日对齐（最近季度/月线 + 当周触发）
      → Chip Confidence / MTF 对齐 / 结构-行为背离 / 市场环境
      → UPSERT 写入 qcfp_mtf_decision

用法：
    python Core/QCFP_MTF/scripts/mtf_fusion_engine.py [--stock 00700]
        [--date 2026-08-14] [--dry-run]
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
from QCFP_MTF.common.asof import (apply_disclosure_overrides, asof_join_latest,
                                  load_disclosure_overrides)
from QCFP_MTF.decision.catalyst_quality import (calc_catalyst_quality,
                                                catalyst_type)
from QCFP_MTF.config.settings import get, load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist
from QCFP_MTF.fusion.anti_inference import filter_conclusions
from QCFP_MTF.fusion.chip_confidence import compute_chip_confidence
from QCFP_MTF.fusion.mtf_alignment import align_mtf, structure_behavior_alignment

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def _market_context(idx_df: pd.DataFrame, decision_dates: pd.DatetimeIndex, settings) -> pd.Series:
    """基于 HSI 60 日收益 + VHSI 的市场环境（risk_on/risk_off/neutral）"""
    cfg = settings.get("fusion", {}).get("market_context", {})
    win = int(cfg.get("hsi_return_window", 60))
    vhsi_off = float(cfg.get("vhsi_risk_off", 25))
    idx = idx_df[["date", "HSI", "VHSI"]].copy()
    idx["date"] = pd.to_datetime(idx["date"])
    idx = idx.sort_values("date").dropna(subset=["HSI"])
    idx["hsi_ret"] = idx["HSI"] / idx["HSI"].shift(win) - 1.0
    idx = idx[["date", "hsi_ret", "VHSI"]].sort_values("date")
    asof = pd.DataFrame({"date": decision_dates})
    m = pd.merge_asof(asof, idx, on="date", direction="backward")

    def _ctx(r):
        if pd.isna(r["hsi_ret"]) or pd.isna(r["VHSI"]):
            return "neutral"
        if r["hsi_ret"] > 0.02 and r["VHSI"] < vhsi_off:
            return "risk_on"
        if r["hsi_ret"] < -0.02 or r["VHSI"] > vhsi_off:
            return "risk_off"
        return "neutral"

    return m.apply(_ctx, axis=1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 多周期融合引擎")
    parser.add_argument("--stock", help="只处理指定股票代码")
    parser.add_argument("--date", help="只处理指定决策日（YYYY-MM-DD）")
    parser.add_argument("--dry-run", action="store_true", help="不写库，仅打印结果")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    from QCFP_MTF.decision.versions import MODEL_VERSION
    model_version = get(settings, "model.version", MODEL_VERSION)
    lag_days = int(get(settings, "institutional.disclosure_lag_days", 45))
    score_map = settings.get("fusion", {}).get("score_mapping", {})
    ai_mode = settings.get("fusion", {}).get("anti_inference", {}).get("mode", "warn")
    log_name = f"mtf_fusion_engine_{args.stock}" if args.stock else "mtf_fusion_engine"
    logger = setup_logger("mtf_fusion_engine", log_file=f"{log_name}.log", mode="w")
    logger.info("=== 多周期融合引擎启动 ===")

    _conn = connect()
    try:
        structural = pd.read_sql_query(
            "SELECT stock_code, stock_name, period_end, available_date, "
            "structural_regime, c_state, f_state, q_trend_score, "
            "q_position_52w, data_quality "
            "FROM qcfp_quarterly_structural", _conn)
        monthly = pd.read_sql_query(
            "SELECT stock_code, month_end, monthly_behavior_state, cbi_score, "
            "cbi_state, cost_position, data_quality "
            "FROM qcfp_monthly_behavior", _conn)
        weekly = pd.read_sql_query(
            "SELECT stock_code, stock_name, week_end, tactical_signal, data_quality "
            "FROM qcfp_weekly_tactical", _conn)
    finally:
        _conn.close()
    chip = load_derived("quarterly_chip_analysis")
    chip = chip[["stock_code", "quarter_end_date", "chip_structure_score"]].copy()
    idx = load_idx_hist()

    if args.stock:
        structural = structural[structural["stock_code"] == args.stock]
        monthly = monthly[monthly["stock_code"] == args.stock]
        weekly = weekly[weekly["stock_code"] == args.stock]
    if weekly.empty:
        logger.error("周线数据为空，请先运行 weekly_tactical_engine")
        return 1
    if args.date:
        weekly = weekly[weekly["week_end"] == args.date].reset_index(drop=True)
    if weekly.empty:
        logger.error(f"指定决策日 {args.date} 无周线数据")
        return 1

    # 统一为 datetime 以便 merge_asof
    # 统一 as-of 可用性：结构按 available_date（真实披露日），
    # 筹码评分同源季度披露，按 quarter_end + 披露滞后推算；
    # 月/周数据期末即已知，按 period_end 对齐。
    structural["available_date_dt"] = pd.to_datetime(
        structural["available_date"], errors="coerce")
    structural["available_date_dt"] = structural["available_date_dt"].fillna(
        pd.to_datetime(structural["period_end"], errors="coerce")
        + pd.Timedelta(days=lag_days))
    overrides = load_disclosure_overrides()
    if overrides:
        structural = apply_disclosure_overrides(structural, overrides)
    monthly["month_end_dt"] = pd.to_datetime(monthly["month_end"], errors="coerce")
    weekly["week_end_dt"] = pd.to_datetime(weekly["week_end"], errors="coerce")
    # P0-2：统一 Chip/Structural 披露日（优先真实/覆盖披露日）
    struct_disc = {(r["stock_code"], r["period_end"]): r["available_date_dt"]
                   for _, r in structural.iterrows()}
    chip["quarter_end"] = pd.to_datetime(
        chip["quarter_end_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    chip["_disc"] = [
        struct_disc.get((r["stock_code"], r["quarter_end"])) for _, r in chip.iterrows()]
    chip["available_date_dt"] = pd.to_datetime(chip["_disc"], errors="coerce")
    chip["available_date_dt"] = chip["available_date_dt"].fillna(
        pd.to_datetime(chip["quarter_end_date"], errors="coerce")
        + pd.Timedelta(days=lag_days))

    w = weekly[["stock_code", "stock_name", "week_end_dt"]].copy()
    w = w.rename(columns={"week_end_dt": "decision_dt"})
    w = w.sort_values("decision_dt")

    w = asof_join_latest(
        w, structural, "decision_dt", "available_date_dt",
        right_cols=["period_end", "structural_regime", "c_state", "f_state",
                    "q_trend_score", "q_position_52w", "data_quality"])
    w = asof_join_latest(
        w, monthly, "decision_dt", "month_end_dt",
        right_cols=["monthly_behavior_state", "cbi_score", "cbi_state",
                    "cost_position", "data_quality"],
        suffixes=("", "_m"))
    w = asof_join_latest(
        w, chip, "decision_dt", "available_date_dt",
        right_cols=["chip_structure_score"], suffixes=("", "_c"))
    w = w.merge(weekly[["stock_code", "week_end_dt", "tactical_signal", "data_quality"]]
                .rename(columns={"data_quality": "data_quality_w", "week_end_dt": "decision_dt"}),
                on=["stock_code", "decision_dt"], how="left")

    # 融合计算
    w["confidence_score"], w["chip_stability_confidence"] = zip(*[
        compute_chip_confidence(r["chip_structure_score"], r["cbi_score"], r["c_state"], settings)
        for _, r in w.iterrows()])
    # 上一季度 F 状态（资金持续性）+ 催化剂质量评分
    struct_sorted = structural.sort_values(["stock_code", "period_end"]).copy()
    struct_sorted["prev_f"] = struct_sorted.groupby("stock_code")["f_state"].shift(1)
    prev_f_map = {(r["stock_code"], r["period_end"]): r["prev_f"]
                  for _, r in struct_sorted.iterrows()}
    w["prev_f_state"] = [
        prev_f_map.get((r["stock_code"], r["period_end"])) for _, r in w.iterrows()]
    w["catalyst_score"] = [
        calc_catalyst_quality(r["f_state"], r["prev_f_state"],
                              r.get("q_trend_score"), r.get("q_position_52w"),
                              r.get("cbi_state"))
        for _, r in w.iterrows()]
    w["catalyst_type"] = w["catalyst_score"].map(catalyst_type)
    to_cfg = settings.get("decision", {}).get("tactical_override", {})
    to_enabled = bool(to_cfg.get("enabled", True))
    to_max_52w = float(to_cfg.get("max_52w_position", 0.15))
    min_trigger = to_cfg.get("min_trigger", "Breakout")
    if isinstance(min_trigger, str):
        min_trigger = tuple(x.strip() for x in min_trigger.split(",") if x.strip())
    else:
        min_trigger = tuple(min_trigger)
    w["mtf_regime"], w["align_method"] = zip(*[
        align_mtf(r["structural_regime"], r["monthly_behavior_state"],
                  r["tactical_signal"],
                  tactical_override=to_enabled,
                  position_52w=r.get("q_position_52w"),
                  max_52w_position=to_max_52w, min_trigger=min_trigger)
        for _, r in w.iterrows()])
    w["structure_behavior_alignment"] = [
        structure_behavior_alignment(r["structural_regime"], r["monthly_behavior_state"])
        for _, r in w.iterrows()]
    w["market_context"] = _market_context(idx, pd.DatetimeIndex(w["decision_dt"]), settings)
    w["qcfp_score"] = w["mtf_regime"].map(lambda s: score_map.get(s) if s else None)

    # 数据质量（三层最差）；结构 UNDETERMINED/D → 整行 DATA_INSUFFICIENT
    def _worst_dq(r):
        grades = [r["data_quality"], r["data_quality_m"], r["data_quality_w"]]
        grades = [g for g in grades if g is not None]
        return max(grades, key=lambda g: GRADE_ORDER.get(g, 3)) if grades else "D"

    w["data_quality"] = w.apply(_worst_dq, axis=1)
    insufficient = (w["structural_regime"].isna()) | \
                   (w["structural_regime"] == "STATE_UNDETERMINED") | \
                   (w["data_quality"] == "D")
    w.loc[insufficient, "mtf_regime"] = "DATA_INSUFFICIENT"
    w.loc[insufficient, "qcfp_score"] = None

    # 证据摘要 + Anti-Inference 检查
    summaries, ai_checks = [], []
    for _, r in w.iterrows():
        text = (f"结构:{r['structural_regime']}(A/A-); 阶段:{r['monthly_behavior_state']}(B); "
                f"触发:{r['tactical_signal']}(C); 置信度:{r['chip_stability_confidence']}")
        filtered, hits = filter_conclusions(text, mode=ai_mode)
        summaries.append(filtered)
        ai_checks.append("PASSED" if not hits else "FLAGGED")
    w["evidence_summary"] = summaries
    w["ai_check"] = ai_checks
    w["decision_date"] = w["decision_dt"].dt.strftime("%Y-%m-%d")

    latest = w.sort_values("decision_dt").groupby("stock_code").tail(1)
    logger.info("=== 最新 MTF 决策 ===")
    for _, r in latest.iterrows():
        logger.info(
            f"  {r['stock_code']} {r['decision_date']}: {r['mtf_regime']} "
            f"(conf={r['chip_stability_confidence']}, align={r['structure_behavior_alignment']}, "
            f"market={r['market_context']}, dq={r['data_quality']}, ai={r['ai_check']})")

    report_root = get_report_root() / "fusion"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    out_cols = ["stock_code", "stock_name", "decision_date", "structural_regime",
                "monthly_behavior_state", "tactical_signal", "cbi_score", "cost_position",
                "chip_stability_confidence", "mtf_regime", "qcfp_score",
                "structure_behavior_alignment", "market_context", "evidence_summary",
                "ai_check", "data_quality", "align_method"]
    out = w[out_cols]
    fname = f"mtf_decision_{args.stock}_{stamp}" if args.stock else f"mtf_decision_{stamp}"
    csv_path = report_root / f"{fname}.csv"
    json_path = report_root / f"{fname}.json"
    out.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(
        json.dumps({"generated_at": stamp, "model_version": model_version,
                    "records": out.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info(f"报告已保存: {csv_path}")

    if not args.dry_run:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for _, r in w.iterrows():
            rows.append((
                r["stock_code"], r["stock_name"], r["decision_date"],
                r["structural_regime"], r["monthly_behavior_state"], r["tactical_signal"],
                r["cbi_score"], r["cost_position"], r["chip_stability_confidence"],
                r["mtf_regime"], r["qcfp_score"], r["structure_behavior_alignment"],
                None, None,
                r["market_context"], r["evidence_summary"],
                r["align_method"],
                r["catalyst_score"], r["catalyst_type"],
                model_version, r["data_quality"], now,
            ))
        conn = connect()
        try:
            conn.executemany(
                """INSERT OR REPLACE INTO qcfp_mtf_decision
                   (stock_code, stock_name, decision_date,
                    structural_regime, monthly_behavior_state, tactical_signal,
                    cbi_score, cost_position, chip_stability_confidence,
                    mtf_regime, qcfp_score, structure_behavior_alignment,
                    action_signal, risk_level,
                    market_context, evidence_summary,
                    align_method,
                    catalyst_score, catalyst_type,
                    model_version, data_quality, update_time)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            conn.commit()
            logger.info(f"已 UPSERT {len(rows)} 行到 qcfp_mtf_decision")
        finally:
            conn.close()
    else:
        logger.info("--dry-run 模式：未写库")

    logger.info("mtf_fusion_engine 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
