#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— Counterfactual Portfolio Report（组合反事实报告）

Actual Portfolio vs No Permission / No Wave / No Risk / No Portfolio
Governance，比较 Return/MDD/Turnover/MFE Capture/MAE/Capital Utilization/
Tail Loss，突出 Risk Alpha / Loss Avoidance Alpha。

用法：
    python Core/QCFP_MTF/scripts/counterfactual_portfolio.py \
        --variants-file variants.json [--stock 01951]

variants-file：{"Actual": {"returns": [...], "turnover": 1.2, ...},
                "No Permission": {...}, ...}
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

from QCFP_MTF.ablation.portfolio_counterfactual import \
    counterfactual_to_md, portfolio_counterfactual
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 组合反事实报告")
    parser.add_argument("--variants-file", required=True)
    parser.add_argument("--stock", default="")
    args = parser.parse_args(argv)
    logger = setup_logger("counterfactual_portfolio",
                          log_file="counterfactual_portfolio.log", mode="a")
    variants = json.loads(Path(args.variants_file).read_text(
        encoding="utf-8"))
    report = portfolio_counterfactual(variants)
    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stock": args.stock,
        "report": report,
    }
    report_root = get_report_root() / "counterfactual_portfolio"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    suffix = f"_{args.stock}" if args.stock else ""
    json_path = report_root / \
        f"counterfactual_portfolio{suffix}_{stamp}.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2,
                                    default=str), encoding="utf-8")
    md = counterfactual_to_md(report)
    md_path = report_root / f"counterfactual_portfolio{suffix}_{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    print(md)
    logger.info(f"CounterfactualPortfolio actual={report['actual']} "
                f"risk_alpha={len(report['risk_alpha'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
