#!/usr/bin/env python
# coding: utf-8

"""
Name: Weekly_TA4B_Analyze_MoneyFlow.py
Function:
1. 从SQLite数据库读取周线资金流数据
2. 计算生成各种周线资金流技术指标
3. 将计算结果保存到SQLite数据库
4. 生成周线资金流分析图表PDF
5. 使用并行处理进行优化

输入数据表：hk_hist_weekly_moneyflow 
输出数据表：hk_weekly_moneyflow_analysis 
生成周线资金流分析图表：{ticker}_weekly_moneyflow_analysis.pdf

"""

# ==================== 标准库导入 ====================
import os
import sys
import io
import time
import shutil
import warnings
import traceback
import platform
import subprocess
import contextlib
import sqlite3
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from threading import Lock
import queue

# ==================== 第三方库导入 ====================
import numpy as np
import pandas as pd
from scipy import stats
import seaborn as sns

# ==================== Matplotlib 配置（在导入 pyplot 之前） ====================
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端，避免线程问题

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
from matplotlib.backends.backend_pdf import PdfPages
from mplfinance.original_flavor import candlestick_ohlc
import matplotlib.font_manager as fm

import logging
# 设置matplotlib的日志级别为WARNING或更高
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
logging.getLogger('matplotlib.pyplot').setLevel(logging.WARNING)

# Set root logger to INFO (suppresses DEBUG messages)
logging.getLogger().setLevel(logging.INFO)

# Or specifically for your logger:
# logger = logging.get_logger()
# logger.setLevel(logging.INFO)

# ==================== 中文字体配置函数 ====================
def setup_chinese_font():
    """
    配置matplotlib中文字体，支持Windows/Linux/Mac
    参考 Weekly_TA3_Analyze_Indicators_Plot.py 中的方法
    """
    try:
        # 设置支持中文字符的字体
        # Windows 系统常用中文字体
        font_list = [
            'SimHei',           # 黑体 (Windows)
            'Microsoft YaHei',  # 微软雅黑 (Windows)
            'SimSun',           # 宋体 (Windows)
            'KaiTi',            # 楷体 (Windows)
            'Arial Unicode MS', # Mac
            'WenQuanYi Zen Hei', # Linux
            'Noto Sans CJK SC', # Linux
            'PingFang SC',      # Mac
            'Heiti SC',         # Mac
            'STHeiti',          # Mac
            'STSong',           # Mac
            'DejaVu Sans'       # 后备字体
        ]
        
        # 检查哪些字体可用
        available_fonts = []
        for font_name in font_list:
            try:
                # 尝试通过 fontproperties 检查
                test_font = fm.FontProperties(fname=font_name)
                available_fonts.append(font_name)
            except:
                # 如果直接指定失败，尝试搜索系统字体
                font_files = fm.findSystemFonts(fontpaths=None, fontext='ttf')
                for font_file in font_files:
                    if font_name.lower() in font_file.lower():
                        available_fonts.append(font_file)
                        break
        
        if available_fonts:
            plt.rcParams['font.sans-serif'] = available_fonts
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
            print(f"✅ 中文字体配置成功，使用字体: {available_fonts[0]}")
            return True
        else:
            # 备用方案
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']
            plt.rcParams['axes.unicode_minus'] = False
            print("⚠️ 未找到中文字体，将使用系统默认字体")
            return False
    except Exception as e:
        print(f"⚠️ 字体配置失败: {e}")
        # 使用默认配置
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        return False

# 执行字体配置
setup_chinese_font()

from fpdf import FPDF
from PyPDF2 import PdfReader, PdfWriter

import psutil
import win32com.client

from IPython.display import display, Markdown

# 全局锁用于线程安全的文件操作
file_lock = Lock()

