#!/usr/bin/env python
# coding: utf-8

"""
Step 6: Analyze chip distribution.
Source code:Daily_TA3C_Chip_Distribution_Analysis.py
Input data:     hk_daily_kline_analysis
Output data:    daily_chip_distribution_analysis.pdf
Function：
读取交易数据及技术分析指标数据（从SQLiteDB读取），进行筹码分布分析。
      1. 短期趋势分析，EMA5/20/50, 20日筹码分布图及 VA 70% 上沿及下沿价格。
      2. 中期趋势分析，EMA20/50/100, 60日筹码分布图及 VA 70% 上沿及下沿价格。
      3. 长期趋势分析，EMA20/50/200, 250日筹码分布图及 VA 70% 上沿及下沿价格。
      4. 显示技术信号条件（底部/顶部信号等）
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.pylab import date2num
from matplotlib.gridspec import GridSpec
from scipy.signal import find_peaks
from matplotlib.patches import Rectangle
import matplotlib.dates as mdates
import os
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib as mpl
import traceback
import warnings
import sys
import io
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import logging
from logging.handlers import RotatingFileHandler

import warnings
warnings.filterwarnings("ignore", message="Failed to find font weight bold")

# 解决中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
mpl.rcParams['font.size'] = 12

# === 添加UTL路径到系统路径 ===
script_dir = Path(__file__).resolve().parent
core_dir = script_dir.parent
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

from utl.stock_analysis_utl import get_project_root
core_dir_from_utils = get_project_root()
project_dir = core_dir_from_utils.parent

if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

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
    print(f"   详细错误: {e}")
    print("=" * 60)
    sys.exit(1)

# === 强制UTF-8编码输出 ===
if 'get_ipython' not in globals():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
else:
    import ipykernel
    if ipykernel:
        sys.stdout.encoding = 'utf-8'
        sys.stderr.encoding = 'utf-8'

setup_windows_encoding()

# ============================================================================
# 日志配置
# ============================================================================
def setup_logger(log_dir):
    """配置日志记录器 - 每次启动时覆盖原有日志文件"""
    # 确保log_dir是Path对象
    if isinstance(log_dir, str):
        log_dir = Path(log_dir)
    
    log_file = log_dir / 'Daily_TA3C_Chip_Distribution_Analysis.log'
    
    # 创建日志目录
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建logger
    logger = logging.getLogger('ChipDistributionAnalysis')
    logger.setLevel(logging.INFO)
    
    # 避免重复添加handler
    if logger.handlers:
        # 清除所有现有的handlers
        logger.handlers.clear()
    
    # 文件处理器 - 使用FileHandler并设置mode='w'实现覆盖
    file_handler = logging.FileHandler(
        str(log_file),  # 转换为字符串
        mode='w',      # 'w'模式表示写入（覆盖），'a'模式表示追加
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 设置格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
    
def load_daily_kline_analysis_from_db(ticker, db_path):
    """
    从SQLite数据库读取单个股票的技术分析数据
    
    参数:
        ticker: 股票代码
        db_path: 数据库路径
    
    返回:
        DataFrame: 包含技术分析指标的数据
    """
    try:
        # 确保db_path是Path对象
        if isinstance(db_path, str):
            db_path = Path(db_path)
        
        conn = sqlite3.connect(str(db_path))
        
        # 查询语句 - 所有列名改为小写
        query = """
        SELECT 
            stock_code,
            stock_name,
            date,
            open,
            high,
            low,
            close,
            volume,
            amount,
            amplitude,
            change_percent,
            change_amount,
            turnover_rate,
            previous_close,
            avg_price,
            close_chgpct,
            avg_volume_5d,
            volume_ratio5,
            avg_volume_20d,
            volume_ratio20,
            ema5,
            ema10,
            ema20,
            ema50,
            ema100,
            ema200,
            vol_ema5,
            vol_ema10,
            vol_ema20,
            price_amp_chip_max_20_70,
            price_amp_chip_min_20_70,
            price_amp_chip_max_60_70,
            price_amp_chip_min_60_70,
            price_amp_chip_max_250_70,
            price_amp_chip_min_250_70,
            -- 技术信号列（布尔类型）
            ema_golden_cross,
            ema_death_cross,
            golden_triangle,
            death_triangle,
            macd_golden_cross,
            macd_death_cross,
            bottom_signal_cond,
            top_signal_cond,
            bottom_entry_signal_cond,
            top_exit_signal_cond,
            continuation_signal_cond,
            decline_continuation_cond,
            accumulation_cond,
            distribution_cond,
            multi_timeframe_chip_confirm_bottom_cond,
            multi_timeframe_chip_confirm_top_cond
        FROM hk_daily_kline_analysis
        WHERE stock_code = ?
        ORDER BY date ASC
        """
        
        df = pd.read_sql_query(query, conn, params=(ticker,))
        conn.close()
        
        if df.empty:
            logger.warning(f"股票 {ticker} 在数据库中无数据")
            return None
        
        # 转换日期格式 - 直接使用date列，不重命名
        df['date'] = pd.to_datetime(df['date'])
        
        # 确保数值列为float类型 - 列名改为小写
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount',
                          'amplitude', 'change_percent', 'change_amount', 'turnover_rate',
                          'previous_close', 'avg_price', 'close_chgpct',
                          'avg_volume_5d', 'volume_ratio5', 'avg_volume_20d', 'volume_ratio20',
                          'ema5', 'ema10', 'ema20', 'ema50', 'ema100', 'ema200',
                          'vol_ema5', 'vol_ema10', 'vol_ema20',
                          'price_amp_chip_max_20_70', 'price_amp_chip_min_20_70',
                          'price_amp_chip_max_60_70', 'price_amp_chip_min_60_70',
                          'price_amp_chip_max_250_70', 'price_amp_chip_min_250_70']
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 确保布尔类型列转换为布尔类型 - 列名改为小写
        boolean_columns = [
            'ema_golden_cross', 'ema_death_cross', 'golden_triangle', 'death_triangle',
            'macd_golden_cross', 'macd_death_cross',
            'bottom_signal_cond', 'top_signal_cond',
            'bottom_entry_signal_cond', 'top_exit_signal_cond',
            'continuation_signal_cond', 'decline_continuation_cond',
            'accumulation_cond', 'distribution_cond',
            'multi_timeframe_chip_confirm_bottom_cond', 'multi_timeframe_chip_confirm_top_cond'
        ]
        
        for col in boolean_columns:
            if col in df.columns:
                # 转换为布尔类型，处理可能的整数/浮点数
                df[col] = df[col].astype(bool, errors='ignore')
        
        logger.info(f"成功从数据库加载股票 {ticker} 的数据，共 {len(df)} 条记录")
        return df
        
    except sqlite3.Error as e:
        logger.error(f"数据库错误: {e}")
        return None
    except Exception as e:
        logger.error(f"加载数据失败: {e}")
        return None

def add_signal_annotations(ax, df, latest_date):
    """
    在图表上添加信号条件标注（移除emoji字符以避免字体警告）
    
    参数:
        ax: matplotlib axes对象
        df: 包含信号列的DataFrame
        latest_date: 最新日期
    """
    if df is None or df.empty:
        return
    
    # 获取最新日期的信号数据
    latest_data = df[df.index == latest_date]
    if latest_data.empty:
        return
    
    # 信号名称映射（中文显示）- 列名改为小写
    signal_map = {
        'ema_golden_cross': 'EMA金叉',
        'ema_death_cross': 'EMA死叉',
        'golden_triangle': '黄金三角',
        'death_triangle': '死亡三角',
        'macd_golden_cross': 'MACD金叉',
        'macd_death_cross': 'MACD死叉',
        'bottom_signal_cond': '底部信号',
        'top_signal_cond': '顶部信号',
        'bottom_entry_signal_cond': '底部入场',
        'top_exit_signal_cond': '顶部出场',
        'continuation_signal_cond': '趋势延续',
        'decline_continuation_cond': '下跌延续',
        'accumulation_cond': '吸筹信号',
        'distribution_cond': '派发信号',
        'multi_timeframe_chip_confirm_bottom_cond': '多周期底部确认',
        'multi_timeframe_chip_confirm_top_cond': '多周期顶部确认'
    }
    
    # 收集所有为True的信号
    active_signals = []
    for col, display_name in signal_map.items():
        if col in latest_data.columns:
            signal_value = latest_data[col].iloc[0]
            if signal_value:  # 布尔值为True
                active_signals.append(display_name)
    
    if active_signals:
        # 构建信号文本 - 移除emoji字符
        signal_text = "当前信号: " + " | ".join(active_signals)
        
        # 获取当前坐标轴范围
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        
        # 在图表左上角添加信号标注
        ax.text(x_min + (x_max - x_min) * 0.02, 
                y_max - (y_max - y_min) * 0.05,
                signal_text,
                transform=ax.transData,
                fontsize=11,
                bbox=dict(boxstyle='round,pad=0.5', 
                         facecolor='yellow', 
                         alpha=0.8,
                         edgecolor='black'),
                verticalalignment='top',
                zorder=10)
        
        # 添加信号统计信息（最近30天的信号发生次数）
        try:
            # 计算最近30天的信号统计
            recent_days = 30
            if len(df) >= recent_days:
                recent_df = df.iloc[-recent_days:]
                signal_counts = {}
                for col, display_name in signal_map.items():
                    if col in recent_df.columns:
                        count = recent_df[col].sum()
                        if count > 0:
                            signal_counts[display_name] = count
                
                if signal_counts:
                    # 构建统计文本 - 移除emoji字符
                    stats_text = "近30天信号统计:\n" + "\n".join([f"  {k}: {v}次" for k, v in signal_counts.items()])
                    
                    # 在图表右上角添加统计信息
                    ax.text(x_max - (x_max - x_min) * 0.02,
                            y_max - (y_max - y_min) * 0.05,
                            stats_text,
                            transform=ax.transData,
                            fontsize=9,
                            bbox=dict(boxstyle='round,pad=0.5',
                                     facecolor='lightblue',
                                     alpha=0.8,
                                     edgecolor='black'),
                            verticalalignment='top',
                            horizontalalignment='right',
                            zorder=10)
        except Exception as e:
            logger.debug(f"添加信号统计失败: {e}")

def plot_daily_chart_with_chip_distribution_by_window(df, ticker, chip_window, start_date, end_date=None):
    """
    使用从数据库加载的数据绘制筹码分布图表
    
    参数:
        df: 包含技术分析指标的DataFrame
        ticker: 股票代码
        chip_window: 筹码窗口大小 (20, 60, 250)
        start_date: 开始日期
        end_date: 结束日期（可选）
    """
    if df is None or df.empty:
        logger.error(f"股票 {ticker} 数据为空，无法生成图表")
        return None
    
    # 复制DataFrame避免修改原始数据
    df = df.copy()
    
    # 检查是否存在'date'列（从数据库查询的列名）
    if 'date' in df.columns:
        # 如果列名是'date'，转换为datetime并设置为索引
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
    elif 'Date' in df.columns:
        # 如果列名是'Date'（兼容旧数据），转换为datetime并设置为索引
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
    else:
        logger.error("数据中找不到日期列")
        return None
    
    # 过滤日期范围
    start_date = pd.to_datetime(start_date)
    if end_date:
        end_date = pd.to_datetime(end_date)
    else:
        end_date = df.index[-1]
    
    # 检查数据范围
    first_day = df.index.min()
    last_day = df.index.max()
    
    if start_date < first_day:
        logger.warning(f"开始日期 {start_date.strftime('%Y-%m-%d')} 早于数据第一天 {first_day.strftime('%Y-%m-%d')}，已自动修正")
        start_date = first_day
    
    if end_date > last_day:
        logger.warning(f"结束日期 {end_date.strftime('%Y-%m-%d')} 超过数据最后日期 {last_day.strftime('%Y-%m-%d')}，已自动修正")
        end_date = last_day
    
    mask = (df.index >= start_date) & (df.index <= end_date)
    df_filtered = df.loc[mask].copy()
    
    if df_filtered.empty:
        logger.error(f"在指定日期范围内没有数据")
        return None
    
    # 获取股票名称
    stock_name = df_filtered['stock_name'].iloc[0] if 'stock_name' in df_filtered.columns else ticker
    
    # 设置图表整体大小
    fig = plt.figure(figsize=(16, 14))
    
    # 创建GridSpec布局
    gs = GridSpec(3, 1, figure=fig, height_ratios=[0.2, 3.0, 0.8])
    
    # 标题区域
    ax_title = fig.add_subplot(gs[0])
    ax_title.set_title(f"{ticker} - {stock_name} # {chip_window}日筹码分布分析", fontsize=20, pad=15)
    ax_title.axis('off')
    
    # 主K线图区域
    ax1 = fig.add_subplot(gs[1])
    ax2 = fig.add_subplot(gs[2])
    
    # --- 绘制K线图 ---
    dates = date2num(df_filtered.index.to_pydatetime())
    
    UP_COLOR = '#006400'
    DOWN_COLOR = '#FF0000'
    
    for i in range(len(df_filtered)):
        curr_date = dates[i]
        open_val = df_filtered.iloc[i]['open']
        close_val = df_filtered.iloc[i]['close']
        high_val = df_filtered.iloc[i]['high']
        low_val = df_filtered.iloc[i]['low']
        
        color = UP_COLOR if close_val >= open_val else DOWN_COLOR
        
        # 绘制影线
        ax1.plot([curr_date, curr_date], [low_val, high_val], color=color, linewidth=0.8, zorder=1)
        
        # 绘制实体
        body_width = 0.5
        rect_x = curr_date - body_width/2
        rect_height = abs(close_val - open_val)
        if rect_height > 0:
            rect_y = min(open_val, close_val)
            rect = Rectangle(
                (rect_x, rect_y),
                width=body_width,
                height=rect_height,
                facecolor=color,
                edgecolor=color,
                zorder=2
            )
            ax1.add_patch(rect)
        else:
            ax1.plot(
                [curr_date - body_width/2, curr_date + body_width/2],
                [open_val, open_val],
                color=color,
                linewidth=1.5,
                zorder=2
            )
    
    # 根据chip_window选择不同的均线组合 - 列名改为小写
    if chip_window == 20:
        if 'ema5' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema5'], label='EMA5', linewidth=1.5, color='royalblue', zorder=3)
        if 'ema20' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema20'], label='EMA20', linewidth=1.5, color='darkorange', zorder=3)
        if 'ema50' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema50'], label='EMA50', linewidth=2.0, color='firebrick', zorder=3)
        ema_title = "EMA5/20/50"
    elif chip_window == 60:
        if 'ema20' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema20'], label='EMA20', linewidth=1.5, color='royalblue', zorder=3)
        if 'ema50' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema50'], label='EMA50', linewidth=1.5, color='darkorange', zorder=3)
        if 'ema100' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema100'], label='EMA100', linewidth=2.0, color='firebrick', zorder=3)
        ema_title = "EMA20/50/100"
    elif chip_window == 250:
        if 'ema20' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema20'], label='EMA20', linewidth=1.5, color='royalblue', zorder=3)
        if 'ema50' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema50'], label='EMA50', linewidth=1.5, color='darkorange', zorder=3)
        if 'ema200' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema200'], label='EMA200', linewidth=2.0, color='firebrick', zorder=3)
        ema_title = "EMA20/50/200"
    else:
        if 'ema5' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema5'], label='EMA5', linewidth=1.5, color='royalblue', zorder=3)
        if 'ema20' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema20'], label='EMA20', linewidth=1.5, color='darkorange', zorder=3)
        if 'ema50' in df_filtered.columns:
            ax1.plot(df_filtered.index, df_filtered['ema50'], label='EMA50', linewidth=2.0, color='firebrick', zorder=3)
        ema_title = "EMA5/20/50"
    
    # 根据chip_window选择对应的70%分位值列 - 列名改为小写
    if chip_window == 20:
        max_col = 'price_amp_chip_max_20_70'
        min_col = 'price_amp_chip_min_20_70'
    elif chip_window == 60:
        max_col = 'price_amp_chip_max_60_70'
        min_col = 'price_amp_chip_min_60_70'
    elif chip_window == 250:
        max_col = 'price_amp_chip_max_250_70'
        min_col = 'price_amp_chip_min_250_70'
    else:
        max_col = 'price_amp_chip_max_20_70'
        min_col = 'price_amp_chip_min_20_70'
    
    # 绘制70%分位值
    if max_col in df_filtered.columns and min_col in df_filtered.columns:
        last_max = df_filtered[max_col].iloc[-1]
        last_min = df_filtered[min_col].iloc[-1]
        
        if not pd.isna(last_max) and not pd.isna(last_min):
            ax1.axhline(y=last_max, color='green', linestyle='--', alpha=0.7, label='70%分位上沿')
            ax1.axhline(y=last_min, color='red', linestyle='--', alpha=0.7, label='70%分位下沿')
            
            first_date = df_filtered.index[0]
            ax1.text(first_date, last_max, f' {last_max:.2f}',
                    color='green', ha='left', va='bottom', fontsize=10)
            ax1.text(first_date, last_min, f' {last_min:.2f}',
                    color='red', ha='left', va='top', fontsize=10)
    
    # 右侧Y轴
    ax1_right = ax1.twinx()
    ax1_right.set_ylim(ax1.get_ylim())
    ax1_right.set_ylabel('价格', rotation=270, labelpad=15)
    
    date_range_str = f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"
    ax1.set_title(f'价格与{ema_title} ({date_range_str})', pad=15)
    ax1.set_ylabel('价格')
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.legend(loc='best')
    
    date_fmt = mdates.DateFormatter('%Y-%m-%d')
    ax1.xaxis.set_major_formatter(date_fmt)
    plt.setp(ax1.get_xticklabels(), rotation=30, ha='right')
    
    # --- 右侧筹码分布图 ---
    bin_count = 50
    last_n_days = df_filtered.iloc[-chip_window:] if len(df_filtered) >= chip_window else df_filtered
    
    if 'avg_price' in last_n_days.columns:
        min_price = last_n_days['avg_price'].min()
        max_price = last_n_days['avg_price'].max()
        price_range = max_price - min_price
        
        if price_range > 0:
            bins = np.linspace(min_price, max_price, bin_count + 1)
            bin_centers = (bins[:-1] + bins[1:]) / 2
            volume_per_bin = np.zeros(bin_count)
            
            for _, row in last_n_days.iterrows():
                if row['high'] > row['low']:
                    price_distribution = (bins - row['low']) / (row['high'] - row['low'])
                    price_distribution = np.clip(price_distribution, 0, 1)
                    
                    bin_proportion = price_distribution[1:] - price_distribution[:-1]
                    bin_proportion = np.clip(bin_proportion, 0, 1)
                    
                    if bin_proportion.sum() > 0:
                        bin_volume = row['volume'] * bin_proportion / bin_proportion.sum()
                        volume_per_bin += bin_volume
            
            total_volume = volume_per_bin.sum()
            
            if total_volume > 0:
                volume_percentage = volume_per_bin / total_volume
                
                # 计算POC
                poc_idx = np.argmax(volume_per_bin)
                poc_price = bin_centers[poc_idx]
                
                # 计算VA(70%)
                sorted_volumes = np.sort(volume_per_bin)[::-1]
                cumulative_volume = np.cumsum(sorted_volumes)
                idx_70 = np.searchsorted(cumulative_volume, total_volume * 0.7)
                threshold_volume = sorted_volumes[idx_70] if idx_70 < len(sorted_volumes) else 0
                
                valid_bins = bin_centers[volume_per_bin >= threshold_volume]
                va_low = np.min(valid_bins) if len(valid_bins) > 0 else bin_centers[0]
                va_high = np.max(valid_bins) if len(valid_bins) > 0 else bin_centers[-1]
                
                # 绘制筹码峰
                y_min, y_max_ax = ax1.get_ylim()
                x_min, x_max_ax = ax1.get_xlim()
                
                chip_width = (x_max_ax - x_min) * 0.2
                chip_x_start = x_max_ax - chip_width
                
                max_vol = np.max(volume_per_bin)
                if max_vol > 0:
                    bar_widths = volume_per_bin / max_vol
                    
                    for i in range(bin_count):
                        bin_price = bin_centers[i]
                        bar_width = bar_widths[i] * chip_width * 0.8
                        bar_x = chip_x_start + chip_width - bar_width
                        bar_height = bins[i+1] - bins[i]
                        
                        rect = Rectangle(
                            (bar_x, bin_price - bar_height/2),
                            width=bar_width,
                            height=bar_height,
                            facecolor='royalblue',
                            alpha=0.7,
                            zorder=4
                        )
                        ax1.add_patch(rect)
                    
                    # 标记POC
                    ax1.axhline(y=poc_price, color='red', linestyle='-', linewidth=2, zorder=5)
                    ax1.text(chip_x_start + chip_width/2, poc_price, f'POC: {poc_price:.2f}',
                            color='red', ha='center', va='center', fontsize=12,
                            bbox=dict(facecolor='white', alpha=0.7), zorder=6)
                    
                    # 标记VA区间
                    ax1.axhspan(va_low, va_high, xmin=(chip_x_start - x_min)/(x_max_ax - x_min),
                               xmax=1.0, color='green', alpha=0.3, zorder=4)
                    
                    # 标记当前价格
                    current_price = df_filtered['close'].iloc[-1]
                    ax1.axhline(y=current_price, color='purple', linestyle='-', alpha=0.7, zorder=5)
                    ax1.text(chip_x_start, current_price, f'当前价: {current_price:.2f}',
                            color='purple', ha='left', va='center', fontsize=10, zorder=6)
                    
                    # 筹码分布标题
                    ax1.text(chip_x_start + chip_width/2, y_max_ax, f'{chip_window}日筹码分布',
                            ha='center', va='bottom', fontsize=12, zorder=6)
    
    # --- 添加技术信号标注 ---
    # 在K线图区域添加信号标注
    add_signal_annotations(ax1, df_filtered, df_filtered.index[-1])
    
    # --- 成交量图 ---
    if 'volume' in df_filtered.columns:
        colors = [UP_COLOR if close >= open_ else DOWN_COLOR
                 for close, open_ in zip(df_filtered['close'], df_filtered['open'])]
        
        max_volume = df_filtered['volume'].max()
        if max_volume >= 1e9:
            volume_factor = 1e9
            volume_unit = 'Bil'
        elif max_volume >= 1e6:
            volume_factor = 1e6
            volume_unit = 'Mil'
        else:
            volume_factor = 1
            volume_unit = ''
        
        volume_data = df_filtered['volume'] / volume_factor
        ax2.bar(df_filtered.index, volume_data, color=colors, width=1.0)
        
        if 'vol_ema5' in df_filtered.columns and 'vol_ema20' in df_filtered.columns:
            ax2.plot(df_filtered.index, df_filtered['vol_ema5'] / volume_factor, label='VOL_EMA5', color='royalblue', linewidth=1.5)
            ax2.plot(df_filtered.index, df_filtered['vol_ema20'] / volume_factor, label='VOL_EMA20', color='firebrick', linewidth=1.5)
        
        ax2.set_title(f'成交量与成交量均线 ({date_range_str})', pad=15)
        ax2.set_ylabel(f'成交量({volume_unit})')
        ax2.grid(True, linestyle='--', alpha=0.7)
        ax2.legend(loc='best')
        
        ax2.xaxis.set_major_formatter(date_fmt)
        plt.setp(ax2.get_xticklabels(), rotation=30, ha='right')
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.93, hspace=0.25)
    
    return fig

def plot_daily_chart_with_chip_distribution(df, ticker, pdf_output, chip_windows, start_date, end_date=None):
    """
    主函数：为不同的筹码窗口生成图表并保存到PDF
    
    参数:
        df: 从数据库加载的DataFrame
        ticker: 股票代码
        pdf_output: 输出PDF文件路径
        chip_windows: 筹码窗口列表，如[20, 60, 250]
        start_date: 开始日期
        end_date: 结束日期（可选）
    """
    if df is None or df.empty:
        logger.error(f"股票 {ticker} 数据为空，无法生成图表")
        return
    
    # 确保pdf_output是Path对象
    if isinstance(pdf_output, str):
        pdf_output = Path(pdf_output)
    
    # 创建输出目录
    pdf_output.parent.mkdir(parents=True, exist_ok=True)
    
    with PdfPages(str(pdf_output)) as pdf:
        for chip_window in chip_windows:
            fig = plot_daily_chart_with_chip_distribution_by_window(
                df, ticker, chip_window, start_date, end_date
            )
            if fig:
                pdf.savefig(fig)
                plt.close(fig)
    
    logger.info(f"图表已成功保存至: {pdf_output}")

def main():
    """主函数，程序的入口点"""
    global logger
    
    try:
        # ========== 主程序路径配置 ==========
        config_path = os.path.join(project_dir, 'config', 'stock_data_analysis.par')
        
        # ========== 加载配置 ==========
        CONFIG = load_config(config_path, project_dir)
        
        # 更新全局路径配置
        GlobalConfig.update_paths(CONFIG, project_dir)
        
        # ========== 设置日志 ==========
        log_dir = GlobalConfig.full_log_dir
        logger = setup_logger(log_dir)
        
        logger.info("=" * 50)
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件位置: {config_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"报告目录: {GlobalConfig.full_report_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        
        # 数据库路径
        db_path = project_dir / 'SQLiteDB' / 'HK_Stock.db'
        if not db_path.exists():
            logger.error(f"数据库文件不存在: {db_path}")
            return
        
        logger.info(f"数据库路径: {db_path}")
        
        if CONFIG.get('tickers'):
            tickers = CONFIG['tickers']
            logger.info(f"股票代码数量: {len(tickers)}")
            if len(tickers) > 5:
                logger.info(f"前5个股票代码: {tickers[:5]}... 等")
            else:
                logger.info(f"股票代码: {tickers}")
        else:
            logger.warning("配置文件中未找到tickers设置")
            return
        
        # ========== 生成技术分析指标报告 ==========
        try:
            # 获取并验证日期范围
            start_date, end_date = get_validated_dates(CONFIG, project_dir)
            logger.info(f"📅 验证通过的日期范围:")
            logger.info(f"开始日期: {start_date.strftime('%Y-%m-%d')}")
            logger.info(f"结束日期: {end_date.strftime('%Y-%m-%d')}")
            
            chip_windows_list = [20, 60, 250]
            
            if not tickers:
                logger.error("无法进行筹码分布技术分析 - 没有配置股票代码")
                return
            
            logger.info("开始进行筹码信号技术分析...")
            
            for ticker in tickers:
                logger.info(f"\n处理股票 {ticker} 的筹码分布分析...")
                
                # 从数据库加载数据
                df = load_daily_kline_analysis_from_db(ticker, db_path)
                
                if df is None or df.empty:
                    logger.warning(f"股票 {ticker} 无数据，跳过")
                    continue
                
                # 生成PDF报告
                output_pdf_file = Path(GlobalConfig.full_report_dir) / f'{ticker}_daily_chip_distribution_analysis.pdf'
                
                plot_daily_chart_with_chip_distribution(
                    df=df,
                    ticker=ticker,
                    pdf_output=output_pdf_file,
                    chip_windows=chip_windows_list,
                    start_date=start_date,
                    end_date=end_date
                )
                
                logger.info(f"股票 {ticker} 的筹码分布分析完成")
            
            logger.info("✅ 全部筹码分布技术分析报告完成！")
            
        except Exception as e:
            logger.error(f"❌ 错误: {str(e)}")
            logger.error(traceback.format_exc())
            
    except Exception as e:
        error_msg = f"发生未知错误: {type(e).__name__}: {e}"
        if 'logger' in globals():
            logger.error(error_msg)
            logger.error(traceback.format_exc())
        else:
            print(error_msg)
            traceback.print_exc()
        
        if 'get_ipython' not in globals():
            sys.exit(1)

if __name__ == "__main__":
    # 初始化logger（在main中会重新配置）
    logger = logging.getLogger('ChipDistributionAnalysis')
    main()