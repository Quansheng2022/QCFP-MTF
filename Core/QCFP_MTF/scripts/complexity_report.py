#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.7 —— Complexity Budget Report（复杂度预算）

读取最近一次 permission_fsm_ablation JSON，对每个治理/零售模块输出
    Marginal Utility + 判定（KEEP / REVIEW / DROP）
防止"系统越来越复杂，但边际收益越来越低"。

用法：python Core/QCFP_MTF/scripts/complexity_report.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.governance.complexity_budget import complexity_budget


def main(argv=None) -> int:
    bt_dir = get_report_root() / "backtest"
    files = sorted(bt_dir.glob("permission_fsm_ablation_*.json"),
                   key=lambda p: p.stat().st_mtime)
    if not files:
        print("❌ 无 Ablation JSON（先运行 permission_fsm_ablation.py）")
        return 1
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    budget = complexity_budget(data)
    out_dir = bt_dir
    stamp = datetime.now().strftime("%Y%m%d")
    (out_dir / f"complexity_budget_{stamp}.json").write_text(
        json.dumps(budget, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    md = ["# QCFP-MTF Complexity Budget\n",
          f"- 数据源：{files[-1].name}　复杂度评分："
          f"{budget['complexity_score']}（{budget['keep']}/{budget['total']} KEEP）\n",
          "| 模块 | 判定 |", "| :-- | :-- |"]
    for k, v in budget["verdicts"].items():
        md.append(f"| {k} | {v} |")
    md += ["\n## 建议移除/复查\n",
           "- " + (", ".join(budget["drop_candidates"])
                   if budget["drop_candidates"] else "无") + "\n"]
    (out_dir / f"complexity_budget_{stamp}.md").write_text(
        "\n".join(md), encoding="utf-8")
    print(f"Complexity Budget：评分 {budget['complexity_score']}，"
          f"待复查 {budget['drop_candidates']}")
    print(f"报告已保存: complexity_budget_{stamp}.{{md,json}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