# ==================== 日志配置 ====================
def setup_logger(log_dir):
    """
    配置日志系统 - 每次启动覆盖日志文件，无备份
    
    Args:
        log_dir: 日志目录路径
    
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    log_file = os.path.join(log_dir, 'Weekly_TA4B_Analyze_MoneyFlow.log')
    
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 配置根日志记录器
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)
    
    # 清除已有的处理器，避免重复
    if logger.handlers:
        logger.handlers.clear()
    
    # 文件处理器 - 使用覆盖模式，无备份
    file_handler = logging.FileHandler(
        log_file,
        mode='w',          # 覆盖写入模式
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 设置格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 初始化logger
logger = None

def get_logger():
    """获取logger实例"""
    global logger
    if logger is None:
        # 如果logger未初始化，创建一个默认的
        logger = logging.getLogger('')
        logger.setLevel(logging.DEBUG)
        
        # 清除已有的处理器
        if logger.handlers:
            logger.handlers.clear()
        
        # 创建控制台处理器
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        
        # 设置格式 - 移除 name 字段
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

# ==================== 全局配置类 ====================
class GlobalConfig:
    full_data_dir = None
    full_report_dir = None
    full_log_dir = None
    full_temp_dir = None
    full_sqlite_dir = None      # 新增：SQLite数据库目录
    db_name = None               # 新增：数据库名称
    full_db_path = None          # 新增：完整数据库路径
    
    @classmethod
    def update_paths(cls, config, project_dir):
        """更新全局路径配置"""
        cls.full_data_dir = os.path.join(project_dir, config.get('data_dir', 'Data'))
        cls.full_report_dir = os.path.join(project_dir, config.get('report_dir', 'Report'))
        cls.full_log_dir = os.path.join(project_dir, config.get('log_dir', 'Log'))
        cls.full_temp_dir = os.path.join(project_dir, config.get('temp_dir', 'Temp'))
        cls.full_sqlite_dir = os.path.join(project_dir, config.get('sqlite_dir', 'SQLiteDB'))
        cls.db_name = config.get('db_name', 'HK_Stock.db')
        cls.full_db_path = os.path.join(cls.full_sqlite_dir, cls.db_name)

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
        GlobalConfig as UtlGlobalConfig
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

# ==================== 日期矫正辅助函数 ====================

def adjust_date_to_friday(date_value):
    """
    将日期矫正为当周的星期五
    
    Args:
        date_value: 日期值，可以是字符串、datetime对象或pandas Timestamp
    
    Returns:
        str: 格式化为 'YYYY-MM-DD' 的星期五日期字符串
    
    Examples:
        >>> adjust_date_to_friday('2026-06-18')  # 星期四
        '2026-06-19'  # 星期五
        >>> adjust_date_to_friday('2026-06-19')  # 星期五
        '2026-06-19'  # 保持不变
    """
    # 转换为datetime对象
    if isinstance(date_value, str):
        dt = datetime.strptime(date_value, '%Y-%m-%d')
    elif isinstance(date_value, pd.Timestamp):
        dt = date_value.to_pydatetime()
    elif isinstance(date_value, datetime):
        dt = date_value
    else:
        # 尝试转换
        dt = pd.to_datetime(date_value).to_pydatetime()
    
    # 获取当前日期是星期几 (0=Monday, 6=Sunday)
    weekday = dt.weekday()
    
    # 如果已经是星期五 (weekday=4)，直接返回
    if weekday == 4:
        return dt.strftime('%Y-%m-%d')
    
    # 计算到本周五的天数差
    # 星期五是第4天 (0=Monday)
    days_to_friday = (4 - weekday) % 7
    friday_date = dt + timedelta(days=days_to_friday)
    
    return friday_date.strftime('%Y-%m-%d')

def adjust_date_column_to_friday(df, date_column='date'):
    """
    将DataFrame中的日期列矫正为当周的星期五
    
    Args:
        df: 包含日期列的DataFrame
        date_column: 日期列名称，默认为 'date'
    
    Returns:
        pd.DataFrame: 日期列被矫正后的DataFrame
    """
    if df.empty or date_column not in df.columns:
        return df
    
    # 复制DataFrame避免修改原数据
    result_df = df.copy()
    
    # 应用日期矫正
    result_df[date_column] = result_df[date_column].apply(adjust_date_to_friday)
    
    # 记录日志
    logger = get_logger()
    logger.debug(f"日期列 '{date_column}' 已矫正为当周星期五")
    
    return result_df

# ==================== 数据库操作辅助函数 ====================

def get_db_connection():
    """获取数据库连接"""
    db_path = GlobalConfig.full_db_path
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_stock_name_from_db(stock_code):
    """从数据库获取股票名称"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT stock_name FROM hk_hist_weekly_moneyflow WHERE stock_code = ? LIMIT 1",
            (stock_code,)
        )
        result = cursor.fetchone()
        conn.close()
        return result['stock_name'] if result else stock_code
    except Exception as e:
        logger = get_logger()
        logger.error(f"获取股票名称失败: {e}")
        return stock_code

