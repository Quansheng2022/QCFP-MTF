#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— 波段事件回放（Major Rally Replay）

诊断"日线是否必需"：找出 26 周窗口涨幅 >= --min-gain 的波段，
在 T0 / +20% / +50% / +90% 四个节点回放 Q/M/W/D 四层状态，
统计"哪一层最先识别出波段"。

用法：
    python Core/QCFP_MTF/scripts/wave_replay.py [--year 2024]
        [--min-gain 0.5] [--focus 01951]
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
from QCFP_MTF.data.loader import load_kline

Q_BULLISH = {"STRUCTURAL_BULLISH", "STRUCTURAL_ACCUMULATION",
             "STRUCTURAL_BOTTOM_CANDIDATE"}


def _layer_states(conn, stock, date):
    q = conn.execute(
        "SELECT structural_regime, f_state FROM qcfp_quarterly_structural "
        "WHERE stock_code=? AND available_date<=? ORDER BY period_end DESC LIMIT 1",
        (stock, date)).fetchone()
    m = conn.execute(
        "SELECT monthly_behavior_state FROM qcfp_monthly_behavior "
        "WHERE stock_code=? AND month_end<=? ORDER BY month_end DESC LIMIT 1",
        (stock, date)).fetchone()
    w = conn.execute(
        "SELECT tactical_signal FROM qcfp_weekly_tactical "
        "WHERE stock_code=? AND week_end<=? ORDER BY week_end DESC LIMIT 1",
        (stock, date)).fetchone()
    d = conn.execute(
        "SELECT daily_state FROM qcfp_daily_tactical "
        "WHERE stock_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 1",
        (stock, date)).fetchone()
    q_regime = q["structural_regime"] if q else None
    q_ok = q_regime in Q_BULLISH
    m_ok = (m["monthly_behavior_state"] == "Improving") if m else False
    w_ok = (w["tactical_signal"] == "Breakout") if w else False
    d_state = d["daily_state"] if d else None
    d_ok = d_state in ("DAILY_BREAKOUT", "DAILY_ACCUMULATION")
    return {
        "q_regime": q_regime, "q_f": q["f_state"] if q else None, "q_ok": q_ok,
        "m_state": m["monthly_behavior_state"] if m else None, "m_ok": m_ok,
        "w_signal": w["tactical_signal"] if w else None, "w_ok": w_ok,
        "d_state": d_state, "d_ok": d_ok,
    }


def find_waves(weekly_df: pd.DataFrame, year: int, min_gain: float, focus=None):
    """按股票扫描：26 周前向收益 >= min_gain 的非重叠波段"""
    df = weekly_df.copy()
    df["week_end"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values(["stock_code", "week_end"])
    waves = []
    for code, g in df.groupby("stock_code"):
        if focus and code != focus:
            continue
        g = g.reset_index(drop=True)
        fwd = g["close"].shift(-26) / g["close"] - 1.0
        cand = [i for i, v in enumerate(fwd)
                if pd.notna(v) and v >= min_gain
                and g["week_end"].iloc[i].startswith(str(year))]
        i = 0
        while i < len(cand):
            t0 = cand[i]
            waves.append((code, g.iloc[t0], float(fwd.iloc[t0])))
            i += 1
            while i < len(cand) and cand[i] <= t0 + 26:
                i += 1
    return waves


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 波段事件回放")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--min-gain", type=float, default=0.5,
                        help="26 周前向收益阈值（默认 0.5，含 01951 的 61.6% 波段）")
    parser.add_argument("--focus", default=None, help="只看指定股票")
    args = parser.parse_args(argv)

    logger = setup_logger("wave_replay", log_file="wave_replay.log", mode="a")
    logger.info("=== 波段事件回放启动 ===")
    weekly = load_kline("weekly")
    waves = find_waves(weekly, args.year, args.min_gain, args.focus)
    logger.info(f"找到 {len(waves)} 个 {args.year} 年 26 周涨幅≥{args.min_gain:.0%} 的波段")

    conn = connect()
    rows = []
    try:
        for code, t0_row, wave_26w in waves:
            t0 = t0_row["week_end"]
            t0_close = float(t0_row["close"])
            g = weekly[weekly["stock_code"] == code].sort_values("date").reset_index(drop=True)
            g["week_end"] = pd.to_datetime(g["date"]).dt.strftime("%Y-%m-%d")
            g = g[g["week_end"] >= t0]
            peaks = {0.0: (t0, t0_close)}
            for lvl in (0.2, 0.5, 0.9):
                hit = g[g["close"] >= t0_close * (1 + lvl)]
                if not hit.empty:
                    r = hit.iloc[0]
                    peaks[lvl] = (r["week_end"], float(r["close"]))
            wave_ret = wave_26w
            for lvl, (date, price) in sorted(peaks.items()):
                st = _layer_states(conn, code, date)
                rows.append({
                    "stock": code, "t0": t0, "t0_close": round(t0_close, 4),
                    "milestone": f"+{int(lvl * 100)}%", "date": date,
                    "close": round(price, 4), "gain": round(price / t0_close - 1, 4),
                    "wave_26w_return": round(wave_ret, 4),
                    **{f"state_{k}": v for k, v in st.items()},
                })
            # 摘要：+20% 节点各层是否已识别
            st20 = _layer_states(conn, code, peaks.get(0.2, (t0, t0_close))[0])
            logger.info(
                f"{code} T0={t0} 26w={wave_ret:.1%} | +20% 节点识别: "
                f"Q={'Y' if st20['q_ok'] else 'N'}({st20['q_regime']}) "
                f"M={'Y' if st20['m_ok'] else 'N'}({st20['m_state']}) "
                f"W={'Y' if st20['w_ok'] else 'N'}({st20['w_signal']}) "
                f"D={'Y' if st20['d_ok'] else 'N'}({st20['d_state']})")
    finally:
        conn.close()

    result = pd.DataFrame(rows)
    report_root = get_report_root() / "wave_replay"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (report_root / f"wave_replay_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "year": args.year,
                    "min_gain": args.min_gain, "focus": args.focus,
                    "records": result.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    result.to_csv(report_root / f"wave_replay_{stamp}.csv",
                  index=False, encoding="utf-8-sig")
    logger.info(f"回放报告已保存: Report/QCFP_MTF/wave_replay/wave_replay_{stamp}.{{json,csv}}")
    logger.info("wave_replay 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
