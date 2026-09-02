#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.6 —— Institutional State Validation（状态预测价值验证）

不能因为状态叫 ACCUMULATION / DISTRIBUTION 就默认它有预测含义。
对每个 Institutional State 统计：
    Forward 1W / 4W / 8W / 12W 收益
    MFE / MAE / 胜率 / 回撤

用法：python Core/QCFP_MTF/scripts/state_validation.py [--focus 00371]
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

import numpy as np
import pandas as pd

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.data.loader import load_kline

HORIZONS = (1, 4, 8, 12)


def forward_stats(state_rows: pd.DataFrame, weekly_kl: pd.DataFrame,
                  horizons=HORIZONS) -> dict:
    """按状态统计前向收益/MFE/MAE/胜率（按 available_date 对齐，PIT 口径）"""
    w = weekly_kl.copy()
    w["week_end"] = pd.to_datetime(w["date"]).dt.strftime("%Y-%m-%d")
    w = w.sort_values(["stock_code", "week_end"])
    w["ret1"] = w.groupby("stock_code")["close"].pct_change(1)
    w["ret4"] = w.groupby("stock_code")["close"].pct_change(4)
    w["ret8"] = w.groupby("stock_code")["close"].pct_change(8)
    w["ret12"] = w.groupby("stock_code")["close"].pct_change(12)
    out = {h: [] for h in horizons}
    for _, r in state_rows.iterrows():
        code = r["stock_code"]
        avail = r["available_date"]
        seg = w[(w["stock_code"] == code) & (w["week_end"] > avail)]
        if seg.empty:
            continue
        for h in horizons:
            vals = seg[f"ret{h}"].dropna().head(h)
            if vals.empty:
                continue
            out[h].append({
                "stock": code, "state": r["institutional_state"],
                "fwd_return": float(vals.iloc[-1]),
                "mfe": float(vals[vals > 0].max()) if (vals > 0).any() else 0.0,
                "mae": float(vals[vals < 0].min()) if (vals < 0).any() else 0.0,
            })
    summary = {}
    for h in horizons:
        df = pd.DataFrame(out[h])
        if df.empty:
            summary[f"fwd{h}w"] = {"n": 0}
            continue
        g = df.groupby("state").agg(
            n=("fwd_return", "size"),
            mean_return=("fwd_return", "mean"),
            median_return=("fwd_return", "median"),
            win_rate=("fwd_return", lambda s: (s > 0).mean()),
            mean_mfe=("mfe", "mean"),
            mean_mae=("mae", "mean"),
        ).round(4)
        summary[f"fwd{h}w"] = g.to_dict(orient="index")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Institutional State Validation")
    parser.add_argument("--focus", default=None)
    args = parser.parse_args(argv)
    conn = connect()
    try:
        q = pd.read_sql_query(
            "SELECT stock_code, period_end, available_date, "
            "c_state, f_state, p_state FROM qcfp_quarterly_structural "
            "WHERE c_state IS NOT NULL AND f_state IS NOT NULL", conn)
    finally:
        conn.close()
    from QCFP_MTF.institutional.state_engine import institutional_state
    q["institutional_state"] = [
        institutional_state(r["c_state"], r["f_state"], r["p_state"])
        for _, r in q.iterrows()]
    q = q[q["institutional_state"] != "UNKNOWN"]
    if args.focus:
        q = q[q["stock_code"] == args.focus]
    weekly_kl = load_kline("weekly")
    summary = forward_stats(q, weekly_kl)
    out_dir = get_report_root() / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    focus = args.focus or "all"
    (out_dir / f"state_validation_{focus}_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "focus": focus,
                    "summary": summary}, ensure_ascii=False, indent=2,
                   default=str), encoding="utf-8")
    md = [f"# Institutional State Validation　{focus}\n"]
    for h in HORIZONS:
        rows = summary.get(f"fwd{h}w", {})
        md += [f"## Forward {h}W\n",
               "| State | n | Mean Ret | WinRate | MFE | MAE |",
               "| :-- | --: | --: | --: | --: | --: |"]
        for state, v in rows.items():
            md.append(f"| {state} | {v['n']} | {v['mean_return']:.2%} | "
                      f"{v['win_rate']:.2%} | {v['mean_mfe']:.2%} | "
                      f"{v['mean_mae']:.2%} |")
    (out_dir / f"state_validation_{focus}_{stamp}.md").write_text(
        "\n".join(md), encoding="utf-8")
    print(f"State Validation 已保存: Report/QCFP_MTF/validation/"
          f"state_validation_{focus}_{stamp}.{{md,json}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