def get_latest_date_from_table(table_name, stock_code):
    """获取某表某股票的最新日期"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT MAX(date) as latest_date FROM {table_name} WHERE stock_code = ?",
            (stock_code,)
        )
        result = cursor.fetchone()
        conn.close()
        return result['latest_date'] if result and result['latest_date'] else None
    except Exception as e:
        logger = get_logger()
        logger.error(f"获取最新日期失败: {e}")
        return None

def get_stock_list_from_db():
    """从stock_list.json获取股票列表（作为后备方案）"""
    try:
        import json
        config_path = os.path.join(project_dir, 'Config', 'stock_list.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [stock['code'] for stock in data.get('stocks', [])]
    except Exception as e:
        logger = get_logger()
        logger.error(f"加载股票列表失败: {e}")
        return []

def read_moneyflow_from_db(stock_code, start_date=None, end_date=None):
    """
    从数据库读取周线资金流数据
    
    Args:
        stock_code: 股票代码
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
    
    Returns:
        pd.DataFrame: 包含所有资金流字段的数据框
    """
    try:
        conn = get_db_connection()
        query = """
            SELECT stock_code, stock_name, date, price_chgpct, capital_trend,
                   extra_large, large, medium, small
            FROM hk_hist_weekly_moneyflow
            WHERE stock_code = ?
        """
        params = [stock_code]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
            
        query += " ORDER BY date ASC"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        logger = get_logger()
        logger.error(f"读取资金流数据失败 ({stock_code}): {e}")
        return pd.DataFrame()

def read_analysis_from_db(stock_code, start_date=None, end_date=None):
    """
    从数据库读取周线资金流分析数据
    
    Args:
        stock_code: 股票代码
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
    
    Returns:
        pd.DataFrame: 包含所有分析字段的数据框
    """
    try:
        conn = get_db_connection()
        query = """
            SELECT stock_code, stock_name, date, price_chgpct, capital_trend,
                   extra_large, large, medium, small, institutional_flow,
                   individual_flow, inst_5ma, ind_5ma, idr, fbi
            FROM hk_weekly_moneyflow_analysis
            WHERE stock_code = ?
        """
        params = [stock_code]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
            
        query += " ORDER BY date ASC"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        logger = get_logger()
        logger.error(f"读取资金流分析数据失败 ({stock_code}): {e}")
        return pd.DataFrame()

def save_analysis_to_db(df, stock_code):
    """
    将分析结果保存到数据库（在保存前进行日期矫正）
    
    Args:
        df: 包含分析结果的DataFrame
        stock_code: 股票代码
    
    Returns:
        bool: 是否保存成功
    """
    try:
        # ===== 关键修改：在保存前进行日期矫正 =====
        # 将日期矫正为当周星期五
        df_corrected = adjust_date_column_to_friday(df, 'date')
        
        logger = get_logger()
        logger.info(f"{stock_code}: 日期已矫正为当周星期五")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取股票名称
        stock_name = get_stock_name_from_db(stock_code)
        
        # 准备插入数据（使用矫正后的日期）
        for _, row in df_corrected.iterrows():
            cursor.execute("""
                INSERT OR REPLACE INTO hk_weekly_moneyflow_analysis 
                (stock_code, stock_name, date, price_chgpct, capital_trend, 
                 extra_large, large, medium, small, institutional_flow, 
                 individual_flow, inst_5ma, ind_5ma, idr, fbi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stock_code,
                stock_name,
                row['date'],
                row.get('price_chgpct', None),
                row.get('capital_trend', None),
                row.get('extra_large', None),
                row.get('large', None),
                row.get('medium', None),
                row.get('small', None),
                row.get('institutional_flow', None),
                row.get('individual_flow', None),
                row.get('inst_5ma', None),
                row.get('ind_5ma', None),
                row.get('idr', None),
                row.get('fbi', None)
            ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger = get_logger()
        logger.error(f"保存分析结果到数据库失败 ({stock_code}): {e}")
        return False

def check_and_process_stock(stock_code):
    """
    检查股票的数据状态并决定是否需要处理
    
    Args:
        stock_code: 股票代码
    
    Returns:
        tuple: (needs_processing, status_message, df_source, df_analysis)
    """
    # 获取原始数据最新日期
    source_latest = get_latest_date_from_table('hk_hist_weekly_moneyflow', stock_code)
    if not source_latest:
        return False, f"{stock_code} 原始数据缺失", None, None
    
    # 获取分析数据最新日期
    analysis_latest = get_latest_date_from_table('hk_weekly_moneyflow_analysis', stock_code)
    
    # 获取股票名称
    stock_name = get_stock_name_from_db(stock_code)
    
    if not analysis_latest:
        # 没有分析数据，需要计算
        return True, f"{stock_code} 无历史分析记录，将进行全量计算", None, None
    
    # 比较日期
    if analysis_latest < source_latest:
        return True, f"{stock_code} 分析数据({analysis_latest})早于原始数据({source_latest})，将增量计算", None, None
    elif analysis_latest == source_latest:
        return False, f"{stock_code} 资金流整合数据已存在，无需重复计算", None, None
    else:
        return False, f"{stock_code} 资金流原始数据缺失或资金流分析数据有误，需进行核查", None, None

def calculate_money_flow_indicator_df(df):
    """
    计算周资金流指标（机构/散户资金流、5周均线、IDR、FBI等）
    注意：在计算前会进行日期矫正
    
    Args:
        df: 包含原始数据的DataFrame
    
    Returns:
        pd.DataFrame: 包含计算结果的DataFrame（日期已矫正为星期五）
    """
    if df.empty:
        return df
    
    # 复制数据框避免修改原数据
    result_df = df.copy()
    
    # ===== 关键修改：在计算指标前进行日期矫正 =====
    # 将日期矫正为当周星期五
    result_df = adjust_date_column_to_friday(result_df, 'date')
    
    # 确保日期列是字符串格式
    if 'date' in result_df.columns:
        # 日期已经被矫正为字符串格式，但为了安全，再做一次格式化
        result_df['date'] = pd.to_datetime(result_df['date']).dt.strftime('%Y-%m-%d')
    
    # 计算资金流指标
    result_df['institutional_flow'] = result_df['extra_large'] + result_df['large']
    result_df['individual_flow'] = result_df['medium'] + result_df['small']
    
    # 计算5周移动平均
    result_df['inst_5ma'] = result_df['institutional_flow'].rolling(window=5, min_periods=1).mean()
    result_df['ind_5ma'] = result_df['individual_flow'].rolling(window=5, min_periods=1).mean()
    
    # 计算IDR和FBI
    denominator = abs(result_df['institutional_flow']) + abs(result_df['individual_flow'])
    safe_denom = denominator.replace(0, np.nan)
    result_df['idr'] = abs(result_df['institutional_flow']) / safe_denom
    result_df['fbi'] = (result_df['institutional_flow'] - result_df['individual_flow']) / safe_denom
    
    logger = get_logger()
    logger.debug(f"日期已矫正为星期五，共处理 {len(result_df)} 条记录")
    
    return result_df

# ==================== PDF报告生成相关函数 ====================

def get_unit_and_scale(data_series):
    """根据数据量级返回合适的单位和缩放因子（Mil/Bil）"""
    max_abs = max(abs(data_series.min()), abs(data_series.max()))
    if max_abs >= 1e9:
        return 'Bil', 1e9
    else:
        return 'Mil', 1e6

def close_pdf_reader(pdf_path):
    """Close Adobe Acrobat Reader if it has the target PDF open"""
    try:
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'].lower() in ['Acrobat.exe', 'acrord32.exe']:
                try:
                    cmdline = proc.cmdline()
                    if any(pdf_path.lower() in arg.lower() for arg in cmdline):
                        proc.terminate()
                        proc.wait(timeout=5)
                        time.sleep(1)
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        return False
    except Exception as e:
        print(f"Warning: Could not close PDF reader - {str(e)}")
        return False

def create_grouped_stacked_bars(current_ticker, date_range_label, period_data_cache, data_periods=None):
    """
    Optimized function to create grouped stacked bar charts with negative value support
    """
    if data_periods is None:
        data_periods = [20, 60, 'AP']

    periods = []
    for period in data_periods:
        if period in period_data_cache:
            periods.append(period_data_cache[period])

    if not periods:
        return None

    categories = ['Institutional_Flow', 'Individual_Flow']
    investor_types = ['Extra_Large', 'Large', 'Medium', 'Small']
    colors = ['#1f77b4', '#5ca0d3', '#ff7f0e', '#ffaa5c']

    all_values = []
    for _, period_df in periods:
        for itype in investor_types:
            all_values.append(period_df[itype].sum())

    total_unit, total_scale = get_unit_and_scale(pd.Series(all_values))

    plot_data = []
    for period_name, period_df in periods:
        extra_large = period_df['Extra_Large'].sum() / total_scale
        large = period_df['Large'].sum() / total_scale
        medium = period_df['Medium'].sum() / total_scale
        small = period_df['Small'].sum() / total_scale

        period_data = {
            'Period': period_name,
            'Institutional_Flow': {
                'Extra_Large': extra_large,
                'Large': large,
            },
            'Individual_Flow': {
                'Medium': medium,
                'Small': small
            },
            'Total Institutional': extra_large + large,
            'Total Individual': medium + small
        }
        plot_data.append(period_data)

    fig, ax = plt.subplots(figsize=(16, 9))

    x = np.arange(len(plot_data))
    width = 0.35
    offset = width / 2

    all_cumulative = []
    for period in plot_data:
        cum = 0
        all_cumulative.append(cum)
        for comp in ['Extra_Large', 'Large']:
            v = period['Institutional_Flow'][comp]
            cum += v
            all_cumulative.append(cum)
        cum2 = 0
        all_cumulative.append(cum2)
        for comp in ['Medium', 'Small']:
            v = period['Individual_Flow'][comp]
            cum2 += v
            all_cumulative.append(cum2)

    min_y = min(all_cumulative)
    max_y = max(all_cumulative)

    if min_y == max_y == 0:
        margin = 0.1
        ax.set_ylim(-0.1, 0.1)
    else:
        margin = (max_y - min_y) * 0.15
        ax.set_ylim(min_y - margin, max_y + margin)

    total_range = max_y - min_y
    if total_range == 0:
        offset_total = 0.01
    else:
        offset_total = total_range * 0.01

    for period_idx, period in enumerate(plot_data):
        inst_components = [
            ('Extra_Large', period['Institutional_Flow']['Extra_Large'], colors[0]),
            ('Large', period['Institutional_Flow']['Large'], colors[1])
        ]

        inst_bottom = 0
        for component, value, color in inst_components:
            bar = ax.bar(
                x[period_idx] - offset, 
                value, 
                width, 
                bottom=inst_bottom,
                color=color,
                edgecolor='white'
            )
            if abs(value) > 1e-5:
                mid = inst_bottom + value/2
                ax.text(
                    x[period_idx] - offset, 
                    mid, 
                    f'{value:,.1f}',
                    ha='center', 
                    va='center',
                    color='white',
                    fontweight='bold',
                    fontsize=9
                )
            inst_bottom += value

        ind_components = [
            ('Medium', period['Individual_Flow']['Medium'], colors[2]),
            ('Small', period['Individual_Flow']['Small'], colors[3])
        ]

        ind_bottom = 0
        for component, value, color in ind_components:
            bar = ax.bar(
                x[period_idx] + offset, 
                value, 
                width, 
                bottom=ind_bottom,
                color=color,
                edgecolor='white'
            )
            if abs(value) > 1e-5:
                mid = ind_bottom + value/2
                ax.text(
                    x[period_idx] + offset, 
                    mid, 
                    f'{value:,.1f}',
                    ha='center', 
                    va='center',
                    color='white',
                    fontweight='bold',
                    fontsize=9
                )
            ind_bottom += value

        total_inst = period['Total Institutional']
        if abs(total_inst) > 1e-5:
            if total_inst >= 0:
                y_pos = inst_bottom + offset_total
                va = 'bottom'
            else:
                y_pos = inst_bottom - offset_total
                va = 'top'
            ax.text(
                x[period_idx] - offset, 
                y_pos, 
                f'Total: {total_inst:,.1f}',
                ha='center', 
                va=va,
                fontsize=9,
                fontweight='bold',
                color='#1f77b4'
            )

        total_ind = period['Total Individual']
        if abs(total_ind) > 1e-5:
            if total_ind >= 0:
                y_pos = ind_bottom + offset_total
                va = 'bottom'
            else:
                y_pos = ind_bottom - offset_total
                va = 'top'
            ax.text(
                x[period_idx] + offset, 
                y_pos, 
                f'Total: {total_ind:,.1f}',
                ha='center', 
                va=va,
                fontsize=9,
                fontweight='bold',
                color='#ff7f0e'
            )

    ax.set_title(
        f'{current_ticker} Investor Flow Breakdown Comparison',
        fontsize=16,
        pad=20
    )
    ax.set_ylabel(f'Total Flow Amount ({total_unit})', fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels([p['Period'] for p in plot_data], fontsize=11)
    ax.grid(axis='y', alpha=0.3, linestyle=':')

    for i in range(1, len(plot_data)):
        ax.axvline(x=i - 0.5, color='gray', linestyle='-', alpha=0.5)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=colors[0], label='Institutional: Extra Large'),
        Patch(facecolor=colors[1], label='Institutional: Large'),
        Patch(facecolor=colors[2], label='Individual: Medium'),
        Patch(facecolor=colors[3], label='Individual: Small'),
    ]

    ax.legend(
        handles=legend_elements, 
        loc='upper center',
        bbox_to_anchor=(0.5, 1.15),
        ncol=4,
        frameon=True,
        framealpha=1,
        fontsize=10
    )

    fig.text(0.5, 0.01, 'Data Source: Flow Analysis System', 
             ha='center', fontsize=9, alpha=0.7)

    plt.tight_layout()
    
    safe_periods = [str(p).replace(':', '-') for p in data_periods]
    period_str = "_".join(safe_periods)
    plot_filename = os.path.join(GlobalConfig.full_temp_dir, f"{current_ticker}_grouped_stacked_breakdown_{period_str}.png")
    plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return plot_filename

