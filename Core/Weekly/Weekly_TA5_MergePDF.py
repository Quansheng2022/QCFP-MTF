#!/usr/bin/env python
# coding: utf-8

"""
Name: Weekly_TA5_MergePDF.py
Function:
将下载
1. 合并周线技术分析与资金流分析图表文件.
2. 输入数据文件: 
    1) 周线技术分析图表文件{ticker}_weekly_TA_analysis.pdf
    2) 周线资金流分析图表文件{ticker}_weekly_moneyflow_analysis.pdf
3. 输出数据文件: 
    1) 周线资金流技术指标文件：{ticker}_weekly_analysis_report.pdf         
"""

# 系统操作
import os
import sys
import time
import io
import json

# 错误处理
import logging
import traceback

# 上下文管理
import contextlib
import PyPDF2

# 路径处理
from pathlib import Path

# 数据处理
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# IPython交互
from IPython.display import display, Markdown, clear_output
from io import StringIO

# 配置日志记录器
def setup_logger(log_dir):
    """设置日志记录器 - 每次运行覆盖原有日志文件"""
    log_file = os.path.join(log_dir, 'Weekly_TA5_MergePDF.log')
    
    # 创建日志目录（如果不存在）
    os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志
    logger = logging.getLogger('Weekly_TA5_MergePDF')
    logger.setLevel(logging.INFO)
    
    # 清除已有的处理器
    if logger.handlers:
        logger.handlers.clear()
    
    # 文件处理器 - 使用 'w' 模式覆盖原有文件
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 统一的时间格式，精确到秒
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def merge_pdfs(pdf_inputs, pdf_output, logger=None):
    """
    将多个PDF文件合并为一个PDF文件

    参数:
    pdf_inputs (list): 包含多个PDF文件路径的列表
    pdf_output (str): 合并后的PDF文件路径
    logger: 日志记录器
    """
    # 创建一个PDF合并器对象
    merger = PyPDF2.PdfMerger()

    # 记录实际合并的文件数量和缺失文件列表
    merged_count = 0
    missing_files = []

    try:
        # 遍历所有输入PDF文件
        for pdf in pdf_inputs:
            # 检查文件是否存在
            if not os.path.exists(pdf):
                msg = f"{pdf} file doesn't exist. Skip for file merge process."
                if logger:
                    logger.warning(msg)
                else:
                    print(msg)
                missing_files.append(pdf)
                continue

            # 用上下文管理器打开每个PDF文件并添加到合并器
            try:
                with open(pdf, 'rb') as f:
                    merger.append(f)
                merged_count += 1
                if logger:
                    # 简化日志信息，只显示添加成功的文件
                    logger.info(f"成功添加PDF文件: {pdf}")
                else:
                    print(f"成功添加PDF文件: {pdf}")
            except Exception as e:
                error_msg = f"处理文件 {pdf} 时出错: {str(e)}"
                if logger:
                    logger.error(error_msg)
                else:
                    print(error_msg)
                raise

        # 如果有成功合并的文件，才写入输出文件
        if merged_count > 0:
            with open(pdf_output, 'wb') as output_file:
                merger.write(output_file)
            msg = f"成功合并 {merged_count} 个PDF文件到: {pdf_output}"
            if logger:
                logger.info(msg)
            else:
                print(msg)
        else:
            msg = "没有有效的PDF文件可供合并"
            if logger:
                logger.warning(msg)
            else:
                print(msg)

    except FileNotFoundError as e:
        error_msg = f"文件未找到错误: {str(e)}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
        raise
    except PyPDF2.errors.PdfReadError as e:
        error_msg = f"PDF读取错误: {str(e)}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
        raise
    except Exception as e:
        error_msg = f"发生未知错误: {str(e)}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
        raise

    finally:
        # 确保资源被释放
        merger.close()

    return merged_count, missing_files

def open_pdf(pdf_path, logger=None):
    """根据操作系统以全屏模式打开PDF文件"""
    if not os.path.exists(pdf_path):
        error_msg = f"PDF文件 '{pdf_path}' 不存在"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
        return False

    try:
        if sys.platform == 'win32':  # Windows系统
            # 尝试使用Acrobat Reader全屏打开
            acrobat_path = r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe"
            if os.path.exists(acrobat_path):
                import subprocess
                cmd = f'cmd /c start /max "" "{acrobat_path}" /A "page=1&navpanes=0&toolbar=0&statusbar=0&view=FitH,100" "{pdf_path}"'
                subprocess.Popen(cmd, shell=True)
                return True

            # 如果没有Acrobat，尝试使用默认程序最大化打开
            msg = "使用默认程序打开pdf文件"
            if logger:
                logger.info(msg)
            else:
                print(msg)
            os.startfile(pdf_path)
            return True

        elif sys.platform == 'darwin':  # macOS系统
            # 使用AppleScript命令让Preview全屏打开
            script = f'''
            tell application "Preview"
                activate
                open POSIX file "{pdf_path}"
                tell application "System Events" to tell process "Preview"
                    set value of attribute "AXFullScreen" of window 1 to true
                end tell
            end tell
            '''
            import subprocess
            subprocess.call(['osascript', '-e', script])
            return True

        else:  # Linux系统
            # 尝试使用Evince全屏打开
            try:
                import subprocess
                subprocess.Popen(['evince', '--fullscreen', pdf_path])
                return True
            except FileNotFoundError:
                # 如果没有Evince，尝试使用Okular全屏打开
                try:
                    import subprocess
                    subprocess.Popen(['okular', '--presentation', pdf_path])
                    return True
                except FileNotFoundError:
                    # 最后尝试使用默认程序打开
                    import subprocess
                    subprocess.call(('xdg-open', pdf_path))
                    return True

    except Exception as e:
        error_msg = f"打开PDF文件时出错: {str(e)}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
        return False

