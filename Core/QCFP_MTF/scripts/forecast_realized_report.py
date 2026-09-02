#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 2.7 —— Forecast-to-Realized Monitor Report"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.monitoring.forecast_realized import (calibration_summary,
                                                   compare_trade,
                                                   _expected_from_quality)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Forecast-to-Realized Report")
    p.add_argument("--stock", default="01951")
    args = p.parse_args(argv)
    root = get_report_root() / "retail_swing"
    files = sorted(root.glob(f"retail_swing_{args.stock}_*.json"),
                   key=lambda x: x.stat().st_mtime)
    if not files:
        print("❌ 无 Trade Ledger（先运行 retail_swing_report.py）")
        return 1
    trades = json.loads(files[-1].read_text(encoding="utf-8")).get("trades", [])
    comparisons = []
    for t in trades:
        expected = _expected_from_quality(
            t.get("trade_quality", 50.0), holding_hint=1.0)
        comparisons.append(compare_trade(t, expected))
    summary = calibration_summary(comparisons)
    out_dir = get_report_root() / "monitoring"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    out = {"generated_at": stamp, "stock": args.stock, "summary": summary,
           "comparisons": comparisons}
    (out_dir / f"forecast_realized_{args.stock}_{stamp}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Forecast-Realized Report 已保存: {args.stock}_{stamp}.json")
    print(f"MFE 平均误差 {summary.get('mfe_mean_error')}；"
          f"MAE 平均误差 {summary.get('mae_mean_error')}；"
          f"持有期平均误差 {summary.get('holding_mean_error')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
