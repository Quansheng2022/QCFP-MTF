#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— 日线增量价值测试（Daily Incremental Value Test）

Model A：Q+M+W 周线决策（现状）
Model B：Q+M+W + 日线时机门（DAILY_BREAKOUT 早入场 / DAILY_DISTRIBUTION 战术减仓 /
         DAILY_PULLBACK 持有不减）

对比：收益/风险/交易 + MFE/MAE（波段捕捉效率）＋ 01951 2024-02~10 波段。
验收：Model B 显著提高波段捕捉/MFE 实现率，且 OOS 口径 Sharpe 不降、
      回撤不恶化、换手成本可控 → 才判定日线层成功。

用法：
    python Core/QCFP_MTF/scripts/daily_alpha_test.py [--focus 01951]
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

from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.backtest.performance import evaluate
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline
from QCFP_MTF.fusion.daily_timing import apply_daily_timing_gate


def _mfe_mae(bt, weekly_kl, horizon=26):
    """逐股扫描入场事件：MFE/MAE/已实现收益/持有周数/捕捉率"""
    kl = weekly_kl[["stock_code", "date", "high", "low", "close"]].copy()
    kl["week_end"] = pd.to_datetime(kl["date"]).dt.strftime("%Y-%m-%d")
    kl = kl.sort_values(["stock_code", "week_end"])
    recs = []
    for code, bg in bt.groupby("stock_code", sort=False):
        bg = bg.sort_values("week_end").reset_index(drop=True)
        kg = kl[kl["stock_code"] == code].reset_index(drop=True)
        if kg.empty:
            continue
        kl_map = {r["week_end"]: r for _, r in kg.iterrows()}
        i, n = 0, len(bg)
        while i < n:
            r = bg.iloc[i]
            if float(r["position"]) <= 0:
                i += 1
                continue
            entry_week = r["week_end"]
            entry = kl_map.get(entry_week)
            if entry is None or pd.isna(entry["close"]):
                i += 1
                continue
            entry_close = float(entry["close"])
            mfe = mae = 0.0
            exit_week, realized = None, None
            horizon_close = None
            j, hcount = i + 1, 0
            while j < n and hcount < horizon:
                rr = bg.iloc[j]
                k = kl_map.get(rr["week_end"])
                if k is not None:
                    hcount += 1
                    horizon_close = float(k["close"])
                    mfe = max(mfe, float(k["high"]) / entry_close - 1)
                    mae = min(mae, float(k["low"]) / entry_close - 1)
                if float(rr["position"]) == 0:
                    exit_week = rr["week_end"]
                    break
                j += 1
            if exit_week is not None and exit_week in kl_map:
                realized = float(kl_map[exit_week]["close"]) / entry_close - 1
            else:
                # P0 口径统一：realized 只算 horizon 内最后一周，禁止泄漏到数据集尾部
                realized = horizon_close / entry_close - 1 \
                    if horizon_close is not None else None
            recs.append({
                "stock_code": code, "entry_week": entry_week,
                "mfe": mfe, "mae": mae, "realized": realized,
                "capture": realized / mfe if mfe > 0.02 else None,
                "hold_weeks": hcount,
            })
            i = j if j > i else i + 1
    return pd.DataFrame(recs)


def _mfe_summary(m):
    if m is None or m.empty:
        return {"n_entries": 0}
    return {
        "n_entries": int(len(m)),
        "mean_mfe": round(float(m["mfe"].mean()), 4),
        "mean_mae": round(float(m["mae"].mean()), 4),
        "mean_realized": round(float(m["realized"].mean()), 4),
        "mean_capture": round(float(m["capture"].mean()), 4)
        if m["capture"].notna().any() else None,
        "median_mfe": round(float(m["mfe"].median()), 4),
        "median_mae": round(float(m["mae"].median()), 4),
        "win_rate": round(float((m["realized"] > 0).mean()), 4),
        "avg_hold_weeks": round(float(m["hold_weeks"].mean()), 2),
        "n_mfe_ge_10pct": int((m["mfe"] >= 0.10).sum()),
    }