def generate_moneyflow_pdf(stock_code, pdf_path):
    """
    生成周线资金流分析图表PDF（使用matplotlib的PDF后端）
    
    Args:
        stock_code: 股票代码
        pdf_path: PDF输出路径
    
    Returns:
        bool: 是否成功生成PDF
    """
    logger = get_logger()
    
    try:
        # 创建临时目录
        os.makedirs(GlobalConfig.full_temp_dir, exist_ok=True)
        
        # 从数据库读取分析数据
        df = read_analysis_from_db(stock_code)
        if df.empty:
            logger.error(f"{stock_code}: 无分析数据，无法生成PDF")
            return False
        
        # 获取股票名称
        stock_name = get_stock_name_from_db(stock_code)
        
        # 转换日期格式
        df['Date'] = pd.to_datetime(df['date'])
        df = df.sort_values('Date')
        
        # 重命名列以匹配旧程序格式
        df = df.rename(columns={
            'price_chgpct': 'Price_Chg%',
            'capital_trend': 'Capital_Trend',
            'extra_large': 'Extra_Large',
            'large': 'Large',
            'medium': 'Medium',
            'small': 'Small',
            'institutional_flow': 'Institutional_Flow',
            'individual_flow': 'Individual_Flow',
            'inst_5ma': 'Inst_5MA',
            'ind_5ma': 'Ind_5MA',
            'idr': 'IDR',
            'fbi': 'FBI'
        })
        
        # 确定分析期间
        today = datetime.now().date()
        data_dates = df['Date'].dt.date.unique()
        data_dates.sort()
        
        if today.weekday() == 4:  # Friday
            candidate = today
        else:
            days_to_last_friday = (today.weekday() - 4) % 7
            candidate = today - timedelta(days=days_to_last_friday)
        
        available_dates = [d for d in data_dates if d <= candidate]
        if not available_dates:
            analysis_end_date = data_dates[-1]
        else:
            analysis_end_date = max(available_dates)
        
        first_day = data_dates[0]
        three_years_before = analysis_end_date - pd.DateOffset(years=3)
        if hasattr(three_years_before, 'date'):
            analysis_start_date = max(three_years_before.date(), first_day)
        else:
            analysis_start_date = first_day
        
        date_range_label = f"{analysis_start_date} to {analysis_end_date}"
        
        # 筛选分析期间数据
        mask = (df['Date'].dt.date >= analysis_start_date) & (df['Date'].dt.date <= analysis_end_date)
        df_latest = df.loc[mask].copy()
        
        if len(df_latest) < 5:
            logger.warning(f"{stock_code}: 分析期间数据不足5周 ({len(df_latest)}周)")
        
        # 单位和缩放
        inst_flow = df_latest['Institutional_Flow']
        ind_flow = df_latest['Individual_Flow']
        unit, scale = get_unit_and_scale(pd.concat([inst_flow, ind_flow]))
        
        # 使用matplotlib的PDF后端（支持中文）
        from matplotlib.backends.backend_pdf import PdfPages
        
        with PdfPages(pdf_path) as pdf:
            # ---------- Page 1: Summary Text ----------
            fig_summary, ax_summary = plt.subplots(figsize=(11, 8.5))
            ax_summary.axis('off')
            
            # 构建摘要文本（支持中文）
            summary_text = f"""
分析报告: {stock_code} ({stock_name})
分析期间: {date_range_label}
周数: {len(df_latest)}

资金流指标:
- 机构主导周数: {(inst_flow > ind_flow).sum()}/{len(df_latest)}
- IDR均值: {df_latest['IDR'].mean():.2f}, FBI均值: {df_latest['FBI'].mean():.2f}
- 平均周涨幅: {df_latest['Price_Chg%'].mean():.2f}%
"""
            
            ax_summary.text(0.1, 0.9, summary_text, 
                          transform=ax_summary.transAxes, 
                          fontsize=12, 
                          verticalalignment='top',
                          fontfamily='sans-serif')
            pdf.savefig(fig_summary, bbox_inches='tight')
            plt.close(fig_summary)
            
            # ---------- Plot 1: Money Flow Trends ----------
            fig1, ax1 = plt.subplots(figsize=(11, 6))
            ax1.plot(df_latest['Date'], inst_flow/scale, label='机构资金流', color='#1f77b4')
            ax1.plot(df_latest['Date'], ind_flow/scale, label='散户资金流', color='#ff7f0e')
            ax1.axhline(0, color='black', linestyle='--')
            ax1.set_title(f'{stock_code} ({stock_name}) 周资金流趋势\n{date_range_label}')
            ax1.set_xlabel('日期')
            ax1.set_ylabel(f'资金流 ({unit})')
            ax1.legend()
            ax1.grid(alpha=0.3)
            pdf.savefig(fig1, bbox_inches='tight')
            plt.close(fig1)
            
            # ---------- Plot 2: 5-Week Moving Average ----------
            fig2, ax2 = plt.subplots(figsize=(11, 6))
            ax2.plot(df_latest['Date'], df_latest['Inst_5MA']/scale, label='机构5周均线', color='#1f77b4')
            ax2.plot(df_latest['Date'], df_latest['Ind_5MA']/scale, label='散户5周均线', color='#ff7f0e')
            ax2.axhline(0, color='black', linestyle='--')
            ax2.set_title(f'{stock_code} ({stock_name}) 5周移动平均线\n{date_range_label}')
            ax2.set_xlabel('日期')
            ax2.set_ylabel(f'资金流 ({unit})')
            ax2.legend()
            ax2.grid(alpha=0.3)
            pdf.savefig(fig2, bbox_inches='tight')
            plt.close(fig2)
            
            # ---------- Plot 3: IDR and FBI Trends ----------
            fig3, ax3 = plt.subplots(figsize=(11, 6))
            ax3.plot(df_latest['Date'], df_latest['IDR'], label='IDR (机构主导比率)', color='#2ca02c')
            ax3.plot(df_latest['Date'], df_latest['FBI'], label='FBI (资金流平衡指标)', color='#d62728')
            ax3.axhline(0.5, color='gray', linestyle='--', alpha=0.5)
            ax3.axhline(0, color='black', linestyle='--')
            ax3.set_title(f'{stock_code} ({stock_name}) IDR & FBI 指标\n{date_range_label}')
            ax3.set_xlabel('日期')
            ax3.set_ylabel('比率')
            ax3.legend()
            ax3.grid(alpha=0.3)
            pdf.savefig(fig3, bbox_inches='tight')
            plt.close(fig3)
            
            # ---------- Stacked bar charts ----------
            period_cache = {}
            all_periods = {20, 60, 'AP', 5, 10}
            for p in all_periods:
                if isinstance(p, int) and len(df) >= p:
                    period_cache[p] = (f"最新{p}周", df.tail(p))
                elif p == 'AP':
                    period_cache['AP'] = (f"分析期间\n{date_range_label}", df_latest)
            
            # 中长期分组堆叠柱状图
            plot1 = create_grouped_stacked_bars(stock_code, date_range_label, period_cache, [20, 60, 'AP'])
            if plot1 and os.path.exists(plot1):
                fig4 = plt.imread(plot1)
                fig4_plot, ax4 = plt.subplots(figsize=(11, 6))
                ax4.imshow(fig4)
                ax4.axis('off')
                pdf.savefig(fig4_plot, bbox_inches='tight')
                plt.close(fig4_plot)
            
            # 短期分组堆叠柱状图
            plot2 = create_grouped_stacked_bars(stock_code, date_range_label, period_cache, [5, 10, 20])
            if plot2 and os.path.exists(plot2):
                fig5 = plt.imread(plot2)
                fig5_plot, ax5 = plt.subplots(figsize=(11, 6))
                ax5.imshow(fig5)
                ax5.axis('off')
                pdf.savefig(fig5_plot, bbox_inches='tight')
                plt.close(fig5_plot)
        
        # 清理临时文件
        temp_files = [plot1, plot2] if 'plot1' in locals() and 'plot2' in locals() else []
        for p in temp_files:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        
        # 检查PDF是否成功生成
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1024:
            return True
        else:
            logger.error(f"{stock_code}: PDF文件生成失败或文件为空: {pdf_path}")
            return False
            
    except Exception as e:
        logger.error(f"{stock_code}: 生成PDF报告时出错: {str(e)}")
        traceback.print_exc()
        return False

