#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
收集 TA_Workflow 项目核心源代码
将主控脚本 run_weekly_TA_workflow.py 和 Core 目录下的所有子脚本
合并到一个文本文件中，便于查阅或备份。

使用方法：
    将本脚本放在项目根目录下的 Code_utl 文件夹中，
    直接运行即可。

输出文件：
    ./temp/run_weekly_TA_workflow_source_code.txt
"""

import os
import sys
import re
import ast
from datetime import datetime


def get_project_root():
    """
    根据本脚本所在位置推断项目根目录。
    假设本脚本位于项目根目录下的 Code_utl 子目录中。
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    return project_root


def extract_script_list(main_file_path):
    """
    从主控文件 run_weekly_TA_workflow.py 中提取 SCRIPT_LIST 变量的值。
    返回包含子脚本文件名的列表。
    """
    with open(main_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 使用正则匹配 SCRIPT_LIST = [ ... ]，支持多行和注释
    pattern = r'SCRIPT_LIST\s*=\s*(\[.*?\])'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        raise ValueError("在主控文件中未找到 SCRIPT_LIST 定义")

    list_str = match.group(1)
    # 安全解析为 Python 列表
    script_list = ast.literal_eval(list_str)
    return script_list


def collect_source_code(project_root, output_path):
    """
    收集所有源代码文件并将其内容写入输出文件。
    """
    main_file = os.path.join(project_root, "run_weekly_TA_workflow.py")
    if not os.path.isfile(main_file):
        print(f"错误：主控文件不存在 - {main_file}")
        sys.exit(1)

    # 提取 SCRIPT_LIST
    try:
        script_list = extract_script_list(main_file)
        print(f"解析到 {len(script_list)} 个子脚本：{script_list}")
    except Exception as e:
        print(f"解析 SCRIPT_LIST 失败：{e}")
        sys.exit(1)

    # 构建待收集文件列表（主控文件 + Core 下的子脚本）
    files_to_collect = [main_file]
    core_dir = os.path.join(project_root, "Core")
    for script in script_list:
        script_path = os.path.join(core_dir, script)
        if os.path.isfile(script_path):
            files_to_collect.append(script_path)
        else:
            print(f"警告：脚本文件不存在，跳过 - {script_path}")

    # 创建输出目录
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    # 写入合并文件
    with open(output_path, 'w', encoding='utf-8') as out_f:
        # 文件头信息
        out_f.write(f"# Source code collection generated at {datetime.now()}\n")
        out_f.write(f"# Project root: {project_root}\n")
        out_f.write("#" * 80 + "\n\n")

        for file_path in files_to_collect:
            rel_path = os.path.relpath(file_path, project_root)
            out_f.write(f"===== File: {rel_path} =====\n")
            out_f.write(f"# Absolute path: {file_path}\n")
            out_f.write("#" * 40 + "\n")

            try:
                with open(file_path, 'r', encoding='utf-8') as in_f:
                    content = in_f.read()
                out_f.write(content)
                if not content.endswith('\n'):
                    out_f.write('\n')
            except Exception as e:
                out_f.write(f"# ERROR: Could not read file - {e}\n")

            out_f.write("\n" + "#" * 40 + "\n\n")

    print(f"源代码已收集到：{output_path}")


def main():
    project_root = get_project_root()
    output_path = os.path.join(project_root, "temp", "run_weekly_TA_workflow_source_code.txt")
    collect_source_code(project_root, output_path)


if __name__ == "__main__":
    main()