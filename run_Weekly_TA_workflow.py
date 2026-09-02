#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import logging
import argparse
from datetime import datetime

# ========== 配置 ==========
LOG_DIR = "log"
os.makedirs(LOG_DIR, exist_ok=True)

# 需要顺序执行的脚本列表（位于 Core 目录下）
SCRIPT_LIST = [
    "Weekly_TA2A_Aggregate_Indicators_akshare.py",
    "Weekly_TA2B_Calculate_indicators.py",
    "Weekly_TA3_Analyze_Indicators_Plot.py",
    "Weekly_TA4A_Aggregate_MoneyFlow.py",
    "Weekly_TA4B_Analyze_MoneyFlow.py",
    "Weekly_TA5_MergePDF.py",
]

# ========== 日志配置 ==========
# 控制程序日志：同时输出到文件和控制台
logger = logging.getLogger("WeeklyWorkflow")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# 文件 Handler
file_handler = logging.FileHandler(
    os.path.join(LOG_DIR, "run_weekly_workflow.log"),
    encoding="utf-8",
    mode="a"  # 追加模式，保留历史
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 控制台 Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ========== 子脚本执行函数 ==========
def run_script(script_name: str, extra_args: list, date_str: str = None) -> bool:
    """
    执行单个脚本，将 stdout/stderr 记录到对应的日志文件。
    返回 True 表示成功，False 表示失败。
    """
    script_path = os.path.join("Core","Weekly", script_name)
    if not os.path.isfile(script_path):
        logger.error(f"脚本不存在: {script_path}")
        return False

    # 子脚本日志文件路径（以脚本名命名）
    log_file_path = os.path.join(LOG_DIR, f"{script_name}.log")

    # 构建命令
    cmd = [sys.executable, script_path] + extra_args
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"   # 强制 UTF-8 输出
    if date_str:
        env["WORKFLOW_DATE"] = date_str  # 通过环境变量传递日期给子脚本

    logger.info(f"开始运行 {script_name}，日志写入 {log_file_path}")

    try:
        # 以写入模式打开子脚本日志文件（每次运行覆盖）
        with open(log_file_path, "w", encoding="utf-8") as f_log:
            # 启动子进程，stdout 和 stderr 合并后重定向到日志文件
            process = subprocess.Popen(
                cmd,
                stdout=f_log,
                stderr=subprocess.STDOUT,  # 合并错误输出
                cwd=os.getcwd(),            # 工作目录为项目根目录
                env=env,
                text=True,
                encoding="utf-8"
            )
            # 等待进程结束
            returncode = process.wait()
        
        if returncode != 0:
            logger.error(f"{script_name} 执行失败，返回码 {returncode}")
            return False
        else:
            logger.info(f"{script_name} 执行成功")
            return True

    except Exception as e:
        logger.exception(f"运行 {script_name} 时发生异常: {e}")
        return False

# ========== 参数解析 ==========
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="TA_Workflow 周交易数据分析控制程序"
    )
    parser.add_argument(
        "--date",
        help="指定分析日期，格式 YYYY-MM-DD，将通过环境变量 WORKFLOW_DATE 传递给每个脚本"
    )
    return parser.parse_args()

# ========== 主流程 ==========
def main():
    args = parse_arguments()
    date_str = args.date

    logger.info("=" * 60)
    logger.info("TA_Workflow 周交易数据分析控制程序启动")
    logger.info(f"当前工作目录: {os.getcwd()}")
    logger.info(f"Python 解释器: {sys.executable}")
    if date_str:
        logger.info(f"传递日期: {date_str}")

    # 额外的命令行参数（如果有）
    extra_args = []
    # 此处可以根据需要向子脚本传递更多参数，目前仅支持 --date 通过环境变量传递

    for script in SCRIPT_LIST:
        success = run_script(script, extra_args, date_str)
        if not success:
            logger.error("流程因脚本执行失败而终止")
            sys.exit(1)

    logger.info("所有周交易数据分析脚本已按顺序成功执行完毕")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()