def process_single_ticker(ticker, CONFIG):
    """
    处理单个股票的完整分析流程（用于并行处理）
    包括：计算指标、保存到数据库、生成PDF报告
    
    Args:
        ticker (str): 股票代码
        CONFIG (dict): 配置字典
    
    Returns:
        tuple: (ticker, success, message)
    """
    try:
        logger = get_logger()
        
        # 检查数据状态
        needs_processing, status_msg, _, _ = check_and_process_stock(ticker)
        logger.info(f"{status_msg}")
        
        # 准备PDF路径
        pdf_path = os.path.join(GlobalConfig.full_report_dir, f"{ticker}_weekly_moneyflow_analysis.pdf")
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        
        # 无论PDF是否存在，都强制重新生成
        if not needs_processing:
            # 数据已存在，强制重新生成PDF（覆盖旧文件）
            if generate_moneyflow_pdf(ticker, pdf_path):
                logger.info(f"✅ {ticker}: PDF报告已重新生成: {pdf_path}")
                return (ticker, True, f"PDF报告已重新生成: {pdf_path}")
            else:
                logger.error(f"❌ {ticker}: PDF报告生成失败: {pdf_path}")
                return (ticker, False, f"PDF报告生成失败: {pdf_path}")
        
        # 读取原始数据
        df_source = read_moneyflow_from_db(ticker)
        if df_source.empty:
            logger.error(f"❌ {ticker}: 原始数据为空")
            return (ticker, False, "原始数据为空")
        
        # 获取已有的分析数据（用于增量更新）
        conn = get_db_connection()
        existing_df = pd.read_sql_query(
            "SELECT * FROM hk_weekly_moneyflow_analysis WHERE stock_code = ?",
            conn, params=(ticker,)
        )
        conn.close()
        
        # 如果有已存在的数据，只处理新增的数据
        if not existing_df.empty:
            # 注意：existing_df中的日期已经是矫正后的星期五日期
            existing_dates = set(existing_df['date'].values)
            df_source = df_source[~df_source['date'].isin(existing_dates)]
            if df_source.empty:
                # 数据无新增，但强制重新生成PDF（覆盖旧文件）
                if generate_moneyflow_pdf(ticker, pdf_path):
                    logger.info(f"✅ {ticker}: PDF报告已重新生成: {pdf_path}")
                    return (ticker, True, f"PDF报告已重新生成: {pdf_path}")
                else:
                    logger.error(f"❌ {ticker}: PDF报告生成失败: {pdf_path}")
                    return (ticker, False, f"PDF报告生成失败: {pdf_path}")
        
        # 计算指标（内部会进行日期矫正）
        df_analysis = calculate_money_flow_indicator_df(df_source)
        
        # 保存到数据库（内部会再次确保日期矫正）
        if not save_analysis_to_db(df_analysis, ticker):
            logger.error(f"❌ {ticker}: 保存到数据库失败")
            return (ticker, False, "保存到数据库失败")
        
        logger.info(f"{ticker}: ✅ 资金流指标计算完成，更新了 {len(df_analysis)} 条记录")
        
        # 生成PDF报告
        if generate_moneyflow_pdf(ticker, pdf_path):
            logger.info(f"✅ {ticker}: PDF报告已生成: {pdf_path}")
            return (ticker, True, f"成功更新 {len(df_analysis)} 条记录，PDF报告已生成: {pdf_path}")
        else:
            logger.error(f"❌ {ticker}: PDF报告生成失败: {pdf_path}")
            return (ticker, False, f"数据更新成功但PDF生成失败: {pdf_path}")
        
    except Exception as e:
        error_msg = f"处理 {ticker} 时发生错误: {str(e)}"
        logger = get_logger()
        logger.error(f"❌ {ticker}: {error_msg}")
        traceback.print_exc()
        return (ticker, False, error_msg)