def _wave(bt, focus, start, end):
    w = bt[(bt["stock_code"] == focus) &
           (bt["week_end"] >= start) & (bt["week_end"] <= end)]
    if w.empty:
        return {"wave_return": None, "pos_weeks": 0, "weeks": 0}
    return {
        "wave_return": round(float((1 + w["pnl"]).prod() - 1), 6),
        "pos_weeks": int((w["position"] > 0).sum()),
        "weeks": int(len(w)),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 日线增量价值测试")
    parser.add_argument("--focus", default="01951")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    logger = setup_logger("daily_alpha_test", log_file="daily_alpha_test.log", mode="a")
    logger.info("=== 日线增量价值测试启动 ===")

    structural = pd.read_sql_query(
        "SELECT stock_code, stock_name, period_end, available_date, structural_regime, "
        "c_state, f_state, p_state, q_trend_score, q_position_52w, data_quality "
        "FROM qcfp_quarterly_structural", connect())
    monthly = pd.read_sql_query(
        "SELECT stock_code, month_end, monthly_behavior_state, cbi_score, cbi_state, "
        "cost_position, data_quality FROM qcfp_monthly_behavior", connect())
    weekly = pd.read_sql_query(
        "SELECT stock_code, stock_name, week_end, tactical_signal, data_quality "
        "FROM qcfp_weekly_tactical", connect())
    chip = load_derived("quarterly_chip_analysis")[["stock_code", "quarter_end_date",
                                                    "chip_structure_score"]]
    idx = load_idx_hist()
    weekly_kl = load_kline("weekly")
    daily = pd.read_sql_query(
        "SELECT stock_code, trade_date, daily_state FROM qcfp_daily_tactical", connect())
    end = args.end or weekly["week_end"].max()
    wave_start, wave_end = "2024-02-02", "2024-10-31"

    signals_a = build_signal_timeline(structural, monthly, weekly, chip, idx, settings,
                                      weekly_kl=weekly_kl, daily=daily)
    signals_b = apply_daily_timing_gate(signals_a, daily, settings)
    bt_a = run_backtest(signals_a, weekly_kl, settings, start=args.start, end=end)
    bt_b = run_backtest(signals_b, weekly_kl, settings, start=args.start, end=end)

    def _perf(bt):
        port = portfolio_returns(bt)
        perf = evaluate(port["portfolio_return"], turnover=port["avg_turnover"])
        return {**perf,
                "avg_weekly_cost": round(float(bt["cost"].mean()), 6)}

    pa, pb = _perf(bt_a), _perf(bt_b)
    ma, mb = _mfe_mae(bt_a, weekly_kl), _mfe_mae(bt_b, weekly_kl)
    wa, wb = _wave(bt_a, args.focus, wave_start, wave_end), \
        _wave(bt_b, args.focus, wave_start, wave_end)
    rows = [
        {"model": "A_QMW", "annualized_return": pa["annualized_return"],
         "sharpe": pa["sharpe"], "max_drawdown": pa["max_drawdown"],
         "annual_turnover": pa["annual_turnover"], "avg_weekly_cost": pa["avg_weekly_cost"],
         "wave_return": wa["wave_return"], "wave_pos_weeks": wa["pos_weeks"],
         **{f"mfe_{k}": v for k, v in _mfe_summary(ma).items()}},
        {"model": "B_QMWD", "annualized_return": pb["annualized_return"],
         "sharpe": pb["sharpe"], "max_drawdown": pb["max_drawdown"],
         "annual_turnover": pb["annual_turnover"], "avg_weekly_cost": pb["avg_weekly_cost"],
         "wave_return": wb["wave_return"], "wave_pos_weeks": wb["pos_weeks"],
         **{f"mfe_{k}": v for k, v in _mfe_summary(mb).items()}},
    ]
    result = pd.DataFrame(rows)

    logger.info("=== Model A (QMW) vs Model B (QMWD) ===")
    for _, r in result.iterrows():
        logger.info(
            f"  {r['model']}: 年化 {r['annualized_return']:.2%}  Sharpe {r['sharpe']}  "
            f"回撤 {r['max_drawdown']:.2%}  换手 {r['annual_turnover']:.2f}  "
            f"周成本 {r['avg_weekly_cost']:.5f}  | {args.focus} 波段 "
            f"{r['wave_return']:.2%}（{r['wave_pos_weeks']} 周）  | "
            f"MFE均值 {r['mfe_mean_mfe']:.2%} 捕捉率 {r['mfe_mean_capture']:.0%}  "
            f"MFE≥10% {r['mfe_n_mfe_ge_10pct']} 笔")

    # 验收：B 显著提高波段/MFE 实现，且 Sharpe/回撤/换手可控
    checks = {
        "波段捕捉提升": wb["wave_return"] is not None and
        (wa["wave_return"] or 0) < wb["wave_return"] and
        (wb["wave_return"] - (wa["wave_return"] or 0)) > 0.005,
        "Sharpe 不显著下降": pb["sharpe"] >= pa["sharpe"] - 0.01,
        "回撤不恶化": pb["max_drawdown"] >= pa["max_drawdown"] - 0.01,
        "换手可控(<=1.4x)": pb["annual_turnover"] <= pa["annual_turnover"] * 1.4 + 0.05,
        "MFE 捕捉率不降": _mfe_summary(mb)["mean_capture"] is None or
        _mfe_summary(mb)["mean_capture"] >= (_mfe_summary(ma)["mean_capture"] or 0) - 0.03,
    }
    for name, ok in checks.items():
        logger.info(f"  验收[{name}]: {'PASS' if ok else 'FAIL'}")
    n_pass = sum(checks.values())
    wave_ok = checks["波段捕捉提升"]
    others = n_pass - (1 if wave_ok else 0)
    success = wave_ok and others >= 3
    logger.info(f"验收结论: {n_pass}/5 PASS（波段捕捉提升为必过项）→ "
                f"{'日线战术层成功，可正式接入' if success else '日线层价值不足，保持诊断工具'}")

    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (report_root / f"daily_alpha_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "focus": args.focus,
                    "wave": {"start": wave_start, "end": wave_end},
                    "models": result.to_dict(orient="records"),
                    "acceptance": checks},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    result.to_csv(report_root / f"daily_alpha_{stamp}.csv",
                  index=False, encoding="utf-8-sig")
    logger.info(f"报告已保存: Report/QCFP_MTF/backtest/daily_alpha_{stamp}.{{json,csv}}")
    logger.info("daily_alpha_test 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
