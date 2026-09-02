#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 2.7 —— Capacity / Market Impact Report（可执行性）"""

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

from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.data.loader import load_kline
from QCFP_MTF.execution.capacity import capacity_assessment


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Capacity Report")
    p.add_argument("--stock", required=True)
    p.add_argument("--capital", type=float, default=5_000_000.0)
    args = p.parse_args(argv)
    weekly_kl = load_kline("weekly", stocks=[args.stock])
    wk = weekly_kl[weekly_kl["stock_code"] == args.stock]
    if wk.empty:
        print(f"❌ {args.stock} 无周线数据")
        return 1
    adv = float(wk["amount"].tail(20).mean()) / 5.0 if "amount" in wk \
        else float((wk["close"] * 1_000_000).tail(20).mean()) / 5.0
    vol = float(wk["close"].pct_change().tail(20).std())
    rows = []
    for participation in (0.02, 0.05, 0.10):
        assess = capacity_assessment(args.capital, adv, vol,
                                     participation=participation)
        assess["participation"] = participation
        rows.append(assess)
    out_dir = get_report_root() / "capacity"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    out = {"stock": args.stock, "capital": args.capital, "adv": round(adv, 2),
           "weekly_vol": round(vol, 4), "rows": rows}
    (out_dir / f"capacity_{args.stock}_{stamp}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{args.stock}：ADV≈{adv:,.0f}，周波动 {vol:.2%}")
    for r in rows:
        print(f"  参与率 {r['participation']:.0%} → 冲击 "
              f"{r['impact']:.2%} / 退出压力 {r['stress_exit_days']} 天 / "
              f"标记 {r['flags']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