def load_stock_list_from_json(json_path, logger=None):
    """
    从 stock_list.json 文件加载股票列表
    
    参数:
    json_path: JSON文件路径
    logger: 日志记录器
    
    返回:
    dict: 股票代码到名称的映射字典
    """
    stock_dict = {}
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'stocks' in data:
            for stock in data['stocks']:
                code = stock.get('code', '')
                name = stock.get('name', '')
                if code and name:
                    stock_dict[code] = name
            
            if logger:
                logger.info(f"从 {json_path} 加载了 {len(stock_dict)} 个股票")
            else:
                print(f"从 {json_path} 加载了 {len(stock_dict)} 个股票")
        else:
            if logger:
                logger.warning(f"JSON文件中未找到 'stocks' 键: {json_path}")
            else:
                print(f"警告: JSON文件中未找到 'stocks' 键: {json_path}")
                
    except FileNotFoundError:
        error_msg = f"stock_list.json 文件不存在: {json_path}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
    except json.JSONDecodeError as e:
        error_msg = f"解析 stock_list.json 失败: {str(e)}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
    except Exception as e:
        error_msg = f"加载 stock_list.json 时出错: {str(e)}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
    
    return stock_dict

def get_stock_name(stock_dict, stock_code, logger=None):
    """
    从股票字典获取股票名称
    
    参数:
    stock_dict: 股票代码到名称的映射字典
    stock_code: 股票代码
    logger: 日志记录器
    
    返回:
    str: 股票名称，如果未找到则返回空字符串
    """
    if stock_code in stock_dict:
        return stock_dict[stock_code]
    else:
        if logger:
            logger.warning(f"未找到股票代码 {stock_code} 的名称")
        return ""

