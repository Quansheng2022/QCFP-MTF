#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.7 —— Failure Mode Report（失败模式数据库）

读取 Trade Ledger + Counterfactual，自动归类 F01–F12，
输出 Failure Rate / Cost / Frequency / by Regime / by Module。

用法：python Core/QCFP_MTF/scripts/failure_report.py [--stock 01951]
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

from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.failure.failure_modes import (FailureModeDB, classify_failure,
                                            classify_miss)


def _latest(pattern):
    files = sorted(pattern, key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF Failure Report")
    parser.add_argument("--stock", default="01951")
    args = parser.parse_args(argv)
    root = get_report_root()
    trade_file = _latest((root / "retail_swing").glob(
        f"retail_swing_{args.stock}_*.json"))
    counter_file = _latest((root / "counterfactual").glob(
        f"counterfactual_{args.stock}_*.json"))
    db = FailureModeDB()
    trades = []
    if trade_file:
        trades = json.loads(trade_file.read_text(encoding="utf-8")).get(
            "trades", [])
        for t in trades:
            for code in classify_failure(t):
                db.record(code, stock=t.get("stock_code"),
                          date=t.get("entry_date"), regime="Sideway",
                          module="retail_swing", cost=t.get("net_return"))
    misses = []
    if counter_file:
        misses = json.loads(counter_file.read_text(encoding="utf-8")).get(
            "missed", [])
        for m in misses:
            db.record(classify_miss(m.get("reason")),
                      stock=m.get("stock_code"), date=m.get("decision_date"),
                      regime="Sideway", module="counterfactual",
                      cost=m.get("gain"))
    summary = db.summary()
    out_dir = root / "failure"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (out_dir / f"failure_{args.stock}_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "summary": summary,
                    "records": db.records},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    md = [f"# QCFP-MTF Failure Mode Report　{args.stock}\n",
          f"- 交易样本：{len(trades)} 笔；错失样本：{len(misses)} 个\n",
          "## 失败模式分布\n",
          "| 模式 | 次数 |", "| :-- | --: |"]
    for code, n in sorted(summary["by_code"].items()):
        md.append(f"| {code}（{code in ('NONE',) and '正常' or ''}） | {n} |")
    md += ["\n## 按 Regime / Module\n",
           f"- by_regime：{summary['by_regime']}",
           f"- by_module：{summary['by_module']}",
           f"- 平均失败成本：{summary['mean_cost']}\n"]
    (out_dir / f"failure_{args.stock}_{stamp}.md").write_text(
        "\n".join(md), encoding="utf-8")
    print(f"Failure Report 已保存: failure_{args.stock}_{stamp}.{{md,json}}")
    print(f"失败模式分布：{summary['by_code']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