def process_tickers_parallel(tickers, max_workers=None, use_processes=False):
    """
    并行处理多个股票
    
    Args:
        tickers (list): 股票代码列表
        max_workers (int): 最大并行工作进程/线程数
        use_processes (bool): True使用ProcessPoolExecutor，False使用ThreadPoolExecutor
    
    Returns:
        dict: 处理结果统计
    """
    logger = get_logger()
    
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, len(tickers))
    
    logger.info(f"🚀 启动并行处理: {len(tickers)} 个股票, {max_workers} 个工作进程/线程")
    logger.info(f"📋 股票列表: {tickers}")
    logger.info("=" * 60)
    
    results = []
    start_time = time.time()
    
    if use_processes:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_ticker, ticker, None): ticker 
                      for ticker in tickers}
            
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    result = future.result(timeout=300)
                    results.append(result)
                    status = "✅" if result[1] else "❌"
                    logger.info(f"{status} {result[0]}: {result[2]}")
                except Exception as e:
                    results.append((ticker, False, f"超时或异常: {str(e)}"))
                    logger.error(f"❌ {ticker}: 处理失败 - {str(e)}")
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_ticker, ticker, None): ticker 
                      for ticker in tickers}
            
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    result = future.result(timeout=300)
                    results.append(result)
                    status = "✅" if result[1] else "❌"
                    logger.info(f"{status} {result[0]}: {result[2]}")
                except Exception as e:
                    results.append((ticker, False, f"超时或异常: {str(e)}"))
                    logger.error(f"❌ {ticker}: 处理失败 - {str(e)}")
    
    elapsed_time = time.time() - start_time
    successful = sum(1 for r in results if r[1])
    failed = len(results) - successful
    
    logger.info("=" * 60)
    logger.info(f"📊 处理完成统计:")
    logger.info(f"   ✅ 成功: {successful}")
    logger.info(f"   ❌ 失败: {failed}")
    logger.info(f"   ⏱️  总用时: {elapsed_time:.2f} 秒")
    logger.info(f"   🚀 平均每个股票: {elapsed_time/len(tickers):.2f} 秒")
    
    if failed > 0:
        logger.info("\n❌ 失败的股票:")
        for ticker, success, msg in results:
            if not success:
                logger.info(f"   - {ticker}: {msg}")
    
    return {
        'total': len(results),
        'successful': successful,
        'failed': failed,
        'results': results,
        'elapsed_time': elapsed_time
    }

