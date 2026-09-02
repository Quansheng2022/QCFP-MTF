#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
源码收集工具
将 run_daily_TA_workflow.py 及其 Core 中调用的脚本合并到 temp 目录下的文本文件。
"""

import os
import sys
import ast
import re
from pathlib import Path

# 项目根目录（当前脚本位于 Code_utl 子目录，上一级即为根目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = PROJECT_ROOT / "Core"
TEMP_DIR = PROJECT_ROOT / "temp"
OUTPUT_FILE = TEMP_DIR / "run_daily_TA_workflow_source_code.txt"
MAIN_SCRIPT = PROJECT_ROOT / "run_daily_TA_workflow.py"


def parse_script_list(main_script_path):
    """
    从主控脚本中解析 SCRIPT_LIST 变量，返回脚本文件名列表。
    使用 ast 模块安全解析。
    """
    try:
        with open(main_script_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "SCRIPT_LIST":
                        # 确保值是列表
                        if isinstance(node.value, ast.List):
                            # 提取所有字符串元素
                            scripts = []
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    scripts.append(elt.value)
                            return scripts
                        else:
                            raise ValueError("SCRIPT_LIST 不是一个列表字面量")
        raise ValueError("未找到 SCRIPT_LIST 定义")
    except Exception as e:
        print(f"解析 SCRIPT_LIST 失败: {e}")
        sys.exit(1)


def collect_source_code():
    """主收集流程"""
    # 确保 temp 目录存在
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # 检查主控脚本是否存在
    if not MAIN_SCRIPT.exists():
        print(f"错误：找不到主控脚本 {MAIN_SCRIPT}")
        sys.exit(1)

    # 解析需要收集的子脚本列表
    script_list = parse_script_list(MAIN_SCRIPT)
    print(f"解析到 {len(script_list)} 个子脚本")

    # 准备输出
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
        # 写入头部信息
        out_f.write("=" * 80 + "\n")
        out_f.write(f"源码收集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out_f.write(f"项目根目录: {PROJECT_ROOT}\n")
        out_f.write("=" * 80 + "\n\n")

        # 1. 写入主控程序
        out_f.write(f"{'=' * 80}\n")
        out_f.write(f"文件: {MAIN_SCRIPT.relative_to(PROJECT_ROOT)}\n")
        out_f.write(f"{'=' * 80}\n\n")
        with open(MAIN_SCRIPT, "r", encoding="utf-8") as main_f:
            out_f.write(main_f.read())
        out_f.write("\n\n")

        # 2. 依次写入 Core 中的子脚本
        for script_name in script_list:
            script_path = CORE_DIR / script_name
            out_f.write(f"{'=' * 80}\n")
            out_f.write(f"文件: Core/{script_name}\n")
            out_f.write(f"{'=' * 80}\n\n")
            if not script_path.exists():
                out_f.write(f"[警告] 文件不存在: {script_path}\n\n")
                print(f"警告：{script_path} 不存在")
            else:
                with open(script_path, "r", encoding="utf-8") as sub_f:
                    out_f.write(sub_f.read())
            out_f.write("\n\n")

    print(f"源码收集完成，输出文件: {OUTPUT_FILE}")


if __name__ == "__main__":
    # 需要 datetime 用于时间戳
    from datetime import datetime
    collect_source_code()