#!/usr/bin/env python
# coding: utf-8

"""
QCFP-MTF 2.1.1 工作流主控（P0 阶段）

按 SCRIPT_LIST 顺序执行 P0 步骤：
    1. init_db            —— 创建 qcfp_* 核心表
    2. audit_coverage     —— 数据覆盖度审计
    3. check_data_quality —— 数据质量检测（A/B/C/D）

用法：
    python run_QCFP_MTF_workflow.py [--date YYYY-MM-DD] [--stock 00700]
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "Log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_LIST = [
    "init_db.py",
    "audit_coverage.py",
    "check_data_quality.py",
    "structural_engine.py",      # P1：季度结构引擎
    "monthly_behavior_engine.py",  # P2：月线行为引擎
    "weekly_tactical_engine.py",   # P3：周线战术引擎
    "daily_tactical_engine.py",    # L4：日线战术引擎（V14，诊断层，不改变 Q/M/W）
    "mtf_fusion_engine.py",        # P4：多周期融合引擎
    "decision_engine.py",          # P5：DSS 决策引擎
    "validate_structural.py",    # P1：结构引擎交叉验证
]
SCRIPT_DIR = PROJECT_ROOT / "Core" / "QCFP_MTF" / "scripts"


def setup_logger():
    logger = logging.getLogger("runQCFPMTFWorkflow")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    file_handler = logging.FileHandler(LOG_DIR / "run_qcfp_mtf_workflow.log",
                                       mode="a", encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s",
                                  datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def run_script(logger, script_name: str, extra_args: list, date_str: str = None) -> bool:
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        logger.error(f"脚本不存在: {script_path}")
        return False
    log_file = LOG_DIR / f"{script_name}.log"
    cmd = [sys.executable, str(script_path)] + extra_args
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if date_str:
        env["WORKFLOW_DATE"] = date_str
    logger.info(f"开始运行 {script_name}，日志写入 {log_file}")
    try:
        with open(log_file, "w", encoding="utf-8") as f_log:
            process = subprocess.Popen(
                cmd, stdout=f_log, stderr=subprocess.STDOUT,
                env=env, cwd=str(PROJECT_ROOT),
            )
            process.wait()
        if process.returncode == 0:
            logger.info(f"✅ {script_name} 完成")
            return True
        logger.error(f"❌ {script_name} 失败（退出码 {process.returncode}），详见 {log_file}")
        return False
    except Exception as e:
        logger.error(f"❌ {script_name} 执行异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="QCFP-MTF 工作流主控")
    parser.add_argument("--date", help="分析日期（如 2026-08-19），将作为 WORKFLOW_DATE 传入子脚本")
    parser.add_argument("--stock", help="仅处理指定股票代码（如 00700）")
    args = parser.parse_args()

    logger = setup_logger()
    logger.info("=" * 60)
    logger.info(f"QCFP-MTF 工作流启动: {datetime.now():%Y-%m-%d %H:%M:%S}")
    logger.info(f"日期: {args.date or '未指定'}  股票: {args.stock or '全部'}")

    extra_args = []
    if args.stock:
        extra_args += ["--stock", args.stock]

    failed = []
    for script_name in SCRIPT_LIST:
        ok = run_script(logger, script_name, extra_args, args.date)
        if not ok:
            failed.append(script_name)
        logger.info("-" * 40)

    if failed:
        logger.error(f"工作流结束，失败步骤: {failed}")
        return 1
    logger.info("QCFP-MTF 工作流全部完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
