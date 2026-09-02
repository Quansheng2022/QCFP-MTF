#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess

# ========== UTF-8 输出兜底 ==========
# 当 stdout/stderr 被重定向时，Windows 默认使用 GBK/cp1252 编码，
# print 中文会抛 UnicodeEncodeError，这里统一强制 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

def run_script(script_name: str) -> bool:
    """
    在当前 Python 解释器下运行指定脚本，并打印输出。
    返回 True 表示成功，False 表示失败。
    """
    script_path = os.path.join("Core","HK_Macro", script_name)
    if not os.path.isfile(script_path):
        print(f"[错误] 找不到脚本: {script_path}")
        return False

    print(f"\n[开始] 运行 {script_name} ...")
    cmd = [sys.executable, script_path]
    
    # 复制当前环境变量，并强制子进程 stdout/stderr 使用 UTF-8 编码
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    
    try:
        result = subprocess.run(
            cmd,
            cwd=os.getcwd(),          # 工作目录为项目根目录
            capture_output=True,
            text=True,
            encoding='utf-8',         # 捕获的输出按 UTF-8 解码
            env=env                   # 传递带有 PYTHONIOENCODING 的环境
        )
        # 打印标准输出
        if result.stdout:
            print(result.stdout)
        # 打印标准错误（即使成功也打印，便于调试）
        if result.stderr:
            print("[stderr]", result.stderr, sep="\n")
        # 检查返回码
        if result.returncode != 0:
            print(f"[错误] {script_name} 执行失败，返回码 {result.returncode}")
            return False
        else:
            print(f"[完成] {script_name} 执行成功")
            return True
    except Exception as e:
        print(f"[异常] 运行 {script_name} 时发生异常: {e}")
        return False

def main():
    scripts = ["HK_Macro_History.py", "HK_Macro_Dashboard.py"]
    print("=== TA_Workflow 控制程序启动 ===")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python 解释器: {sys.executable}")

    for script in scripts:
        if not run_script(script):
            print("\n[终止] 流程因错误中断。")
            sys.exit(1)

    print("\n=== 所有脚本已按顺序成功执行完毕 ===")

if __name__ == "__main__":
    main()
