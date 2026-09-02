#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 2.7 —— Stress Scenario Report（极端情景压力）"""

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
from QCFP_MTF.stress.engine import stress_scenarios


def main(argv=None) -> int:
    bt_dir = get_report_root() / "backtest"
    files = sorted(bt_dir.glob("equity_*.csv"),
                   key=lambda p: p.stat().st_mtime)
    if not files:
        print("❌ 无回测 equity（先运行 backtest_runner）")
        return 1
    bt = pd.read_csv(files[-1])
    port = bt.groupby("week_end")["pnl"].mean().sort_index()
    returns = port.to_numpy()
    n = max(5, len(returns))
    scenarios = stress_scenarios(returns, n=n)
    out_dir = get_report_root() / "stress"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (out_dir / f"stress_{stamp}.json").write_text(
        json.dumps(scenarios, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Stress Scenario Report：")
    for s in scenarios:
        print(f"  {s['name']}: MDD {s['mdd']:.2%} / 恢复 {s['recovery_days']} 周")
    return 0


if __name__ == "__main__":
    sys.exit(main())
