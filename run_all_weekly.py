#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import os
from pathlib import Path

def find_venv_python():
    """
    在当前目录及其上级目录中查找虚拟环境的 Python 解释器。
    优先查找 .venv（您指定的路径），再查找其他常见名称。
    返回路径字符串或 None。
    """
    # 将 .venv 放在第一位，优先匹配
    venv_names = [".venv", "venv", ".env", "env", "myenv"]
    base_dir = Path.cwd()

    # 向上最多查找 3 级（可根据需要调整）
    for _ in range(3):
        for name in venv_names:
            venv_dir = base_dir / name
            if venv_dir.exists() and venv_dir.is_dir():
                if sys.platform == "win32":
                    python_path = venv_dir / "Scripts" / "python.exe"
                else:
                    python_path = venv_dir / "bin" / "python"
                if python_path.exists():
                    return str(python_path)
        base_dir = base_dir.parent

    return None

def get_python_interpreter():
    """
    获取应使用的 Python 解释器路径。
    优先使用虚拟环境中的，否则回退到当前解释器。
    """
    venv_python = find_venv_python()
    if venv_python:
        print(f"✅ 使用虚拟环境 Python: {venv_python}")
        return venv_python
    else:
        print(f"⚠️  未找到虚拟环境，使用当前 Python 解释器: {sys.executable}")
        return sys.executable

def run_scripts():
    """依次运行每周任务所需的所有 Python 脚本"""
    python_exe = get_python_interpreter()

    scripts = [
        [python_exe, "run_Weekly_TA_workflow.py"],
        [python_exe, r"Code_Prompt\Gen_Prompt_Weekly.py"],
        [python_exe, r"core\Daily\Daily_TA6A_Buy_Signal_Analyzer_Optimized.py"],
        [python_exe, r"core\Daily\Daily_TA6B_Sell_Signal_Analyzer_Optimized.py"],
        [python_exe, r"core\Daily\Daily_TA7_Merge_Analysis_Report_Workflow.py"],
        [python_exe, r"core\Daily\Daily_TA_report.py"]
    ]

    total = len(scripts)
    for idx, cmd in enumerate(scripts, 1):
        print(f"\n{'='*60}")
        print(f"运行脚本 {idx}/{total}: {' '.join(cmd)}")
        print('='*60)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(f"【错误输出】\n{result.stderr}", file=sys.stderr)
            if result.returncode != 0:
                print(f"⚠️  脚本退出码: {result.returncode} (非零，可能执行失败)", file=sys.stderr)
                # 如需遇到失败立即停止，取消下面注释
                # break
            else:
                print(f"✅ 脚本执行成功 (返回码 0)")
        except FileNotFoundError as e:
            print(f"❌ 错误: 找不到脚本或 Python 解释器 - {e}", file=sys.stderr)
        except Exception as e:
            print(f"❌ 未知错误: {e}", file=sys.stderr)

    print("\n所有脚本执行完毕。")

if __name__ == "__main__":
    run_scripts()