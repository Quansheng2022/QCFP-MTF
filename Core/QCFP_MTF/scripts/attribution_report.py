#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— P&L Attribution Report（收益来源归因报告）

把总收益拆解为：Market Beta / Wave / Entry Timing / Sizing / Exit Timing /
Regime / Sector / Risk Avoidance / Execution Cost / Slippage / Alpha，
并归入 Beta / Wave / Timing / Sizing / Risk_Avoidance / Execution / Alpha。

用法：
    python Core/QCFP_MTF/scripts/attribution_report.py \
        --stock 01951 --trades-file trades.json \
        [--blocked-file blocked.json] [--returns-file ret.json] \
        [--benchmark-file bench.json]

trades-file：JSON 列表，每项含 net_return/gross_return/exposure/
    entry_delay_weeks/exit_delay_weeks/setup_type/regime（可选字段缺省 0）。
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

from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.performance.attribution import attribution_report, \
    attribution_to_md


def _load_json_list(path) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("trades", [])


def _load_returns(path):
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [float(x) for x in data]
    for key in ("portfolio_return", "returns", "weekly_return"):
        if key in data:
            return [float(x) for x in data[key]]
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF P&L 归因报告")
    parser.add_argument("--stock", required=True)
    parser.add_argument("--trades-file", required=True)
    parser.add_argument("--blocked-file", default=None)
    parser.add_argument("--returns-file", default=None)
    parser.add_argument("--benchmark-file", default=None)
    parser.add_argument("--sector-contribution", type=float, default=0.0)
    parser.add_argument("--slippage-contribution", type=float, default=0.0)
    parser.add_argument("--total-return", type=float, default=None)
    args = parser.parse_args(argv)
    logger = setup_logger("attribution_report",
                          log_file="attribution_report.log", mode="a")
    trades = _load_json_list(args.trades_file)
    blocked = _load_json_list(args.blocked_file) if args.blocked_file else []
    rets = _load_returns(args.returns_file)
    bench = _load_returns(args.benchmark_file)
    report = attribution_report(
        portfolio_returns=rets, benchmark_returns=bench,
        trades=trades, blocked_trades=blocked,
        sector_contribution=args.sector_contribution,
        slippage_contribution=args.slippage_contribution,
        total_return=args.total_return)
    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stock": args.stock,
        "report": report,
    }
    report_root = get_report_root() / "attribution"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    json_path = report_root / f"attribution_{args.stock}_{stamp}.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2,
                                    default=str), encoding="utf-8")
    md = attribution_to_md(report)
    md_path = report_root / f"attribution_{args.stock}_{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    print(md)
    logger.info(f"{args.stock} total={report['total_return']:.2%} "
                f"alpha={report['buckets']['Alpha']:.2%} trades="
                f"{report['n_trades']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
