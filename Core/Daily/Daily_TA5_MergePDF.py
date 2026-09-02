#!/usr/bin/env python
# coding: utf-8

"""
Step 10: Merge technical analysis reports into daily analysis report.
Source Code: Daily_TA5_MergePDF.py
Function: Merge technical analysis reports including K charts report, chip analysis report, moneyflow analysis report.
"""

# 系统操作
import os
import sys
import time
import io

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
from datetime import datetime, timedelta

# IPython交互
from IPython.display import display, Markdown, clear_output
from io import StringIO


def setup_logging(log_dir, log_filename="Daily_TA5_MergePDF.log"):
    """
    配置日志系统，同时输出到控制台和日志文件
    
    参数:
    log_dir (str): 日志文件目录
    log_filename (str): 日志文件名
    """
    # 确保日志目录存在
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        log_filepath = os.path.join(log_dir, log_filename)
    else:
        log_filepath = log_filename
    
    # 清除现有的handler，避免重复
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 配置日志格式
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 设置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # 文件处理器 - 写入日志文件
            logging.FileHandler(log_filepath, encoding='utf-8'),
            # 控制台处理器 - 输出到控制台
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # 重定向print到logging
    # 创建一个自定义的print函数
    global print
    original_print = print
    
    def logging_print(*args, **kwargs):
        """自定义print函数，将输出重定向到logging"""
        # 将args转换为字符串
        message = ' '.join(str(arg) for arg in args)
        # 如果有sep参数，使用它
        if 'sep' in kwargs:
            message = kwargs['sep'].join(str(arg) for arg in args)
        # 记录到日志
        logging.info(message)
    
    print = logging_print
    
    logging.info(f"日志系统初始化完成，日志文件: {log_filepath}")
    return log_filepath


def merge_pdfs(pdf_inputs, pdf_output):
    """
    将多个PDF文件合并为一个PDF文件

    参数:
    pdf_inputs (list): 包含多个PDF文件路径的列表
    pdf_output (str): 合并后的PDF文件路径
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
                logging.warning(f"{pdf} 文件不存在，跳过合并")
                missing_files.append(pdf)
                continue

            # 用上下文管理器打开每个PDF文件并添加到合并器
            try:
                with open(pdf, 'rb') as f:
                    merger.append(f)
                merged_count += 1
                logging.info(f"成功添加PDF文件: {pdf}")
            except Exception as e:
                logging.error(f"处理文件 {pdf} 时出错: {str(e)}")
                raise

        # 如果有成功合并的文件，才写入输出文件
        if merged_count > 0:
            with open(pdf_output, 'wb') as output_file:
                merger.write(output_file)
            logging.info(f"成功合并 {merged_count} 个PDF文件到: {pdf_output}")
        else:
            logging.warning("没有有效的PDF文件可供合并")

    except FileNotFoundError as e:
        logging.error(f"文件未找到错误: {str(e)}")
        raise
    except PyPDF2.errors.PdfReadError as e:
        logging.error(f"PDF读取错误: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"发生未知错误: {str(e)}")
        raise

    finally:
        # 确保资源被释放
        merger.close()

    return merged_count, missing_files


# === 添加UTL路径到系统路径 ===
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

# 确保项目根目录也在 sys.path（便于其他模块使用，虽非必需）
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

# 从 utl.stock_analysis_utl 导入所需工具（同在 utl 目录下）
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


# === 强制UTF-8编码输出 ===
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


def main():
    """主函数，程序的入口点"""
    try:
        # ========== 主程序路径配置 ==========        
        # 构建配置文件路径：父目录下的config文件夹中的stock_data_analysis.par
        config_path = os.path.join(project_dir, 'config', 'stock_data_analysis.par')

        # ========== 加载配置 ==========
        # 使用load_config函数加载配置
        CONFIG = load_config(config_path, project_dir)
        print(f"配置文件加载成功: {config_path}")

        # 更新全局路径配置
        GlobalConfig.update_paths(CONFIG, project_dir)

        # ========== 初始化日志系统 ==========
        # 在更新路径后初始化日志系统
        log_filepath = setup_logging(
            GlobalConfig.full_log_dir, 
            "Daily_TA5_MergePDF.log"
        )
        
        # ========== 打印配置信息 ==========
        logging.info("=" * 50)
        logging.info(f"项目目录: {project_dir}")
        logging.info(f"配置文件位置: {config_path}")
        logging.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logging.info(f"报告目录: {GlobalConfig.full_report_dir}")
        logging.info(f"日志目录: {GlobalConfig.full_log_dir}")
        logging.info(f"日志文件: {log_filepath}")

        if CONFIG.get('tickers'):
            tickers = CONFIG['tickers']
            logging.info(f"股票代码数量: {len(tickers)}")
            if len(tickers) > 5:
                logging.info(f"前5个股票代码: {tickers[:5]}... 等")
            else:
                logging.info(f"股票代码: {tickers}")
        else:
            logging.warning("配置文件中未找到tickers设置")

        # ========== 合并分析报告 ==========
        if not tickers:
            logging.error("无法合并分析报告 - 没有配置股票代码")
        else:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(f"{current_time} 开始合并分析报告！")
            
            # 处理每个股票代码
            for ticker in tickers:
                try:
                    logging.info(f"开始处理股票代码: {ticker}")
                    
                    # 构建输入文件路径
                    daily_pdf = os.path.join(GlobalConfig.full_report_dir, f'{ticker}_daily_TA_indicator_analysis.pdf')
                    chip_signal_pdf = os.path.join(GlobalConfig.full_report_dir, f'{ticker}_daily_chip_signal_analysis.pdf')
                    chip_distribution_pdf = os.path.join(GlobalConfig.full_report_dir, f'{ticker}_daily_chip_distribution_analysis.pdf')
                    money_flow_pdf = os.path.join(GlobalConfig.full_report_dir, f'{ticker}_daily_moneyflow_analysis.pdf')

                    input_files = [daily_pdf, chip_signal_pdf, chip_distribution_pdf, money_flow_pdf]
                    output_file = os.path.join(GlobalConfig.full_report_dir, f'{ticker}_daily_analysis_report.pdf')
                    
                    # 合并PDF
                    merged_count, missing_files = merge_pdfs(input_files, output_file)
                    
                    # 记录合并结果
                    if missing_files:
                        logging.warning(f"股票 {ticker} 缺失 {len(missing_files)} 个PDF文件")
                        for missing_file in missing_files:
                            logging.warning(f"  缺失文件: {missing_file}")
                    
                    logging.info(f"股票 {ticker} 合并完成，成功合并 {merged_count} 个文件")
                    
                except Exception as e:
                    logging.error(f"处理股票 {ticker} 时出错: {str(e)}")
                    logging.error(traceback.format_exc())
                    continue

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(f"{current_time} ✅ 全部分析报告合并完成！")

    except Exception as e:
        logging.error(f"发生未知错误: {type(e).__name__}: {e}")
        logging.error(traceback.format_exc())

        if 'get_ipython' not in globals():
            sys.exit(1)
        else:
            logging.info("在Jupyter环境中运行，程序继续但可能无法正常工作")


if __name__ == "__main__":
    main()