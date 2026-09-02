#!/usr/bin/env python
# coding: utf-8

"""
Step 5: Analyze chip signals.
Source code: Daily_TA3B_Chip_Signal_Analysis.py
Input data:     hk_daily_kline_analysis
Output data:    daily_chip_signal_analysis.pdf
Function：
1. 读取交易数据及技术分析指标数据（从SQLite数据库读取）
2. 采用价格振幅法进行筹码集中度分析，适用于进行突破有效性验证。
3. 分析结果保存到SQLite数据库表：hk_daily_kline_analysis
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.pylab import date2num
from mplfinance.original_flavor import candlestick_ohlc
import matplotlib.gridspec as gridspec 
import matplotlib.dates as mdates
import os
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib as mpl
import warnings
import sys
import io
from datetime import datetime, timedelta
import time
from pathlib import Path
import traceback
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
import warnings

# ===== 屏蔽字体警告 =====
# 1. 设置 matplotlib 日志级别
logging.getLogger('matplotlib').setLevel(logging.ERROR)
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
logging.getLogger('matplotlib.backends').setLevel(logging.ERROR)

# 2. 过滤特定警告信息
warnings.filterwarnings("ignore", message="Failed to find font weight bold")
warnings.filterwarnings("ignore", message="Glyph.*missing from font")
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
warnings.filterwarnings("ignore", category=UserWarning, message=".*missing from font.*")

# 3. 设置字体权重避免使用 bold
plt.rcParams['font.weight'] = 'normal'
mpl.rcParams['font.weight'] = 'normal'


# 设置中文字体支持
def set_chinese_font():
    """设置中文字体支持"""
    try:
        # 尝试使用系统字体
        if sys.platform == 'win32':
            # Windows系统
            font_path = 'C:/Windows/Fonts/simhei.ttf'  # 黑体
            if os.path.exists(font_path):
                plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
                plt.rcParams['axes.unicode_minus'] = False
                plt.rcParams['font.weight'] = 'normal'   # 解决粗体找不到的问题
            else:
                font_path = 'C:/Windows/Fonts/msyh.ttc'  # 微软雅黑
                plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
                plt.rcParams['axes.unicode_minus'] = False
                plt.rcParams['font.weight'] = 'normal'   # 解决粗体找不到的问题
        elif sys.platform == 'darwin':
            # macOS系统
            font_path = '/System/Library/Fonts/PingFang.ttc'  # 苹方
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False
            plt.rcParams['font.weight'] = 'normal'   # 解决粗体找不到的问题
        else:
            # Linux系统
            font_path = '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False
            plt.rcParams['font.weight'] = 'normal'   # 解决粗体找不到的问题

        # 检查字体文件是否存在
        if os.path.exists(font_path):
            # 注册字体
            font_prop = fm.FontProperties(fname=font_path)
            plt.rcParams['font.family'] = font_prop.get_name()
            return True

        # 设置回退方案
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.weight'] = 'normal'   # 解决粗体找不到的问题
        return True
    except:
        # 最终回退方案
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.weight'] = 'normal'   # 解决粗体找不到的问题
        return False

# 设置中文支持
set_chinese_font()

# 确保负号显示正常
plt.rcParams['axes.unicode_minus'] = False

# 全局logger
logger = None
def setup_logger(log_dir, log_name='Daily_TA3B_Chip_Signal_Analysis.log'):
    """
    设置日志记录器
    
    参数:
        log_dir (str): 日志目录路径
        log_name (str): 日志文件名
    
    返回:
        logging.Logger: 配置好的logger对象
    """
    global logger
    
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, log_name)
    
    # 创建logger
    logger = logging.getLogger('Daily_TA3B_Chip_Signal_Analysis')
    logger.setLevel(logging.DEBUG)
    
    # 如果已经有handler，先清除
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建文件handler - 使用 'w' 模式直接覆盖原有文件
    file_handler = logging.FileHandler(
        log_file, 
        mode='w',  # 'w' 模式会覆盖原有文件
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 创建控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加handler到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 记录启动信息
    logger.info("=" * 80)
    logger.info(f"日志系统初始化完成")
    logger.info(f"日志文件: {log_file}")
    logger.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    return logger

def log_decorator(func):
    """日志装饰器，用于记录函数调用"""
    def wrapper(*args, **kwargs):
        global logger
        func_name = func.__name__
        if logger:
            logger.debug(f"开始执行函数: {func_name}")
        try:
            result = func(*args, **kwargs)
            if logger:
                logger.debug(f"函数执行完成: {func_name}")
            return result
        except Exception as e:
            if logger:
                logger.error(f"函数 {func_name} 执行出错: {str(e)}")
                logger.error(traceback.format_exc())
            raise
    return wrapper


def read_data_from_db(db_path, ticker, start_date=None, end_date=None):
    """
    从SQLite数据库读取K线数据和技术分析指标数据
    
    参数:
        db_path (str): 数据库文件路径
        ticker (str): 股票代码
        start_date (str): 开始日期 (格式: 'YYYY-MM-DD')
        end_date (str): 结束日期 (格式: 'YYYY-MM-DD')
    
    返回:
        pd.DataFrame: 包含K线数据和技术分析指标的数据框
    """
    global logger
    try:
        if logger:
            logger.info(f"开始从数据库读取股票 {ticker} 的数据")
            logger.debug(f"数据库路径: {db_path}")
            logger.debug(f"日期范围: {start_date} 至 {end_date}")
        
        conn = sqlite3.connect(db_path)
        
        # 先获取表的所有列名
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(hk_daily_kline_analysis)")
        columns_info = cursor.fetchall()
        all_columns = [col[1] for col in columns_info]
        
        if logger:
            logger.debug(f"表 hk_daily_kline_analysis 共有 {len(all_columns)} 个字段")
        
        # 基础列（必须存在的列）- 修改为小写
        base_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        
        # 从所有列中排除id列
        select_columns = [col for col in all_columns if col != 'id']
        
        # 如果没有指定要选择的列，使用所有列 - 修改为小写
        if not select_columns:
            select_columns = ['date', 'open', 'high', 'low', 'close', 'volume', 
                            'amount', 'amplitude', 'change_percent', 'change_amount',
                            'turnover_rate', 'previous_close', 'avg_price', 'close_chgpct',
                            'avg_volume_5d', 'volume_ratio5', 'avg_volume_20d', 'volume_ratio20']
        
        # 构建查询语句
        query = f"""
        SELECT {', '.join(select_columns)}
        FROM hk_daily_kline_analysis
        WHERE stock_code = ?
        """
        
        params = [ticker]
        
        # 添加日期范围条件
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
            
        # 按日期排序
        query += " ORDER BY date ASC"
        
        if logger:
            logger.debug(f"执行SQL查询: {query}")
        
        # 执行查询
        df = pd.read_sql_query(query, conn, params=params)
        
        conn.close()
        
        if df.empty:
            if logger:
                logger.warning(f"在数据库中未找到股票 {ticker} 的数据")
            print(f"警告: 在数据库中未找到股票 {ticker} 的数据")
            return df
            
        # 将date列转换为datetime类型
        df['Date'] = pd.to_datetime(df['date'])
        df.set_index('Date', inplace=True)
        df.drop('date', axis=1, inplace=True)
        
        if logger:
            logger.info(f"成功从数据库读取 {len(df)} 条记录，包含 {len(df.columns)} 个字段")
            logger.debug(f"数据日期范围: {df.index.min()} 至 {df.index.max()}")
        
        print(f"成功从数据库读取 {len(df)} 条记录，包含 {len(df.columns)} 个字段")
        return df
        
    except Exception as e:
        error_msg = f"从数据库读取数据时出错: {e}"
        if logger:
            logger.error(error_msg)
            logger.error(traceback.format_exc())
        print(f"错误: {error_msg}")
        traceback.print_exc()
        return pd.DataFrame()


def save_analysis_to_db(db_path, ticker, stock_name, analysis_data):
    """
    将K线分析结果保存到SQLite数据库
    
    参数:
        db_path (str): 数据库文件路径
        ticker (str): 股票代码
        stock_name (str): 股票名称
        analysis_data (pd.DataFrame): 分析数据（包含所有指标列）
    """
    global logger
    try:
        if logger:
            logger.info(f"开始保存股票 {ticker} 的分析数据到数据库")
            logger.debug(f"数据记录数: {len(analysis_data)}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取表的列名
        cursor.execute("PRAGMA table_info(hk_daily_kline_analysis)")
        columns_info = cursor.fetchall()
        existing_columns = [col[1] for col in columns_info if col[1] != 'id']
        
        if logger:
            logger.debug(f"表 hk_daily_kline_analysis 可写字段数: {len(existing_columns)}")
        
        # 获取当前时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 准备插入或更新数据
        saved_count = 0
        updated_count = 0
        inserted_count = 0
        
        for index, row in analysis_data.iterrows():
            date_str = index.strftime("%Y-%m-%d")
            
            # 检查记录是否存在
            check_query = """
            SELECT COUNT(*) FROM hk_daily_kline_analysis 
            WHERE stock_code = ? AND date = ?
            """
            cursor.execute(check_query, (ticker, date_str))
            exists = cursor.fetchone()[0] > 0
            
            # 准备需要保存的字段
            save_columns = []
            save_values = []
            
            for col in existing_columns:
                if col in row.index:
                    save_columns.append(col)
                    value = row[col]
                    # 处理NaN值
                    if pd.isna(value):
                        value = None
                    save_values.append(value)
            
            if not save_columns:
                if logger:
                    logger.warning(f"日期 {date_str} 没有可保存的字段")
                continue
            
            if exists:
                # 更新现有记录
                set_clause = ', '.join([f"{col} = ?" for col in save_columns])
                update_query = f"""
                UPDATE hk_daily_kline_analysis 
                SET {set_clause}
                WHERE stock_code = ? AND date = ?
                """
                values = save_values + [ticker, date_str]
                cursor.execute(update_query, values)
                updated_count += 1
            else:
                # 插入新记录
                # 确保stock_code和date在要保存的字段中
                if 'stock_code' not in save_columns:
                    save_columns.insert(0, 'stock_code')
                    save_values.insert(0, ticker)
                if 'stock_name' not in save_columns:
                    save_columns.insert(1, 'stock_name')
                    save_values.insert(1, stock_name)
                if 'date' not in save_columns:
                    save_columns.append('date')
                    save_values.append(date_str)
                
                insert_query = f"""
                INSERT INTO hk_daily_kline_analysis ({', '.join(save_columns)})
                VALUES ({', '.join(['?'] * len(save_values))})
                """
                cursor.execute(insert_query, save_values)
                inserted_count += 1
            
            saved_count += 1
        
        conn.commit()
        conn.close()
        
        if logger:
            logger.info(f"成功保存 {saved_count} 条记录到数据库 (新增: {inserted_count}, 更新: {updated_count})")
        
        print(f"成功将 {saved_count} 条分析记录保存到数据库 (新增: {inserted_count}, 更新: {updated_count})")
        
    except Exception as e:
        error_msg = f"保存数据到数据库时出错: {e}"
        if logger:
            logger.error(error_msg)
            logger.error(traceback.format_exc())
        print(f"错误: {error_msg}")
        traceback.print_exc()


# 绘制K线图并标记市场筹码分析信号
def visualize_chip_signals(data, pdf_path, ticker, start_date=None, end_date=None):
    """
    读取交易数据，绘制K线图并标记市场筹码分析信号，同时列出所有信号日期

    参数:
        data (pd.DataFrame): 包含K线数据和技术指标的数据框
        pdf_path (str): PDF保存路径
        ticker (str): 股票代码
        start_date (str): 分析开始日期 (格式: 'YYYY-MM-DD')
        end_date (str): 分析结束日期 (格式: 'YYYY-MM-DD')
    """
    global logger
    try:
        if logger:
            logger.info(f"开始生成股票 {ticker} 的筹码信号分析图表")
            logger.debug(f"PDF输出路径: {pdf_path}")
        
        # 设置支持更广泛字符的字体
        plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用默认字体
        plt.rcParams['axes.unicode_minus'] = False    # 解决负号显示问题

        # 确保数据不为空
        if data.empty:
            error_msg = f"股票 {ticker} 无数据可分析"
            if logger:
                logger.error(error_msg)
            print(f"错误: {error_msg}")
            return None, None

        # 记录原始数据日期范围
        original_start = data.index.min()
        original_end = data.index.max()

        # 修正日期范围（确保不超过数据边界）
        if start_date:
            start_date = pd.to_datetime(start_date)
            if start_date < original_start:  # 如果早于数据最早日期
                start_date = original_start  # 修正为数据最早日期
        else:
            start_date = original_start

        if end_date:
            end_date = pd.to_datetime(end_date)
            if end_date > original_end:  # 如果晚于数据最晚日期
                end_date = original_end   # 修正为数据最晚日期
        else:
            end_date = original_end

        # 应用日期范围过滤
        mask = (data.index >= start_date) & (data.index <= end_date)
        data = data.loc[mask].copy()

        # 检查过滤后的数据是否为空
        if data.empty:
            warn_msg = f"在指定日期范围 {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')} 内没有数据"
            if logger:
                logger.warning(warn_msg)
            print(f"警告: {warn_msg}")
            return None, None	

        date_range_str = f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"
        if logger:
            logger.info(f"分析日期范围: {date_range_str}")
        print(f"分析日期范围: {date_range_str}")

        # 3. 准备信号数据 - 检查哪些信号列存在
        signal_cols = [
            'bottom_signal_cond', 'top_signal_cond',
            'bottom_entry_signal_cond', 'top_exit_signal_cond',
            'continuation_signal_cond', 'decline_continuation_cond',
            'accumulation_cond', 'distribution_cond',
            'multi_timeframe_chip_confirm_bottom_cond',
            'multi_timeframe_chip_confirm_top_cond'
        ]
        
        # 为每个信号列添加默认值（False），如果不存在的话
        for col in signal_cols:
            if col not in data.columns:
                data[col] = False
                if logger:
                    logger.debug(f"添加默认信号列: {col} (所有值为False)")
                print(f"  添加默认信号列: {col} (所有值为False)")
            else:
                # 确保信号列是布尔类型
                try:
                    # 尝试转换为布尔类型
                    data[col] = data[col].astype(bool)
                    if logger:
                        logger.debug(f"信号列 {col} 已转换为布尔类型")
                except Exception as e:
                    # 如果转换失败，使用值 > 0 来判断
                    try:
                        data[col] = data[col] > 0
                        if logger:
                            logger.debug(f"信号列 {col} 已转换为布尔类型 (使用 > 0)")
                    except:
                        # 如果还是失败，使用字符串比较
                        data[col] = data[col].astype(str).str.lower() == 'true'
                        if logger:
                            logger.debug(f"信号列 {col} 已转换为布尔类型 (使用字符串比较)")
                print(f"  信号列 {col} 已转换为布尔类型")

        # 检查是否存在信号列
        existing_signals = [col for col in signal_cols if col in data.columns]
        missing_signals = [col for col in signal_cols if col not in data.columns]
        
        if missing_signals:
            warn_msg = f"以下信号列不存在，已添加为默认False: {', '.join(missing_signals)}"
            if logger:
                logger.warning(warn_msg)
            print(f"警告: {warn_msg}")
            print("提示: 这些信号需要在数据导入时计算，或通过其他程序生成")

        # 4. 创建信号报告
        signal_report = {}
        for col in signal_cols:
            # 获取信号为True的日期 - 使用安全的方式
            if col in data.columns:
                # 确保是布尔类型
                bool_series = data[col].astype(bool)
                signal_dates = data.index[bool_series].tolist()
                signal_report[col] = signal_dates
            else:
                signal_report[col] = []

        # 6. 创建图表 - 增加整体高度以适应新子图
        fig = plt.figure(figsize=(16, 28), dpi=100)  # 调整为28以适应新子图

        # 创建网格布局: 调整为7个子图
        gs = gridspec.GridSpec(7, 1, height_ratios=[3, 1, 1, 2, 1, 1, 1.2])  # 增加一个新位置

        # 创建子图
        ax1 = plt.subplot(gs[0])  # K线图
        ax2 = plt.subplot(gs[1], sharex=ax1)  # 成交量
        ax3 = plt.subplot(gs[2], sharex=ax1)  # 价格振幅 筹码集中度
        ax4 = plt.subplot(gs[3], sharex=ax1)  # 信号时间线
        ax5 = plt.subplot(gs[4], sharex=ax1)  # 新子图：成本价差 筹码集中度
        ax6 = plt.subplot(gs[5], sharex=ax1)  # 收盘价
        ax7 = plt.subplot(gs[6], sharex=ax1)  # MACD技术指标示例（作为主时间轴）

        # 设置标题
        symbol = ticker
        plt.suptitle(f'{symbol} - 市场筹码分析信号\n分析期间: {date_range_str}', 
                    fontsize=18, fontweight='bold', y=0.97)  # 调整y位置

        # 7. 绘制K线图（蜡烛图）- 修改为小写列名
        # 准备OHLC数据
        ohlc_data = data[['open', 'high', 'low', 'close']].reset_index()
        ohlc_data['Date_num'] = ohlc_data['Date'].map(mdates.date2num)
        ohlc_values = ohlc_data[['Date_num', 'open', 'high', 'low', 'close']].values

        # 绘制蜡烛图
        candlestick_ohlc(ax1, ohlc_values, width=0.6, colorup='g', colordown='r', alpha=0.8)

        # 添加移动平均线 - 修改为小写列名
        if 'ema5' in data.columns and 'ema20' in data.columns:
            ax1.plot(data.index, data['ema5'], label='5日均线', color='blue', linewidth=1.5, alpha=0.7)
            ax1.plot(data.index, data['ema20'], label='20日均线', color='orange', linewidth=1.5, alpha=0.7)

        # 设置K线图属性
        ax1.set_ylabel('价格', fontsize=12)
        ax1.grid(True, alpha=0.3)
        # 只有当有标签时才显示图例
        if ax1.get_legend_handles_labels()[1]:
            ax1.legend(loc='best', fontsize=10)

        # 8. 绘制成交量 - 修改为小写列名
        # 计算涨跌颜色
        colors = ['g' if close >= open_ else 'r' for open_, close in zip(data['open'], data['close'])]
        ax2.bar(data.index, data['volume'], color=colors, width=0.6, alpha=0.8)

        # 添加成交量均线 - 修改为小写列名
        if 'vol_ema5' in data.columns and 'vol_ema20' in data.columns:
            ax2.plot(data.index, data['vol_ema5'], label='5日成交量均线', color='blue', linewidth=1.5)
            ax2.plot(data.index, data['vol_ema20'], label='20日成交量均线', color='orange', linewidth=1.5)

        # 设置成交量图属性
        ax2.set_ylabel('成交量', fontsize=12)
        ax2.grid(True, alpha=0.3)
        # 只有当有标签时才显示图例
        if ax2.get_legend_handles_labels()[1]:
            ax2.legend(loc='best', fontsize=10)

        # 9. 添加筹码集中度图表（价格振幅 筹码集中度）- 修改为小写列名
        if 'price_amp_market_chip_concentration' in data.columns:
            # 绘制筹码集中度曲线
            ax3.plot(data.index, data['price_amp_market_chip_concentration'], 
                     label='价格振幅 筹码集中度(%)', color='#7B1FA2', linewidth=2)

            # 添加参考线
            ax3.axhline(25, color='#4CAF50', linestyle='--', alpha=0.7)
            ax3.axhline(50, color='#9E9E9E', linestyle='--', alpha=0.7)
            ax3.axhline(75, color='#F44336', linestyle='--', alpha=0.7)

            # 添加参考线标签
            ax3.text(data.index[-1], 25, '25% - 高度集中', ha='right', va='bottom', fontsize=9, color='#4CAF50')
            ax3.text(data.index[-1], 75, '75% - 高度分散', ha='right', va='top', fontsize=9, color='#F44336')

            # 设置Y轴标签
            ax3.set_ylabel('价格振幅 筹码集中度(%)', fontsize=10)

            # 设置Y轴范围
            min_concentration = max(0, data['price_amp_market_chip_concentration'].min() * 0.8)
            max_concentration = min(100, data['price_amp_market_chip_concentration'].max() * 1.2)
            ax3.set_ylim(min_concentration, max_concentration)

            # 添加网格
            ax3.grid(True, alpha=0.2)

            # 添加图例
            ax3.legend(loc='best', fontsize=10)
        else:
            warn_msg = "未找到 'price_amp_market_chip_concentration' 列，跳过绘制价格振幅筹码集中度图"
            if logger:
                logger.warning(warn_msg)
            print(f"警告: {warn_msg}")
            ax3.text(0.5, 0.5, '无价格振幅筹码集中度数据', 
                     fontsize=12, ha='center', va='center', transform=ax3.transAxes)
            ax3.set_ylabel('价格振幅 筹码集中度', fontsize=12)
            ax3.grid(True, alpha=0.2)

        # 10. 创建信号时间线（保持不变）
        ax4.set_ylabel('信号类型', fontsize=12)
        ax4.set_yticks([])
        ax4.grid(axis='x', alpha=0.2)

        # 为每个信号类型分配一个y位置和标记（保持不变）
        signal_markers = {
            'bottom_signal_cond': ('#4CAF50', '^', '底部确认信号'),
            'top_signal_cond': ('#F44336', 'v', '顶部预警信号'),
            'bottom_entry_signal_cond': ('#2E7D32', '*', '底部建仓条件'),
            'top_exit_signal_cond': ('#C62828', '*', '顶部离场条件'),
            'continuation_signal_cond': ('#2196F3', 'o', '上涨中继确认'),
            'decline_continuation_cond': ('#FF9800', 'o', '下跌中继确认'),
            'accumulation_cond': ('#9C27B0', '<', '机构吸筹信号'),
            'distribution_cond': ('#795548', '>', '机构派发信号'),
            'multi_timeframe_chip_confirm_bottom_cond': ('#8BC34A', 'd', '多周期底部共振'),
            'multi_timeframe_chip_confirm_top_cond': ('#E91E63', 'd', '多周期顶部共振')
        }

        # 增加信号间距 - 增大y_step
        signal_y_pos = {}
        y_step = 1.8  # 从1.4增加到1.8
        for i, signal in enumerate(signal_markers.keys()):
            signal_y_pos[signal] = 1 + i * y_step

        # 在时间线上标记信号（保持不变）
        for signal, y_pos in signal_y_pos.items():
            if signal in data.columns:
                # 确保是布尔类型
                bool_series = data[signal].astype(bool)
                signal_points = data[bool_series]

                if not signal_points.empty:
                    color = signal_markers[signal][0]
                    marker = signal_markers[signal][1]
                    label = signal_markers[signal][2]

                    # 在时间线上标记
                    ax4.scatter(
                        signal_points.index, 
                        [y_pos] * len(signal_points), 
                        color=color, 
                        marker=marker, 
                        s=80,
                        alpha=0.8,
                        label=label
                    )

        # 添加信号类型标签（保持不变）
        for signal, y_pos in signal_y_pos.items():
            if signal in signal_markers:
                label = signal_markers[signal][2]
                color = signal_markers[signal][0]

                # 绘制信号标签
                ax4.text(
                    data.index[0], 
                    y_pos, 
                    label, 
                    fontsize=10,
                    va='center',
                    color=color,
                    bbox=dict(facecolor='white', alpha=0.7, edgecolor='none')
                )

                # 在右侧添加信号计数
                if signal in data.columns:
                    bool_series = data[signal].astype(bool)
                    signal_count = len(data[bool_series])
                    ax4.text(
                        data.index[-1], 
                        y_pos, 
                        f"({signal_count})", 
                        fontsize=9, 
                        ha='left',
                        va='center',
                        color='black'
                    )

        # 设置Y轴范围以适应所有信号 - 增大间距
        min_y = 0.8  # 从0.5增加到0.8
        max_y = max(signal_y_pos.values()) + y_step * 0.8  # 从0.5增加到0.8
        ax4.set_ylim(min_y, max_y)

        # 11. 绘制成本价差 筹码集中度 - 修改为小写列名
        if 'cost_spread_chip_concentration' in data.columns:
            # 绘制筹码集中度曲线
            ax5.plot(data.index, data['cost_spread_chip_concentration'], 
                     label='成本价差 筹码集中度(%)', color='#FF5722', linewidth=2)  # 使用橙色

            # 添加参考线
            ax5.axhline(8, color='#4CAF50', linestyle='--', alpha=0.7)
            ax5.axhline(15, color='#F44336', linestyle='--', alpha=0.7)

            # 添加参考线标签
            ax5.text(data.index[-1], 8, '8% - 筹码高度锁定 （机构控盘）', ha='right', va='bottom', fontsize=9, color='#4CAF50')
            ax5.text(data.index[-1], 15, '15% - 筹码发散（散户主导）', ha='right', va='top', fontsize=9, color='#F44336')

            # 设置Y轴标签
            ax5.set_ylabel('成本价差 筹码集中度(%)', fontsize=10)

            # 设置Y轴范围
            min_concentration = max(0, data['cost_spread_chip_concentration'].min() * 0.8)
            max_concentration = min(100, data['cost_spread_chip_concentration'].max() * 1.2)
            ax5.set_ylim(min_concentration, max_concentration)

            # 添加网格
            ax5.grid(True, alpha=0.2)

            # 添加图例
            ax5.legend(loc='best', fontsize=10)
        else:
            warn_msg = "未找到 'cost_spread_chip_concentration' 列，跳过绘制成本价差筹码集中度图"
            if logger:
                logger.warning(warn_msg)
            print(f"警告: {warn_msg}")
            # 创建空白图
            ax5.text(0.5, 0.5, '无成本价差筹码集中度数据', 
                     fontsize=12, ha='center', va='center', transform=ax5.transAxes)
            ax5.set_ylabel('成本价差 筹码集中度', fontsize=12)
            ax5.grid(True, alpha=0.2)

        # 12. 绘制收盘价 - 修改为小写列名
        ax6.plot(data.index, data['close'], label='收盘价', color='#1976D2', linewidth=2)

        # 添加技术指标 - 修改为小写列名
        if 'ema20' in data.columns:
            ax6.plot(data.index, data['ema20'], label='20日均线', color='#FF9800', linewidth=1.5, alpha=0.8)

        if 'ema60' in data.columns:
            ax6.plot(data.index, data['ema60'], label='60日均线', color='#9C27B0', linewidth=1.5, alpha=0.8)

        # 设置属性
        ax6.set_ylabel('收盘价', fontsize=12)
        ax6.grid(True, alpha=0.3)
        ax6.legend(loc='best', fontsize=10)

        # 13. 绘制MACD指标 - 修改为小写列名
        if 'macd' in data.columns and 'dif' in data.columns and 'dea' in data.columns:
            # 绘制MACD柱状图
            colors_macd = ['g' if val >= 0 else 'r' for val in data['macd']]
            ax7.bar(data.index, data['macd'], color=colors_macd, width=0.6, alpha=0.8, label='MACD')

            # 绘制DIF和DEA线
            ax7.plot(data.index, data['dif'], label='DIF', color='blue', linewidth=1.5)
            ax7.plot(data.index, data['dea'], label='DEA', color='orange', linewidth=1.5)

            # 设置属性
            ax7.set_ylabel('MACD', fontsize=12)
            ax7.grid(True, alpha=0.3)
            ax7.legend(loc='best', fontsize=10)
        else:
            # 如果没有MACD，绘制RSI - 修改为小写列名
            if 'rsi14' in data.columns:
                ax7.plot(data.index, data['rsi14'], label='RSI14', color='#7B1FA2', linewidth=2)
                ax7.axhline(30, color='green', linestyle='--', alpha=0.5)
                ax7.axhline(70, color='red', linestyle='--', alpha=0.5)
                ax7.set_ylabel('RSI', fontsize=12)
                ax7.grid(True, alpha=0.3)
                ax7.legend(loc='best', fontsize=10)
            else:
                # 如果既没有MACD也没有RSI，显示空图
                ax7.text(0.5, 0.5, '无技术指标数据', 
                         fontsize=12, ha='center', va='center', transform=ax7.transAxes)
                ax7.set_ylabel('技术指标', fontsize=12)
                ax7.grid(True, alpha=0.2)

        # 14. 标记信号（在K线图上）- 修改为小写列名
        for signal, (color, marker, label) in signal_markers.items():
            if signal in data.columns:
                bool_series = data[signal].astype(bool)
                signal_points = data[bool_series]

                if not signal_points.empty:
                    # 计算标记位置 (避免重叠) - 使用小写列名
                    y_pos = signal_points['low'] * 0.98

                    # 标记信号点
                    ax1.scatter(
                        signal_points.index, 
                        y_pos, 
                        color=color, 
                        marker=marker,
                        s=120,
                        alpha=0.9,
                        edgecolors='white',
                        linewidths=1.5,
                        zorder=10,
                        label=label
                    )

        # 15. 设置统一的X轴范围 - 修改位置，增加左右padding
        # 计算扩展后的日期范围
        x_padding = pd.Timedelta(days=5)  # 左右各增加5天的空间
        padded_start = start_date - x_padding
        padded_end = end_date + x_padding

        plt.xlim(padded_start, padded_end)
        if logger:
            logger.debug(f"图形显示范围: {padded_start.strftime('%Y-%m-%d')} 至 {padded_end.strftime('%Y-%m-%d')}")
        print(f"图形显示范围: {padded_start.strftime('%Y-%m-%d')} 至 {padded_end.strftime('%Y-%m-%d')} (原始数据: {original_start.strftime('%Y-%m-%d')} 至 {original_end.strftime('%Y-%m-%d')})")

        # 16. 设置日期格式和旋转
        date_format = mdates.DateFormatter('%Y-%m-%d')

        # 在所有子图底部显示日期标签
        for ax in [ax1, ax2, ax3, ax4, ax5, ax6, ax7]:
            ax.xaxis.set_major_formatter(date_format)
            # 应用刻度定位器
            date_range = (end_date - start_date).days
            if date_range > 730:  # 超过2年
                locator = mdates.YearLocator()
            elif date_range > 365:  # 1-2年
                locator = mdates.MonthLocator(interval=2)
            elif date_range > 180:  # 6个月到1年
                locator = mdates.MonthLocator(interval=1)
            elif date_range > 90:   # 3-6个月
                locator = mdates.WeekdayLocator(byweekday=mdates.MO, interval=2)
            elif date_range > 30:   # 1-3个月
                locator = mdates.WeekdayLocator(byweekday=mdates.MO)
            else:                   # 少于1个月
                locator = mdates.DayLocator(interval=1)
            ax.xaxis.set_major_locator(locator)

            # 设置标签旋转和对齐方式
            plt.setp(ax.get_xticklabels(), rotation=30, ha='right', fontsize=9)

        # 重点优化底部子图的日期标签显示
        plt.setp(ax7.get_xticklabels(), rotation=45, ha='right', fontsize=9, visible=True)
        ax7.tick_params(axis='x', which='major', pad=10)  # 增加标签与图之间的间距

        # 17. 调整布局 - 增加底部空间确保标签可见
        plt.tight_layout()
        plt.subplots_adjust(
            top=0.95, 
            hspace=0.15,  # 减少垂直间距
            bottom=0.1    # 增加底部空间
        )

        # 18. 创建信号报告数据（保持不变）
        report_data = []

        for signal in signal_cols:
            if signal in signal_markers:
                signal_name = signal_markers[signal][2]
                dates = signal_report.get(signal, [])
                count = len(dates)

                # 添加到报告数据
                report_data.append({
                    '信号类型': signal_name,
                    '出现次数': count,
                    '最近出现日期': max(dates).strftime('%Y-%m-%d') if dates else '无',
                    '首次出现日期': min(dates).strftime('%Y-%m-%d') if dates else '无'
                })

        # 创建信号摘要表格
        report_df = pd.DataFrame(report_data)

        # 19. 创建最近3个月的信号数据（保持不变）
        recent_signal_data = []
        if len(data) > 0:
            three_months_ago = data.index[-1] - pd.DateOffset(months=3)
            recent_signals = data.loc[three_months_ago:].copy()

            # 构建条件：任何信号列为True
            condition = pd.Series([False] * len(recent_signals), index=recent_signals.index)
            for col in signal_cols:
                if col in recent_signals.columns:
                    condition = condition | recent_signals[col].astype(bool)
            
            signal_data = recent_signals[condition]

            if not signal_data.empty:
                for date, row in signal_data.iterrows():
                    signals = []
                    for col in signal_cols:
                        if col in signal_markers and col in row.index:
                            if row[col]:
                                signals.append(signal_markers[col][2])
                    if signals:
                        recent_signal_data.append({
                            '日期': date.strftime('%Y-%m-%d'),
                            '信号': ', '.join(signals)
                        })

        recent_signal_df = pd.DataFrame(recent_signal_data)

        # 20. 创建PDF文件（保持不变）
        # 确保输出目录存在
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        
        with PdfPages(pdf_path) as pdf:
            # 第一页：图形
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)  # 关闭图形释放内存

            # 第二页：信号报告
            fig2 = plt.figure(figsize=(11.69, 8.27))  # A4尺寸
            fig2.suptitle(f'{symbol} - 市场筹码分析信号报告\n分析期间: {date_range_str}', 
                         fontsize=16, fontweight='bold', y=0.95)

            # 创建三个子图区域：文本、信号摘要、最近信号
            gs = gridspec.GridSpec(3, 1, height_ratios=[1.5, 1, 1], hspace=0.4)

            # 第一区域：报告文本
            ax_text = fig2.add_subplot(gs[0])
            ax_text.axis('off')

            # 添加报告文本
            report_text = """
            市场筹码分析信号报告
            ===================

            本报告基于市场筹码分析理论，通过对股票交易数据的深度分析，识别出以下关键信号：

            1. 底部确认信号：市场筹码高度集中，主力资金开始建仓
            2. 顶部预警信号：市场筹码高度分散，主力资金开始出货
            3. 上涨中继确认：市场筹码在上涨过程中重新集中，预示上涨趋势将持续
            4. 下跌中继确认：市场筹码在下跌过程中重新分散，预示下跌趋势将持续
            5. 机构吸筹信号：大资金在低位持续买入，筹码逐步集中
            6. 机构派发信号：大资金在高位持续卖出，筹码逐步分散
            7. 多周期底部共振：多个时间周期同时出现底部信号，预示强支撑
            8. 多周期顶部共振：多个时间周期同时出现顶部信号，预示强阻力

            以上信号结合成交量、价格走势和技术指标，为投资者提供决策参考。
            """

            ax_text.text(0.05, 0.95, report_text, fontsize=10, 
                        ha='left', va='top', transform=ax_text.transAxes)

            # 第二区域：信号摘要表格 - 增加行高
            ax_table1 = fig2.add_subplot(gs[1])
            ax_table1.axis('off')

            if not report_df.empty:
                # 添加表格标题
                ax_table1.text(0.5, 0.95, '信号摘要', fontsize=14, fontweight='bold', 
                              ha='center', va='top', transform=ax_table1.transAxes)

                # 创建表格 - 增加行高到2.0
                table = ax_table1.table(
                    cellText=report_df.values,
                    colLabels=report_df.columns,
                    cellLoc='center',
                    loc='center',
                    colWidths=[0.25, 0.15, 0.3, 0.3],
                    bbox=[0.0, 0.0, 1.0, 0.8]  # 固定bbox位置
                )

                # 设置表格样式 - 增加行高和字体大小
                table.auto_set_font_size(False)
                table.set_fontsize(11)  # 增加字体大小
                table.scale(1, 2.0)    # 增加行高到2.0

                # 设置单元格样式 - 增加内边距
                for key, cell in table.get_celld().items():
                    cell.set_height(0.08)  # 增加单元格高度
                    cell.PAD = 0.1         # 增加内边距

            # 第三区域：最近信号表格 - 动态调整行高
            ax_table2 = fig2.add_subplot(gs[2])
            ax_table2.axis('off')

            if not recent_signal_df.empty:
                # 添加表格标题
                ax_table2.text(0.5, 0.95, '最近3个月出现的信号', fontsize=14, fontweight='bold', 
                              ha='center', va='top', transform=ax_table2.transAxes)

                # 动态计算行高
                max_signal_length = recent_signal_df['信号'].apply(len).max()
                if max_signal_length > 100:    # 超长内容
                    row_height = 2.0
                elif max_signal_length > 60:   # 中等长度
                    row_height = 1.8
                elif max_signal_length < 30:   # 短内容
                    row_height = 1.5
                else:                          # 默认
                    row_height = 1.5

                if logger:
                    logger.debug(f"信号内容最大长度: {max_signal_length}字符，自动设置行高: {row_height}")
                print(f"信号内容最大长度: {max_signal_length}字符，自动设置行高: {row_height}")

                # 创建表格（直接使用动态行高）
                table2 = ax_table2.table(
                    cellText=recent_signal_df.values,
                    colLabels=recent_signal_df.columns,
                    cellLoc='center',
                    loc='center',
                    colWidths=[0.3, 0.7],
                    bbox=[0.0, 0.0, 1.0, 0.8]
                )

                # 应用样式
                table2.auto_set_font_size(False)
                table2.set_fontsize(10)
                table2.scale(1, row_height)

                # 优化单元格显示
                for key, cell in table2.get_celld().items():
                    cell.set_height(0.07)
                    cell.PAD = 0.05
            else:
                # 如果没有最近信号
                ax_table2.text(0.5, 0.5, '最近3个月无信号出现', 
                              fontsize=12, ha='center', va='center')

            # 调整布局 - 增加顶部和底部边距
            fig2.subplots_adjust(top=0.85, bottom=0.05, left=0.1, right=0.9, hspace=0.6)

            # 保存第二页
            pdf.savefig(fig2, bbox_inches='tight')
            plt.close(fig2)

        if logger:
            logger.info(f"PDF报告已保存为: {pdf_path}")
        print(f"PDF报告已保存为: {pdf_path}")

        # 返回信号报告
        return report_df, recent_signal_df

    except Exception as e:
        error_msg = f"处理数据时出错: {e}"
        if logger:
            logger.error(error_msg)
            logger.error(traceback.format_exc())
        print(f"错误: {error_msg}")
        traceback.print_exc()
        return None, None


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
        GlobalConfig,
        get_validated_dates
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
    global logger
    try:
        # ========== 主程序路径配置 ==========        
        # 构建配置文件路径：父目录下的config文件夹中的stock_data_analysis.par
        config_path = os.path.join(project_dir, 'config', 'stock_data_analysis.par')
        config_file = 'stock_data_analysis.par'

        # ========== 加载配置 ==========
        # 使用load_config函数加载配置
        CONFIG = load_config(config_path, project_dir)
        print(f"配置文件加载成功: {config_path}")

        # 更新全局路径配置
        GlobalConfig.update_paths(CONFIG, project_dir)

        # ========== 初始化日志系统 ==========
        # 设置日志目录和文件
        log_dir = GlobalConfig.full_log_dir
        log_name = 'Daily_TA3B_Chip_Signal_Analysis.log'
        logger = setup_logger(log_dir, log_name)

        # ========== 打印配置信息 ==========
        print("=" * 50)
        print(f"项目目录: {project_dir}")
        print(f"配置文件位置: {config_path}")
        print(f"数据目录: {GlobalConfig.full_data_dir}")
        print(f"报告目录: {GlobalConfig.full_report_dir}")
        print(f"日志目录: {GlobalConfig.full_log_dir}")
        print(f"日志文件: {os.path.join(log_dir, log_name)}")
        
        logger.info("程序启动")
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件: {config_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"报告目录: {GlobalConfig.full_report_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        
        # 数据库路径
        db_path = os.path.join(project_dir, 'SQLiteDB', 'HK_Stock.db')
        print(f"数据库路径: {db_path}")
        logger.info(f"数据库路径: {db_path}")

        if CONFIG.get('tickers'):
            tickers = CONFIG['tickers']
            print(f"股票代码数量: {len(tickers)}")
            logger.info(f"股票代码数量: {len(tickers)}")
            if len(tickers) > 5:
                print(f"前5个股票代码: {tickers[:5]}... 等")
                logger.info(f"前5个股票代码: {tickers[:5]}... 等")
            else:
                print(f"股票代码: {tickers}")
                logger.info(f"股票代码: {tickers}")
        else:
            warn_msg = "配置文件中未找到tickers设置"
            print(f"警告: {warn_msg}")
            logger.warning(warn_msg)

        # ========== 根据配置生成技术分析指标报告 ==========
        try:
            # 获取并验证日期范围
            start_date, end_date = get_validated_dates(CONFIG, project_dir)
            print(f"📅 验证通过的日期范围:")
            print(f"开始日期: {start_date.strftime('%Y-%m-%d')}")
            print(f"结束日期: {end_date.strftime('%Y-%m-%d')}")
            logger.info(f"验证通过的日期范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")

            # 进行技术分析
            if not tickers:
                error_msg = "无法进行筹码信号技术分析 - 没有配置股票代码"
                print(f"错误: {error_msg}")
                logger.error(error_msg)
            else:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"{current_time} 开始进行筹码信号技术分析...")
                logger.info(f"开始进行筹码信号技术分析，共 {len(tickers)} 只股票")
                
                # 从配置文件获取股票名称映射（如果有）
                stock_names = CONFIG.get('stock_names', {})
                
                for ticker in tickers:
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n{current_time} 正在分析股票 {ticker} 的筹码信号...")
                    logger.info(f"开始分析股票 {ticker}")

                    # 从数据库读取K线数据和技术指标数据
                    data = read_data_from_db(
                        db_path=db_path,
                        ticker=ticker,
                        start_date=start_date.strftime('%Y-%m-%d'),
                        end_date=end_date.strftime('%Y-%m-%d')
                    )
                    
                    if data.empty:
                        warn_msg = f"股票 {ticker} 在数据库中无数据，跳过分析"
                        print(f"警告: {warn_msg}")
                        logger.warning(warn_msg)
                        continue
                    
                    # 获取股票名称
                    stock_name = stock_names.get(ticker, ticker)
                    
                    # 生成PDF报告
                    output_pdf_file = os.path.join(GlobalConfig.full_report_dir, f'{ticker}_daily_chip_signal_analysis.pdf')
                    
                    # 生成筹码信号分析图表
                    report_df, recent_signal_df = visualize_chip_signals(
                        data=data,
                        pdf_path=output_pdf_file,
                        ticker=ticker,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n{current_time} 股票 {ticker} 的筹码信号分析完成。")
                    logger.info(f"股票 {ticker} 的筹码信号分析完成")

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"{current_time} ✅ 全部筹码信号技术分析报告完成！")
            logger.info("全部筹码信号技术分析报告完成")

        except Exception as e:
            error_msg = f"导出过程失败: {str(e)}"
            print(f"❌ 错误: {error_msg}")
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            traceback.print_exc()

    except Exception as e:
        error_msg = f"发生未知错误: {type(e).__name__}: {e}"
        print(error_msg)
        if logger:
            logger.error(error_msg)
            logger.error(traceback.format_exc())
        traceback.print_exc()

        if 'get_ipython' not in globals():
            sys.exit(1)
        else:
            print("在Jupyter环境中运行，程序继续但可能无法正常工作")

if __name__ == "__main__":
    main()