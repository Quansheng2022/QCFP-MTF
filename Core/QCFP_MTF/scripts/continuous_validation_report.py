#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— Continuous Validation Report（持续验证与安全状态报告）

把监控指标聚合为 NORMAL / WARNING / SAFE_MODE / HALTED 并给出建议。

用法：
    python Core/QCFP_MTF/scripts/continuous_validation_report.py \
        [--metrics-file metrics.json] \
        [--replay-consistent|--no-replay-consistent] \
        [--ledger-ok|--no-ledger-ok] [--stock 01951]

metrics-file：JSON，字段示例（缺省自动填 0）：
    data_missing_rate / pit_grade / settings_drift / permission_flip_rate /
    wave_capture_trend / slippage_ratio / liquidity_flag / mfe_bias /
    mae_bias / false_entry_rate / governance_violations /
    ledger_integrity / replay_consistent / risk_budget_breach / abnormal_market
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
from QCFP_MTF.safety.continuous_validation import continuous_validation, \
    validation_to_md


DEFAULT_METRICS = {
    "data_missing_rate": None,
    "pit_grade": None,
    "settings_drift": 0.0,
    "permission_flip_rate": 0.0,
    "wave_capture_trend": 1.0,
    "slippage_ratio": 1.0,
    "liquidity_flag": "LIQUIDITY_OK",
    "mfe_bias": 0.0,
    "mae_bias": 0.0,
    "false_entry_rate": 0.0,
    "governance_violations": False,
    "ledger_integrity": None,
    "replay_consistent": None,
    "risk_budget_breach": 0.0,
    "abnormal_market": False,
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 持续验证报告")
    parser.add_argument("--stock", default="")
    parser.add_argument("--metrics-file", default=None)
    parser.add_argument("--replay-consistent", dest="replay", action="store_true")
    parser.add_argument("--no-replay-consistent", dest="replay",
                        action="store_false")
    parser.set_defaults(replay=None)
    parser.add_argument("--ledger-ok", dest="ledger", action="store_true")
    parser.add_argument("--no-ledger-ok", dest="ledger", action="store_false")
    parser.set_defaults(ledger=None)
    args = parser.parse_args(argv)
    logger = setup_logger("continuous_validation_report",
                          log_file="continuous_validation_report.log",
                          mode="a")
    metrics = dict(DEFAULT_METRICS)
    if args.metrics_file:
        metrics.update(json.loads(Path(args.metrics_file).read_text(
            encoding="utf-8")))
    if args.replay is not None:
        metrics["replay_consistent"] = args.replay
    if args.ledger is not None:
        metrics["ledger_integrity"] = args.ledger
    result = continuous_validation(metrics)
    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stock": args.stock,
        "validation": result.as_dict(),
    }
    report_root = get_report_root() / "continuous_validation"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    suffix = f"_{args.stock}" if args.stock else ""
    json_path = report_root / f"continuous_validation{suffix}_{stamp}.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2,
                                    default=str), encoding="utf-8")
    md = validation_to_md(result)
    md_path = report_root / f"continuous_validation{suffix}_{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    print(md)
    logger.info(f"ContinuousValidation status={result.status} "
                f"triggered={result.triggered}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