def get_column_names_from_db(db_path, table_name, logger=None):
    """
    从SQLite数据库获取表的列名（已弃用，保留以备将来使用）
    
    参数:
    db_path: 数据库路径
    table_name: 表名
    logger: 日志记录器
    
    返回:
    list: 列名列表
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取表的列信息
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        conn.close()
        
        if columns:
            column_names = [col[1] for col in columns]  # col[1]是列名
            return column_names
        else:
            if logger:
                logger.warning(f"表 {table_name} 不存在或没有列")
            return []
            
    except Exception as e:
        error_msg = f"从数据库获取列名失败: {str(e)}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
        return []

import os
import sys
import subprocess
import logging

def main():
    """主函数，程序的入口点"""
    try:
        # ========== 添加UTL路径到系统路径 ==========
        # 当前脚本所在目录：
        script_dir = Path(__file__).resolve().parent

        # 将 Core 目录加入 sys.path，以便导入 utl 包
        core_dir = script_dir.parent   # TA_Workflow/Core
        if str(core_dir) not in sys.path:
            sys.path.insert(0, str(core_dir))

        # 从 utl.stock_analysis_utl 导入 get_project_root（该函数返回 Core 目录）
        from utl.stock_analysis_utl import get_project_root

        # 利用该函数获取 Core 目录，再取其父目录得到项目根目录 (TA_Workflow)
        core_dir_from_utils = get_project_root()   # Path 对象，指向 Core
        project_dir = core_dir_from_utils.parent  # TA_Workflow

        # 确保项目根目录也在 sys.path
        if str(project_dir) not in sys.path:
            sys.path.insert(0, str(project_dir))

        # 从 utl.stock_analysis_utl 导入所需工具
        try:
            from utl.stock_analysis_utl import (
                load_config,
                setup_windows_encoding,
                GlobalConfig
            )
        except ImportError as e:
            print("=" * 60)
            print("❌ 严重错误：无法导入 utl.stock_analysis_utl 模块")
            print(f"   期望路径: {core_dir / 'utl' / 'stock_analysis_utl.py'}")
            print(f"   请确认该文件存在，且 utl 包中有 __init__.py")
            print(f"   详细错误: {e}")
            print("=" * 60)
            sys.exit(1)

        # ========== 强制UTF-8编码输出 ==========
        if 'get_ipython' not in globals():
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        else:
            # 在Jupyter环境中添加兼容处理
            import ipykernel
            if ipykernel:
                sys.stdout.encoding = 'utf-8'
                sys.stderr.encoding = 'utf-8'

        # 执行Windows编码设置
        setup_windows_encoding()

        # ========== 主程序路径配置 ==========        
        # 构建配置文件路径：父目录下的config文件夹中的stock_data_analysis.par
        config_path = os.path.join(project_dir, 'config', 'stock_data_analysis.par')

        # ========== 加载配置 ==========
        # 使用load_config函数加载配置
        CONFIG = load_config(config_path, project_dir)
        print(f"配置文件加载成功: {config_path}")

        # 更新全局路径配置
        GlobalConfig.update_paths(CONFIG, project_dir)

        # ========== 设置日志 ==========
        logger = setup_logger(GlobalConfig.full_log_dir)
        logger.info("=" * 60)
        logger.info("Weekly_TA5_MergePDF 开始执行")
        logger.info("=" * 60)

        # ========== 打印配置信息 ==========
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件位置: {config_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"报告目录: {GlobalConfig.full_report_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        logger.info(f"SQLite数据库目录: {GlobalConfig.full_sqlite_dir}")

        # ========== 加载股票列表 ==========
        # 构建 stock_list.json 路径
        stock_list_path = os.path.join(project_dir, 'config', 'stock_list.json')
        logger.info(f"加载股票列表: {stock_list_path}")
        
        # 从 JSON 文件加载股票名称映射
        stock_dict = load_stock_list_from_json(stock_list_path, logger)
        if not stock_dict:
            logger.warning("未能加载股票列表，股票名称将为空")
            print("警告: 未能加载股票列表，股票名称将为空")

        # 获取股票列表
        if CONFIG.get('tickers'):
            tickers = CONFIG['tickers']
            logger.info(f"股票代码数量: {len(tickers)}")
            if len(tickers) > 5:
                logger.info(f"前5个股票代码: {tickers[:5]}... 等")
            else:
                logger.info(f"股票代码: {tickers}")
        else:
            logger.warning("配置文件中未找到tickers设置")
            print("错误: 配置文件中未找到tickers设置")
            return

        # ========== 构建数据库路径 ==========
        db_path = os.path.join(GlobalConfig.full_sqlite_dir, 'HK_Stock.db')
        if not os.path.exists(db_path):
            error_msg = f"数据库文件不存在: {db_path}"
            logger.error(error_msg)
            print(error_msg)
            return

        logger.info(f"数据库路径: {db_path}")

        # ========== 合并分析报告 ==========
        if not tickers:
            logger.error("无法合并分析报告 - 没有配置股票代码")
            print("错误: 无法合并分析报告 - 没有配置股票代码")
            return

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"{current_time} 开始合并分析报告！")
        print(f"{current_time} 开始合并分析报告！")

        # 处理每个股票代码
        for ticker in tickers:
            try:
                # 从股票字典获取股票名称
                stock_name = get_stock_name(stock_dict, ticker, logger)
                if stock_name:
                    logger.info(f"处理股票: {ticker} ({stock_name})")
                    print(f"处理股票: {ticker} ({stock_name})")
                else:
                    logger.info(f"处理股票: {ticker}")
                    print(f"处理股票: {ticker}")
                
                # 构建输入输出文件路径
                TA_pdf = os.path.join(GlobalConfig.full_report_dir, f'{ticker}_weekly_TA_analysis.pdf')
                money_flow_pdf = os.path.join(GlobalConfig.full_report_dir, f'{ticker}_weekly_moneyflow_analysis.pdf')

                input_files = [TA_pdf, money_flow_pdf]
                output_file = os.path.join(GlobalConfig.full_report_dir, f'{ticker}_weekly_analysis_report.pdf')
                
                # 合并PDF
                merge_pdfs(input_files, output_file, logger)

                # 自动打开PDF报告
                auto_open_pdf = CONFIG.get('auto_open_pdf', False)
                if auto_open_pdf:
                    logger.info(f"正在打开PDF报告: {ticker}")
                    print(f"正在打开PDF报告: {ticker}...")
                    try:
                        open_pdf(output_file, logger)
                        time.sleep(1)
                        logger.info(f"已打开PDF报告: {output_file}")
                    except Exception as e:
                        logger.error(f"打开PDF报告失败: {str(e)}")
                        print(f"打开PDF报告失败: {str(e)}")

            except Exception as e:
                error_msg = f"处理股票 {ticker} 时出错: {str(e)}"
                logger.error(error_msg)
                print(error_msg)
                continue

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"{current_time} ✅ 全部分析报告合并完成！")
        print(f"{current_time} ✅ 全部分析报告合并完成！")

        logger.info("=" * 60)
        logger.info("Weekly_TA5_MergePDF 执行完成")
        logger.info("=" * 60)

    except Exception as e:
        error_msg = f"发生未知错误: {type(e).__name__}: {e}"
        if 'logger' in locals():
            logger.error(error_msg)
            logger.error(traceback.format_exc())
        else:
            print(error_msg)
            traceback.print_exc()

        if 'get_ipython' not in globals():
            sys.exit(1)
        else:
            print("在Jupyter环境中运行，程序继续但可能无法正常工作")

if __name__ == "__main__":
    main()