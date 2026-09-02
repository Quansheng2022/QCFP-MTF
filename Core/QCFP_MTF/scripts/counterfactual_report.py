#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.7 —— Counterfactual Decision Analysis（为什么没买）

对每个"模型未参与"的大波段，回溯当时决策：
    Permission / primary_reason / FSM → 归因错失原因
    （PERMISSION_BLOCK / WATCH / SETUP_ABSENT / COOLDOWN / RISK / OTHER）

用法：python Core/QCFP_MTF/scripts/counterfactual_report.py
        [--stock 01951] [--min-gain 0.5]
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd

from QCFP_MTF.backtest.engine import run_backtest
from QCFP_MTF.backtest.wave_capture import find_waves, wave_capture_metrics
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_kline


def _classify(primary_reason, permission) -> str:
    if primary_reason in ("HARD_EXIT", "FORCED_DELEVERAGE", "STOP_EXIT",
                          "RISK_EXIT"):
        return "RISK"
    if permission == "BLOCK":
        return "PERMISSION_BLOCK"
    if permission == "WATCH":
        return "PERMISSION_WATCH"
    if primary_reason in ("COOLDOWN",):
        return "COOLDOWN"
    if primary_reason == "SETUP_ABSENT":
        return "SETUP_ABSENT"
    return "OTHER"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Counterfactual Analysis")
    parser.add_argument("--stock", default=None)
    parser.add_argument("--min-gain", type=float, default=0.5)
    args = parser.parse_args(argv)
    settings = load_qcfp_settings()
    weekly_kl = load_kline("weekly")
    # 用最新台账行重建 bt 信号源：直接以 ledger 的 final_target 为 target 太重；
    # 反事实关注"错过时点的决策"，故直接查 Ledger 在波段窗口内的决策。
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT stock_code, decision_date, institutional_permission, "
            "primary_reason, next_fsm_state, final_target "
            "FROM qcfp_decision_ledger WHERE status='ACTIVE'").fetchall()
    finally:
        conn.close()
    ledger = pd.DataFrame([dict(r) for r in rows])
    waves = find_waves(weekly_kl, min_gain=args.min_gain, window=26)
    if args.stock:
        waves = waves[waves["stock_code"] == args.stock]
    if ledger.empty:
        print("❌ 台账为空（先运行 shadow_mode）")
        return 1
    # 参与状态：以台账 target>0 表示参与
    ledger["decision_dt"] = pd.to_datetime(ledger["decision_date"])
    missed = []
    for _, w in waves.iterrows():
        code = w["stock_code"]
        seg = ledger[(ledger["stock_code"] == code)
                     & (ledger["decision_dt"] >= pd.Timestamp(w["start_date"])
                        - timedelta(days=30))
                     & (ledger["decision_dt"] <= pd.Timestamp(w["peak_date"]))]
        seg = seg.sort_values("decision_dt")
        if seg.empty:
            missed.append({"wave_id": f"{code}_{w['start_date']}",
                           "stock_code": code, "gain": w["gain"],
                           "reason": "NO_DECISION_RECORD",
                           "permission": "?", "primary_reason": "?"})
            continue
        first = seg.iloc[0]
        participated = bool((seg["final_target"] > 0).any())
        if not participated:
            missed.append({
                "wave_id": f"{code}_{w['start_date']}",
                "stock_code": code, "gain": round(float(w["gain"]), 4),
                "reason": _classify(first["primary_reason"],
                                    first["institutional_permission"]),
                "permission": first["institutional_permission"],
                "primary_reason": first["primary_reason"],
                "decision_date": first["decision_date"],
            })
    df = pd.DataFrame(missed)
    out_dir = get_report_root() / "counterfactual"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    focus = args.stock or "all"
    base = f"counterfactual_{focus}_{stamp}"
    df.to_csv(out_dir / f"{base}.csv", index=False, encoding="utf-8-sig")
    summary = {}
    if not df.empty:
        summary = {"n_missed": int(len(df)),
                   "by_reason": df["reason"].value_counts().to_dict(),
                   "mean_gain": round(float(df["gain"].mean()), 4),
                   "ge50pct": int((df["gain"] >= 0.5).sum())}
    (out_dir / f"{base}.json").write_text(
        json.dumps({"generated_at": stamp, "summary": summary,
                    "missed": df.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    print(f"Counterfactual Report 已保存: {base}.{{md,csv,json}}")
    print(f"错失 {summary.get('n_missed', 0)} 个波段，"
          f"原因分布：{summary.get('by_reason', {})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
