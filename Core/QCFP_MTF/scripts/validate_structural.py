#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P1 —— 季度结构引擎交叉验证

将 qcfp_quarterly_structural 的方向与现有 hk_quarterly_chip_analysis
的 chip_flow_price_regime 方向对比（仅统计资金流可用的 2021+ 季度），
输出一致率报告。
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
from QCFP_MTF.config.settings import get, load_qcfp_settings
from QCFP_MTF.data.loader import load_derived
from QCFP_MTF.structural.structural_regime import regime_direction

BULL_KW = ["多头", "吸筹", "走强", "蓄势", "流入", "价涨", "底背离",
           "筹码偏多", "筹码走强", "共振"]
BEAR_KW = ["空头", "派发", "流出", "下跌", "顶背离", "筹码偏空",
           "回落", "反弹", "抛压"]


def chip_direction(label: str) -> str:
    if not label or not isinstance(label, str):
        return "neutral"
    score = sum(1 for k in BULL_KW if k in label) - sum(1 for k in BEAR_KW if k in label)
    if score > 0:
        return "bull"
    if score < 0:
        return "bear"
    return "neutral"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 结构引擎交叉验证")
    parser.add_argument("--stock", help="只验证指定股票")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    from QCFP_MTF.decision.versions import MODEL_VERSION
    model_version = get(settings, "model.version", MODEL_VERSION)
    logger = setup_logger("validate_structural", log_file="validate_structural.log", mode="w")

    conn = connect()
    try:
        reg = pd.read_sql_query(
            """SELECT stock_code, stock_name, period_end, structural_regime,
                      core_score, data_quality, resolve_method
               FROM qcfp_quarterly_structural""", conn)
    finally:
        conn.close()

    chip = load_derived("quarterly_chip_analysis")
    chip["period_end"] = pd.to_datetime(chip["quarter_end_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    chip = chip[["stock_code", "period_end", "institutional_flow", "chip_flow_price_regime"]]

    m = pd.merge(reg, chip, on=["stock_code", "period_end"], how="inner")
    if args.stock:
        m = m[m["stock_code"] == args.stock]
    m["regime_dir"] = m["structural_regime"].map(regime_direction)
    m["chip_dir"] = m["chip_flow_price_regime"].map(chip_direction)

    # 仅统计资金流可用（2021+）且双方方向明确（bull/bear）的季度
    usable = m[m["institutional_flow"].notna() &
               m["regime_dir"].isin(["bull", "bear"]) &
               m["chip_dir"].isin(["bull", "bear"])].copy()
    usable["agree"] = usable["regime_dir"] == usable["chip_dir"]
    usable["method"] = usable.get("resolve_method", "").fillna("")

    total_compared = len(usable)
    agree = int(usable["agree"].sum())
    rate = agree / total_compared if total_compared else None

    logger.info(f"可比季度: {total_compared}（有资金流 + 双方方向明确）")
    if total_compared:
        logger.info(f"方向一致: {agree} / {total_compared} = {rate:.1%}")

    # 验收口径：direct（当季 C/F/P 证据直接判定）一致率 >= 70%
    direct = usable[usable["method"] == "direct"]
    d_total = len(direct)
    d_agree = int(direct["agree"].sum()) if d_total else 0
    d_rate = d_agree / d_total if d_total else None
    if d_total:
        logger.info(f"direct 证据行: {d_agree} / {d_total} = {d_rate:.1%}")
        if d_rate is not None and d_rate >= 0.70:
            logger.info("direct 一致率达标（≥70%）✅")
        else:
            logger.warning(f"direct 一致率 {d_rate:.1%} 低于验收线 70%，建议检查阈值")
    else:
        logger.warning("无可比 direct 证据行")
    n_hold = len(usable) - d_total
    logger.info(f"hold 保持行（参考，路径依赖）: {n_hold} 行，一致 {int(usable['agree'].sum()) - d_agree}")

    report_root = get_report_root() / "structural"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    usable.to_csv(report_root / f"validate_{stamp}.csv", index=False, encoding="utf-8-sig")
    (report_root / f"validate_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "model_version": model_version,
                    "total_compared": total_compared, "agree": agree,
                    "agreement_rate": rate,
                    "direct_compared": d_total, "direct_agree": d_agree,
                    "direct_agreement_rate": d_rate,
                    "records": usable.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info(f"验证报告已保存: Report/QCFP_MTF/structural/validate_{stamp}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
