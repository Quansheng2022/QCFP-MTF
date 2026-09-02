#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 流程治理工作流主控（Flow Governance Engineering）

按 Sprint 顺序执行 10 项流程治理的静态部分（不依赖数据库/网络）：
    Sprint A（1-3）：spec / baseline-init / baseline-check / traceability
    Sprint B（4-6）：contract-impl / contract-accept / impact（需输入文件）
    Sprint C（7-8）：review / patch-audit（需输入文件）
    Sprint D（9-10）：judge / promote（需证据包）

用法：
    python run_QCFP_Governance_workflow.py            # Sprint A + judge
    python run_QCFP_Governance_workflow.py --sprint A
    python run_QCFP_Governance_workflow.py --sprint all
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "Log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

GOV_FLOW = (PROJECT_ROOT / "Core" / "QCFP_MTF" / "scripts"
            / "governance_flow.py")

# Sprint → governance_flow 子命令（B/C/D 中需要外部输入文件的命令不自动执行）
SPRINT_STEPS = {
    "A": ["spec", "baseline-init", "baseline-check", "traceability"],
    "B": ["contract-impl", "contract-accept", "impact"],
    "C": ["review", "patch-audit"],
    "D": ["judge", "promote"],
}


def setup_logger():
    logger = logging.getLogger("runQCFPGovernanceWorkflow")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(LOG_DIR / "run_qcfp_governance_workflow.log",
                             mode="a", encoding="utf-8")
    ch = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 流程治理工作流")
    parser.add_argument("--sprint", default="A",
                        choices=("A", "B", "C", "D", "all"))
    parser.add_argument("--judge-dir", default="",
                        help="Pure Judge 证据包目录（默认 audit/bundle）")
    args = parser.parse_args(argv)
    logger = setup_logger()
    logger.info("=" * 60)
    logger.info("QCFP-MTF 流程治理工作流启动")
    logger.info(f"Sprint: {args.sprint}")

    sprints = ("A", "B", "C", "D") if args.sprint == "all" \
        else (args.sprint,)
    steps = []
    for s in sprints:
        steps += SPRINT_STEPS[s]
    if "judge" in steps and args.judge_dir:
        steps[steps.index("judge")] = f"judge {args.judge_dir}"

    env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    failed = []
    for step in steps:
        logger.info(f"执行: governance_flow.py {step}")
        cmd = [sys.executable, str(GOV_FLOW)] + step.split()
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT),
                                env=env, capture_output=True, text=True)
        if result.stdout:
            logger.info(result.stdout.strip())
        if result.returncode != 0:
            logger.error(f"❌ {step} 失败（rc={result.returncode}）")
            if result.stderr:
                logger.error(result.stderr.strip()[:2000])
            failed.append(step)
        else:
            logger.info(f"✅ {step} 通过")
    if failed:
        logger.error(f"流程治理工作流结束，失败步骤: {failed}")
        return 1
    logger.info("流程治理工作流全部完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())

