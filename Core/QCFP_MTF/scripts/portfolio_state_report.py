#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 2.7 —— Portfolio State Report（组合状态）"""

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
from QCFP_MTF.portfolio.state_engine import portfolio_state, state_constraints


def main(argv=None) -> int:
    bt_dir = get_report_root() / "backtest"
    files = sorted(bt_dir.glob("equity_*.csv"),
                   key=lambda p: p.stat().st_mtime)
    if not files:
        print("❌ 无回测 equity（先运行 backtest_runner）")
        return 1
    bt = pd.read_csv(files[-1])
    rows = []
    for week, g in bt.groupby("week_end"):
        exposure = float(g["position_start"].mean())
        metrics = {
            "total_exposure": exposure,
            "cash_ratio": 1.0 - exposure,
            "sector_concentration": 0.3,
            "correlation": 0.3,
            "permission_risk_share": 0.0,
            "wave_bullish_share": 0.3,
            "market_vol": 0.2,
            "mdd_recent": 0.0,
        }
        state = portfolio_state(metrics)
        rows.append({"week_end": week, "state": state,
                     **state_constraints(state)})
    out_dir = get_report_root() / "portfolio_state"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (out_dir / f"portfolio_state_{stamp}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Portfolio State Report 已保存: {stamp}.json")
    from collections import Counter
    print("状态分布：", dict(Counter(r["state"] for r in rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
