#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

def collect_sources():
    """
    收集主控程序及其控制的 core 子目录中的脚本源码，
    合并写入到 temp 目录下的指定文本文件中。
    """
    # 当前脚本所在目录 (Code_utl)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 项目根目录 (Code_utl 的上一级)
    project_root = os.path.dirname(script_dir)

    # 需要收集的文件列表（相对于项目根目录）
    files_to_collect = [
        "run_HK_macro_dashboard_workflow.py",
        os.path.join("core", "HK_Macro","HK_Macro_History.py"),
        os.path.join("core", "HK_Macro","HK_Macro_Dashboard.py"),
    ]

    # 输出文件路径
    output_dir = os.path.join(project_root, "temp")
    output_file = os.path.join(output_dir, "run_HK_macro_dashboard_workflow_source_code.txt")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    try:
        with open(output_file, "w", encoding="utf-8") as out_f:
            for rel_path in files_to_collect:
                abs_path = os.path.join(project_root, rel_path)
                if not os.path.isfile(abs_path):
                    print(f"警告: 文件不存在，跳过: {abs_path}")
                    continue

                # 写入文件分隔头和文件名
                out_f.write(f"\n{'='*60}\n")
                out_f.write(f"文件: {rel_path}\n")
                out_f.write(f"{'='*60}\n\n")

                # 写入文件内容
                try:
                    with open(abs_path, "r", encoding="utf-8") as in_f:
                        content = in_f.read()
                        out_f.write(content)
                        out_f.write("\n\n")  # 文件间留空行
                    print(f"已收集: {rel_path}")
                except Exception as e:
                    print(f"读取文件 {rel_path} 时出错: {e}")
                    continue

        print(f"\n所有源码已合并到: {output_file}")

    except Exception as e:
        print(f"写入输出文件失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    collect_sources()