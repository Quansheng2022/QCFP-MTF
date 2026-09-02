#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— Research Experiment Registry（研究实验注册中心）

防止"测试 100 个版本只报告最好的一个"：
    未注册实验 → 不得作为正式研究结论（assert_registered）。

用法：
    # 登记实验
    python Core/QCFP_MTF/scripts/research_registry_report.py register \
        EXP-00001 --hypothesis "Permission 降低错误交易" \
        --baseline "Wave Only" --treatment "Wave+Permission" \
        --dataset "HK 2020-2026" --pit-grade B --oos-window 2023-2026

    # 输出报告
    python Core/QCFP_MTF/scripts/research_registry_report.py report

    # 校验实验已登记（未登记 → 非零退出）
    python Core/QCFP_MTF/scripts/research_registry_report.py check EXP-00001
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

from QCFP_MTF.ablation.statistical import ExperimentRegistry
from QCFP_MTF.common.paths import get_report_root


def _registry_path():
    d = get_report_root() / "research_registry"
    d.mkdir(parents=True, exist_ok=True)
    return d / "registry.json"


def _load():
    p = _registry_path()
    if p.exists():
        return ExperimentRegistry(
            experiments=json.loads(p.read_text(encoding="utf-8")))
    return ExperimentRegistry()


def _save(reg):
    _registry_path().write_text(
        json.dumps(reg.experiments, ensure_ascii=False, indent=2,
                   default=str), encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="QCFP-MTF 研究实验注册中心")
    sub = p.add_subparsers(dest="cmd", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("experiment_id")
    reg.add_argument("--hypothesis", required=True)
    reg.add_argument("--baseline", required=True)
    reg.add_argument("--treatment", required=True)
    reg.add_argument("--dataset", default="")
    reg.add_argument("--pit-grade", default="C")
    reg.add_argument("--oos-window", default="")
    reg.add_argument("--selection-rule", default="best_ci")
    chk = sub.add_parser("check")
    chk.add_argument("experiment_id")
    rep = sub.add_parser("report")
    args = p.parse_args(argv)
    reg_obj = _load()
    if args.cmd == "register":
        reg_obj.register_research(
            args.experiment_id, args.hypothesis, args.baseline,
            args.treatment, args.dataset, pit_grade=args.pit_grade,
            oos_window=args.oos_window, selection_rule=args.selection_rule)
        _save(reg_obj)
        print(f"✅ 已登记 {args.experiment_id}")
        return 0
    if args.cmd == "check":
        try:
            reg_obj.assert_registered(args.experiment_id)
            print(f"✅ {args.experiment_id} 已登记")
            return 0
        except ValueError as exc:
            print(f"❌ {exc}")
            return 2
    # report
    r = reg_obj.report()
    lines = [
        "# Research Experiment Registry",
        "",
        f"**实验总数：{r['experiment_count']}**　候选版本数："
        f"{r['candidate_count']}　显著数：{r['significant_count']}",
        "",
    ]
    for e in r["research_records"]:
        lines.append(f"- `{e['experiment_id']}`：{e.get('hypothesis','')}"
                     f"（{e.get('baseline','')}→{e.get('treatment','')}）"
                     f" dataset={e.get('dataset','')} pit={e.get('pit_grade','')}"
                     f" oos={e.get('oos_window','')}")
    lines += ["", "## 挑选风险", "",
              f"- {reg_obj.check_selection_bias()['reason']}", ""]
    md = "\n".join(lines)
    stamp = datetime.now().strftime("%Y%m%d")
    md_path = _registry_path().parent / \
        f"research_registry_{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