# ==================== 主函数 ====================

def main():
    """主函数，程序的入口点"""
    global logger
    
    try:
        # ========== 主程序路径配置 ==========
        # 构建配置文件路径
        config_path = os.path.join(project_dir, 'Config', 'stock_data_analysis.par')

        # ========== 加载配置 ==========
        CONFIG = load_config(config_path, project_dir)
        print(f"配置文件加载成功: {config_path}")

        # 更新全局路径配置
        GlobalConfig.update_paths(CONFIG, project_dir)
        
        # 初始化日志系统
        logger = setup_logger(GlobalConfig.full_log_dir)
        logger.info("=" * 80)
        logger.info("Weekly_TA4B_Analyze_MoneyFlow 启动")
        logger.info("=" * 80)

        # ========== 打印配置信息 ==========
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件位置: {config_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"报告目录: {GlobalConfig.full_report_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        logger.info(f"SQLite数据库目录: {GlobalConfig.full_sqlite_dir}")
        logger.info(f"数据库文件: {GlobalConfig.full_db_path}")

        # 检查数据库是否存在
        if not os.path.exists(GlobalConfig.full_db_path):
            logger.error(f"❌ 错误: 数据库文件不存在: {GlobalConfig.full_db_path}")
            return

        # ========== 从配置文件读取股票列表（参考 Weekly_TA3 的方法） ==========
        if CONFIG.get('tickers'):
            tickers = CONFIG['tickers']
            logger.info(f"📋 从配置文件读取到 {len(tickers)} 个股票代码")
            if len(tickers) > 5:
                logger.info(f"前5个股票代码: {tickers[:5]}... 等")
            else:
                logger.info(f"股票代码: {tickers}")
        else:
            logger.warning("⚠️ 配置文件中未找到 tickers 设置")
            # 后备方案：从 stock_list.json 读取
            logger.info("尝试从 stock_list.json 读取股票列表...")
            tickers = get_stock_list_from_db()
            if not tickers:
                logger.error("❌ 错误: 无法从任何来源获取股票列表")
                return
            logger.info(f"从 stock_list.json 读取到 {len(tickers)} 个股票代码")
            if len(tickers) > 5:
                logger.info(f"前5个股票代码: {tickers[:5]}... 等")
            else:
                logger.info(f"股票代码: {tickers}")

        # ========== 选择处理模式 ==========
        parallel_config = CONFIG.get('parallel_processing', {})
        use_parallel = parallel_config.get('enabled', True)
        max_workers = parallel_config.get('max_workers', None)
        use_processes = parallel_config.get('use_processes', False)
        
        logger.info("\n" + "=" * 60)
        logger.info("⚙️  并行处理配置:")
        logger.info(f"  启用并行: {use_parallel}")
        if use_parallel:
            logger.info(f"  最大工作进程/线程: {max_workers or '自动'}")
            logger.info(f"  使用进程池: {use_processes} (True=进程, False=线程)")
        logger.info("=" * 60 + "\n")

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"{current_time} 开始分析周资金流指标...")

        # 先检查所有股票的状态
        logger.info("\n📊 检查股票数据状态:")
        for ticker in tickers:
            _, status_msg, _, _ = check_and_process_stock(ticker)
            logger.info(f"   {status_msg}")

        logger.info("\n" + "=" * 60)

        if use_parallel and len(tickers) > 1:
            # 并行处理
            result_stats = process_tickers_parallel(tickers, max_workers, use_processes)
            
            if result_stats['successful'] == 0:
                logger.error("❌ 所有股票处理都失败了，请检查错误信息")
                return
        else:
            # 串行处理
            logger.info("🔄 使用串行处理模式...")
            for ticker in tickers:
                process_single_ticker(ticker, CONFIG)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"\n{current_time} ✅ 全部周资金流指标分析完成！")
        logger.info("=" * 80)

    except Exception as e:
        error_msg = f"发生未知错误: {type(e).__name__}: {e}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
        traceback.print_exc()

        if 'get_ipython' not in globals():
            sys.exit(1)

if __name__ == "__main__":
    main()