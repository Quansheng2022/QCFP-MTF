#!/usr/bin/env python
# coding: utf-8

"""
Name: Weekly_TA2B_Calculate_indicators.py
Function: 
计算周线数据技术分析指标。
输入数据表：hk_hist_weekly_kline
输出数据表：hk_weekly_kline_analysis
"""

# ==================== 标准库导入 ====================
import io
import os
import sys
import time
import traceback
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

# ==================== 第三方库导入 ====================
import numpy as np
import pandas as pd

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch
from mplfinance.original_flavor import candlestick_ohlc

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows


# ==================== 配置类 ====================
class GlobalConfig:
    full_data_dir = None
    full_report_dir = None
    full_log_dir = None
    full_temp_dir = None
    full_sqlite_dir = None
    db_name = None
    full_db_path = None

    @classmethod
    def update_paths(cls, config, project_dir):
        """更新全局路径配置"""
        cls.full_data_dir = Path(project_dir) / config.get('data_dir', 'Data')
        cls.full_report_dir = Path(project_dir) / config.get('report_dir', 'Report')
        cls.full_log_dir = Path(project_dir) / config.get('log_dir', 'Log')
        cls.full_temp_dir = Path(project_dir) / config.get('temp_dir', 'Temp')
        cls.full_sqlite_dir = Path(project_dir) / config.get('sqlite_dir', 'SQLiteDB')
        cls.db_name = config.get('db_name', 'HK_Stock.db')
        cls.full_db_path = cls.full_sqlite_dir / cls.db_name


def setup_logging(log_dir):
    """设置日志配置 - 每次运行覆盖旧日志文件"""
    log_file = Path(log_dir) / 'Weekly_TA2B_Calculate_indicators.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 移除可能存在的旧处理器，避免重复
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # 自定义日期格式，去掉毫秒
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',  # 添加这一行，只显示到秒
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def get_db_connection(db_path):
    """获取数据库连接"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def load_stock_names_from_db(conn):
    """
    从 hk_stock_info 表加载股票名称映射
    
    Args:
        conn: 数据库连接
        
    Returns:
        dict: {stock_code: stock_name} 的映射字典
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT stock_code, stock_name 
            FROM hk_stock_info 
            WHERE is_active = 1
        """)
        results = cursor.fetchall()
        
        stock_names = {}
        for row in results:
            code = row['stock_code'].strip() if row['stock_code'] else ''
            name = row['stock_name'].strip() if row['stock_name'] else ''
            if code and name:
                stock_names[code] = name
        
        logging.info(f"从 hk_stock_info 表加载了 {len(stock_names)} 个股票名称")
        return stock_names
    except Exception as e:
        logging.error(f"从 hk_stock_info 表加载股票名称失败: {e}")
        return {}


def check_analysis_status(conn, stock_code):
    """
    检查分析数据状态
    返回: (status, latest_analysis_date, latest_kline_date)
    status: 'need_update', 'up_to_date', 'data_error'
    """
    cursor = conn.cursor()
    
    # 获取原始K线最新日期
    cursor.execute("""
        SELECT MAX(date) as latest_date 
        FROM hk_hist_weekly_kline 
        WHERE stock_code = ?
    """, (stock_code,))
    kline_result = cursor.fetchone()
    latest_kline_date = kline_result['latest_date'] if kline_result else None
    
    # 获取分析数据最新日期
    cursor.execute("""
        SELECT MAX(date) as latest_date 
        FROM hk_weekly_kline_analysis 
        WHERE stock_code = ?
    """, (stock_code,))
    analysis_result = cursor.fetchone()
    latest_analysis_date = analysis_result['latest_date'] if analysis_result else None
    
    # 判断状态
    if latest_kline_date is None:
        return 'data_error', latest_analysis_date, latest_kline_date
    
    if latest_analysis_date is None:
        return 'need_update', latest_analysis_date, latest_kline_date
    
    if latest_analysis_date < latest_kline_date:
        return 'need_update', latest_analysis_date, latest_kline_date
    elif latest_analysis_date == latest_kline_date:
        return 'up_to_date', latest_analysis_date, latest_kline_date
    else:
        return 'data_error', latest_analysis_date, latest_kline_date


def load_weekly_data_from_db(conn, stock_code):
    """从数据库加载周线数据"""
    query = """
        SELECT 
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
            ema5,
            ema10,
            ema20,
            ema50,
            ema100,
            ema200,
            macd_dif as dif,
            macd_signal as dea,
            macd_histogram as macd
        FROM hk_hist_weekly_kline
        WHERE stock_code = ?
        ORDER BY date ASC
    """
    df = pd.read_sql_query(query, conn, params=(stock_code,))
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df


def save_analysis_to_db(conn, df, stock_code, stock_name):
    """
    保存分析结果到数据库
    
    Args:
        conn: 数据库连接
        df: 分析后的DataFrame
        stock_code: 股票代码
        stock_name: 股票名称
    """
    cursor = conn.cursor()
    
    # 先删除该股票已有的分析数据
    cursor.execute("DELETE FROM hk_weekly_kline_analysis WHERE stock_code = ?", (stock_code,))
    
    # 准备插入数据 - 字段名与数据库表结构匹配
    columns = [
        'stock_code', 'stock_name', 'date', 'open', 'high', 'low', 'close', 
        'volume', 'amount', 'amplitude', 'change_percent', 'change_amount', 
        'turnover_rate', 'ema5', 'ema10', 'ema20', 'ema50', 'ema100', 'ema200',
        'macd_dif', 'macd_signal', 'macd_histogram',
        'ema5_10_status', 'ema5_10_streak',
        'ema5_20_status', 'ema5_20_streak',
        'ema10_50_status', 'ema10_50_streak',
        'ema20_50_status', 'ema20_50_streak',
        'golden_triangle', 'death_triangle',
        'macd_cross', 'macd_status', 'macd_golden_streak', 'macd_death_streak',
        'kdj_k', 'kdj_d', 'kdj_j',
        'vol_ema5', 'volume_ratio',
        'gain', 'loss', 'avg_gain', 'avg_loss', 'rs', 'rsi14'
    ]
    
    # 准备数据
    records = []
    for _, row in df.iterrows():
        record = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'date': row['date'].strftime('%Y-%m-%d') if pd.notna(row['date']) else None,
            'open': row.get('open'),
            'high': row.get('high'),
            'low': row.get('low'),
            'close': row.get('close'),
            'volume': row.get('volume'),
            'amount': row.get('amount'),
            'amplitude': row.get('amplitude'),
            'change_percent': row.get('change_percent'),
            'change_amount': row.get('change_amount'),
            'turnover_rate': row.get('turnover_rate'),
            'ema5': row.get('ema5'),
            'ema10': row.get('ema10'),
            'ema20': row.get('ema20'),
            'ema50': row.get('ema50'),
            'ema100': row.get('ema100'),
            'ema200': row.get('ema200'),
            'macd_dif': row.get('dif'),
            'macd_signal': row.get('dea'),
            'macd_histogram': row.get('macd'),
            'ema5_10_status': row.get('ema5_10_status'),
            'ema5_10_streak': row.get('ema5_10_streak'),
            'ema5_20_status': row.get('ema5_20_status'),
            'ema5_20_streak': row.get('ema5_20_streak'),
            'ema10_50_status': row.get('ema10_50_status'),
            'ema10_50_streak': row.get('ema10_50_streak'),
            'ema20_50_status': row.get('ema20_50_status'),
            'ema20_50_streak': row.get('ema20_50_streak'),
            'golden_triangle': row.get('golden_triangle'),
            'death_triangle': row.get('death_triangle'),
            'macd_cross': row.get('macd_cross'),
            'macd_status': row.get('macd_status'),
            'macd_golden_streak': row.get('macd_golden_streak'),
            'macd_death_streak': row.get('macd_death_streak'),
            'kdj_k': row.get('kdj_k'),
            'kdj_d': row.get('kdj_d'),
            'kdj_j': row.get('kdj_j'),
            'vol_ema5': row.get('vol_ema5'),
            'volume_ratio': row.get('volume_ratio'),
            'gain': row.get('gain'),
            'loss': row.get('loss'),
            'avg_gain': row.get('avg_gain'),
            'avg_loss': row.get('avg_loss'),
            'rs': row.get('rs'),
            'rsi14': row.get('rsi14')
        }
        records.append(record)
    
    # 批量插入
    if records:
        placeholders = ', '.join(['?' for _ in columns])
        columns_str = ', '.join(columns)
        insert_sql = f"INSERT INTO hk_weekly_kline_analysis ({columns_str}) VALUES ({placeholders})"
        
        # 准备数据元组列表
        data_tuples = []
        for record in records:
            data_tuple = tuple(record.get(col) for col in columns)
            data_tuples.append(data_tuple)
        
        cursor.executemany(insert_sql, data_tuples)
        conn.commit()


def analyze_weekly_data(df):
    """
    分析周线数据，计算技术指标
    """
    # 1. 确保数据按日期排序
    df = df.sort_values('date').reset_index(drop=True)
    
    # 2. 计算EMA交叉状态
    def add_ema_status(df, short_col, long_col, status_col, streak_col):
        short = df[short_col]
        long_ = df[long_col]
        golden = short > long_
        death = short < long_
        golden_cross = golden & (short.shift(1) <= long_.shift(1))
        death_cross = death & (short.shift(1) >= long_.shift(1))

        status = pd.Series('', index=df.index)
        status[golden_cross] = '金叉'
        status[death_cross] = '死叉'

        # 延续状态：只有从实际金叉/死叉开启的趋势段才标记为“延续”
        golden_run_start = golden & ~golden.shift(1, fill_value=False)
        death_run_start = death & ~death.shift(1, fill_value=False)
        golden_run_id = golden_run_start.cumsum()
        death_run_id = death_run_start.cumsum()
        valid_golden_run = golden_run_id.isin(golden_run_id[golden_run_start & golden_cross])
        valid_death_run = death_run_id.isin(death_run_id[death_run_start & death_cross])
        status[golden & ~golden_cross & valid_golden_run] = '金叉延续'
        status[death & ~death_cross & valid_death_run] = '死叉延续'

        # 连续天数（状态变化时重新计数，与原循环逻辑一致）
        status_change = status != status.shift(1, fill_value='')
        df[streak_col] = status_change.cumsum().groupby(status_change.cumsum()).cumcount() + 1
        df[status_col] = status
    
    # 3. 确保EMA列存在
    required_ema = ['ema5', 'ema10', 'ema20', 'ema50', 'ema100', 'ema200']
    for col in required_ema:
        if col not in df.columns:
            try:
                period = int(col[3:])
                df[col] = df['close'].ewm(span=period, adjust=False).mean()
            except:
                pass
    
    # 4. 添加EMA状态
    ema_pairs = [
        ('ema5', 'ema10', 'ema5_10_status', 'ema5_10_streak'),
        ('ema5', 'ema20', 'ema5_20_status', 'ema5_20_streak'),
        ('ema10', 'ema50', 'ema10_50_status', 'ema10_50_streak'),
        ('ema20', 'ema50', 'ema20_50_status', 'ema20_50_streak')
    ]
    
    for short_col, long_col, status_col, streak_col in ema_pairs:
        if all(col in df.columns for col in [short_col, long_col]):
            add_ema_status(df, short_col, long_col, status_col, streak_col)
    
    # 5. 黄金三角形 / 死亡三角形
    df['golden_triangle'] = (df['ema5'] > df['ema10']) & (df['ema10'] > df['ema20'])
    df['death_triangle'] = (df['ema5'] < df['ema10']) & (df['ema10'] < df['ema20'])
    
    # 6. 处理MACD列 - 使用 dif, dea, macd (从数据库读取时已重命名)
    macd_columns = ['dif', 'dea']
    macd_missing = not all(col in df.columns for col in macd_columns)
    
    if not macd_missing:
        macd_bullish = df['dif'] > df['dea']
        macd_bearish = df['dif'] < df['dea']

        macd_golden = macd_bullish & (df['dif'].shift(1) <= df['dea'].shift(1))
        macd_death = macd_bearish & (df['dif'].shift(1) >= df['dea'].shift(1))

        status = pd.Series('', index=df.index)
        status[macd_golden] = '金叉'
        status[macd_death] = '死叉'

        bull_run_start = macd_bullish & ~macd_bullish.shift(1, fill_value=False)
        bear_run_start = macd_bearish & ~macd_bearish.shift(1, fill_value=False)
        bull_run_id = bull_run_start.cumsum()
        bear_run_id = bear_run_start.cumsum()
        valid_bull_run = bull_run_id.isin(bull_run_id[bull_run_start & macd_golden])
        valid_bear_run = bear_run_id.isin(bear_run_id[bear_run_start & macd_death])
        status[macd_bullish & ~macd_golden & valid_bull_run] = '金叉延续'
        status[macd_bearish & ~macd_death & valid_bear_run] = '死叉延续'

        cross_status = pd.Series('', index=df.index)
        cross_status[macd_golden] = '金叉'
        cross_status[macd_death] = '死叉'
        df['macd_cross'] = cross_status
        df['macd_status'] = status

        golden_mask = status.isin(['金叉', '金叉延续'])
        death_mask = status.isin(['死叉', '死叉延续'])
        df['macd_golden_streak'] = golden_mask.groupby((~golden_mask).cumsum()).cumsum()
        df['macd_death_streak'] = death_mask.groupby((~death_mask).cumsum()).cumsum()
    
    # 7. 计算周线 KDJ
    if all(col in df.columns for col in ['high', 'low', 'close']):
        def calculate_kdj(df, n=9, m1=3, m2=3):
            low_n = df['low'].rolling(window=n, min_periods=n).min()
            high_n = df['high'].rolling(window=n, min_periods=n).max()
            denom = (high_n - low_n).replace(0, np.nan)
            rsv = (df['close'] - low_n) / denom * 100
            # 高低相等时 rsv 为 inf，若直接进入递推会让 K/D 之后全部变成 inf，统一按 NaN 处理
            rsv = rsv.replace([np.inf, -np.inf], np.nan)
            # 与原始递推 K=(2/3)K_prev+(1/3)RSV、D=(2/3)D_prev+(1/3)K 完全等价
            k = rsv.ewm(alpha=1/3, adjust=False, ignore_na=True).mean()
            d = k.ewm(alpha=1/3, adjust=False, ignore_na=True).mean()
            j = 3 * k - 2 * d
            df['kdj_k'] = k
            df['kdj_d'] = d
            df['kdj_j'] = j
        
        calculate_kdj(df)
    
    # 8. 处理成交量
    if 'volume' in df.columns:
        df['vol_ema5'] = df['volume'].ewm(span=5, adjust=False).mean()
        df['volume_ratio'] = df['volume'] / df['vol_ema5']
    
    # 9. 计算RSI14
    if len(df) >= 14:
        df['gain'] = df['close'].diff().clip(lower=0)
        df['loss'] = -df['close'].diff().clip(upper=0)

        first_14_gains = df['gain'].iloc[:14].mean()
        first_14_losses = df['loss'].iloc[:14].mean()

        g = df['gain'].copy()
        l = df['loss'].copy()
        g.iloc[:13] = np.nan
        l.iloc[:13] = np.nan
        g.iloc[13] = first_14_gains
        l.iloc[13] = first_14_losses

        # Wilder平滑：avg = (prev*13 + cur)/14，等价于以首14日均值为种子、alpha=1/14 的 EMA
        df['avg_gain'] = g.ewm(alpha=1/14, adjust=False, ignore_na=True).mean()
        df['avg_loss'] = l.ewm(alpha=1/14, adjust=False, ignore_na=True).mean()

        rs = df['avg_gain'] / df['avg_loss'].replace(0, np.nan)
        df['rs'] = rs
        df['rsi14'] = (100 - (100 / (1 + rs))).fillna(100)
        # 前13行与原实现一致保持NaN（avg_gain/avg_loss 尚未定义）
        df.loc[df.index[:13], 'rsi14'] = np.nan
    else:
        df['rsi14'] = np.nan
    
    # 10. 高质量金叉计算
    if not macd_missing and 'volume' in df.columns and 'vol_ema5' in df.columns:
        df['zero_above_golden_count'] = 0
        df['high_quality_golden'] = ''
        
        golden_count = 0
        last_death_position = None
        
        for i in range(1, len(df)):
            # 检测MACD金叉（dif上穿dea）
            if df.loc[i, 'dif'] > df.loc[i, 'dea'] and df.loc[i-1, 'dif'] <= df.loc[i-1, 'dea']:
                # 零轴上方金叉
                if df.loc[i, 'dif'] > 0:
                    golden_count += 1
                    df.loc[i, 'zero_above_golden_count'] = golden_count
                    
                    # 高质量金叉判断
                    volume_condition = df.loc[i, 'volume'] > df.loc[i, 'vol_ema5']
                    
                    if golden_count == 1 and last_death_position is not None:
                        # 零轴下方首次金叉（超跌反弹）
                        if last_death_position < i:
                            df.loc[i, 'high_quality_golden'] = '是' if volume_condition else ''
                    elif golden_count >= 2:
                        # 零轴上方二次及以上金叉（主升浪延续）
                        df.loc[i, 'high_quality_golden'] = '是' if volume_condition else ''
                else:
                    # 零轴下方金叉，重置计数
                    golden_count = 0
                    df.loc[i, 'zero_above_golden_count'] = 0
            
            # 检测死叉
            if df.loc[i, 'dif'] < df.loc[i, 'dea'] and df.loc[i-1, 'dif'] >= df.loc[i-1, 'dea']:
                last_death_position = i
                if df.loc[i, 'dif'] > 0:
                    golden_count = 0
                    df.loc[i, 'zero_above_golden_count'] = 0
            
            # 更新计数延续
            if i > 0 and df.loc[i, 'dif'] > df.loc[i, 'dea']:
                df.loc[i, 'zero_above_golden_count'] = df.loc[i-1, 'zero_above_golden_count']
    
    return df


def print_latest_analysis(df, stock_code, logger):
    """打印最新一周的分析结果 - 优化版，过滤空行"""
    if len(df) == 0:
        logger.info(f"股票 {stock_code} 没有数据")
        return
    
    latest_week = df.iloc[-1]
    
    # 构建信息列表，只添加非空内容
    info_lines = []
    info_lines.append(f"\n{'='*60}")
    info_lines.append(f"📊 股票 {stock_code} 最新周线分析结果")
    info_lines.append(f"{'='*60}")
    
    if pd.notna(latest_week.get('date')):
        info_lines.append(f"日期: {latest_week['date'].strftime('%Y-%m-%d')}")
    if pd.notna(latest_week.get('close')):
        info_lines.append(f"收盘价: {latest_week['close']:.4f}")
    
    # EMA数值
    ema_values = []
    for ema in ['ema5', 'ema10', 'ema20', 'ema50', 'ema100', 'ema200']:
        if ema in df.columns and pd.notna(latest_week.get(ema)):
            ema_values.append(f"{ema.upper()}: {latest_week[ema]:.4f}")
    if ema_values:
        info_lines.append("")
        info_lines.append("[EMA数值]")
        info_lines.extend(ema_values)
    
    # VOL_EMA5数值
    if 'vol_ema5' in df.columns and pd.notna(latest_week.get('vol_ema5')):
        info_lines.append("")
        info_lines.append("[VOL_EMA5数值]")
        info_lines.append(f"VOL_EMA5: {latest_week['vol_ema5']:.2f}")
    
    # RSI14数值
    if 'rsi14' in df.columns:
        info_lines.append("")
        info_lines.append("[RSI14数值]")
        rsi_value = latest_week['rsi14'] if not pd.isna(latest_week['rsi14']) else 'N/A'
        if not pd.isna(rsi_value):
            info_lines.append(f"RSI14: {rsi_value:.2f}")
            if rsi_value > 70:
                info_lines.append("状态: 超买")
            elif rsi_value < 30:
                info_lines.append("状态: 超卖")
            else:
                info_lines.append("状态: 中性")
        else:
            info_lines.append("RSI14: N/A")
            info_lines.append("状态: 数据不足")
    
    # 三角形形态
    info_lines.append("")
    info_lines.append("[EMA5/10/20 三角形形态]")
    golden = latest_week.get('golden_triangle', False)
    death = latest_week.get('death_triangle', False)
    info_lines.append(f"Golden_Triangle: {'是 (EMA5>EMA10>EMA20)' if golden else '否'}")
    info_lines.append(f"Death_Triangle: {'是 (EMA5<EMA10<EMA20)' if death else '否'}")
    
    # 均线状态分析
    info_lines.append("")
    info_lines.append("[均线状态分析]")
    ema_pairs = [
        ('ema5', 'ema10', 'ema5_10_status', 'ema5_10_streak'),
        ('ema5', 'ema20', 'ema5_20_status', 'ema5_20_streak'),
        ('ema10', 'ema50', 'ema10_50_status', 'ema10_50_streak'),
        ('ema20', 'ema50', 'ema20_50_status', 'ema20_50_streak')
    ]
    ema_status_lines = []
    for short_col, long_col, status_col, streak_col in ema_pairs:
        if status_col in df.columns and pd.notna(latest_week.get(status_col)):
            status = latest_week[status_col]
            if status:
                ema_pair_name = f"{short_col[3:]}/{long_col[3:]}"
                streak = latest_week.get(streak_col, 0)
                ema_status_lines.append(f"{ema_pair_name}状态: {status} (已持续 {int(streak)} 周)")
    if ema_status_lines:
        info_lines.extend(ema_status_lines)
    
    # MACD分析
    info_lines.append("")
    info_lines.append("[MACD分析]")
    if 'macd_status' in df.columns and pd.notna(latest_week.get('macd_status')):
        macd_status = latest_week['macd_status']
        if "金叉" in macd_status:
            streak = latest_week.get('macd_golden_streak', 0)
        else:
            streak = latest_week.get('macd_death_streak', 0)
        
        if macd_status:
            info_lines.append(f"MACD状态: {macd_status} (已持续 {int(streak)} 周)")
    if 'dif' in df.columns and pd.notna(latest_week.get('dif')):
        info_lines.append(f"DIF: {latest_week['dif']:.4f}")
    if 'dea' in df.columns and pd.notna(latest_week.get('dea')):
        info_lines.append(f"DEA: {latest_week['dea']:.4f}")
    
    # 高质量信号
    if 'high_quality_golden' in df.columns:
        info_lines.append("")
        info_lines.append("[高质量信号]")
        info_lines.append(f"高质量金叉: {latest_week['high_quality_golden']}")
    
    # 成交量分析
    if all(col in df.columns for col in ['volume', 'vol_ema5', 'volume_ratio']):
        if pd.notna(latest_week.get('volume')):
            info_lines.append("")
            info_lines.append("[成交量分析]")
            volume = latest_week['volume']
            ema5_volume = latest_week.get('vol_ema5', 0)
            volume_ratio = latest_week.get('volume_ratio', 0)
            
            def format_large_number(num):
                if pd.isna(num):
                    return "不可用"
                if num > 1e9:
                    return f"{num/1e9:.2f}B"
                elif num > 1e6:
                    return f"{num/1e6:.2f}M"
                return f"{num:.2f}"
            
            volume_msg = format_large_number(volume)
            ma5_msg = format_large_number(ema5_volume)
            info_lines.append(f"成交量: {volume_msg} (比率: {volume_ratio:.2f}x) vs 5周均量: {ma5_msg}")
    
    info_lines.append(f"{'='*60}")
    
    # 过滤空行并输出
    for line in info_lines:
        if line.strip():  # 跳过空行
            logger.info(line)


# ==================== 主程序 ====================
def main():
    """主函数，程序的入口点"""
    try:
        # 获取项目根目录
        script_dir = Path(__file__).resolve().parent
        core_dir = script_dir.parent
        if str(core_dir) not in sys.path:
            sys.path.insert(0, str(core_dir))
        
        from utl.stock_analysis_utl import get_project_root
        core_dir_from_utils = get_project_root()
        project_dir = core_dir_from_utils.parent
        
        if str(project_dir) not in sys.path:
            sys.path.insert(0, str(project_dir))
        
        from utl.stock_analysis_utl import (
            load_config,
            setup_windows_encoding,
            GlobalConfig as UtlGlobalConfig
        )
        
        # 设置编码
        setup_windows_encoding()
        
        # 加载配置
        config_path = os.path.join(project_dir, 'config', 'stock_data_analysis.par')
        CONFIG = load_config(config_path, project_dir)
        
        # 更新全局配置
        GlobalConfig.update_paths(CONFIG, project_dir)
        
        # 设置日志
        logger = setup_logging(GlobalConfig.full_log_dir)
        
        logger.info("="*60)
        logger.info("Weekly_TA2B_Calculate_indicators 启动")
        logger.info("="*60)
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"数据库路径: {GlobalConfig.full_db_path}")
        
        # 获取股票列表
        tickers = CONFIG.get('tickers', [])
        if not tickers:
            logger.error("错误: 配置文件中未找到tickers设置")
            return
        
        logger.info(f"股票代码数量: {len(tickers)}")
        logger.info(f"股票代码: {tickers}")
        
        # 连接数据库
        conn = get_db_connection(GlobalConfig.full_db_path)
        
        # 从数据库加载股票名称映射
        stock_names = load_stock_names_from_db(conn)
        
        # 收集所有处理结果
        processed_stocks = []
        skipped_stocks = []
        error_stocks = []
        
        try:
            # 处理每个股票
            for stock_code in tickers:
                logger.info(f"\n{'='*60}")
                logger.info(f"处理股票: {stock_code}")
                logger.info(f"{'='*60}")
                
                # 获取股票名称
                stock_name = stock_names.get(stock_code, '')
                if not stock_name:
                    logger.warning(f"⚠️ 未找到股票 {stock_code} 的名称，请检查 hk_stock_info 表")
                    # 使用股票代码作为名称的备选
                    stock_name = stock_code
                else:
                    logger.info(f"📌 股票名称: {stock_name}")
                
                # 检查分析状态
                status, latest_analysis_date, latest_kline_date = check_analysis_status(conn, stock_code)
                
                if status == 'up_to_date':
                    logger.info(f"✅ {stock_code}({stock_name}) k线分析数据已存在，无需重复计算")
                    skipped_stocks.append(stock_code)
                    # 加载已有分析数据用于显示
                    df = load_weekly_data_from_db(conn, stock_code)
                    if not df.empty:
                        print_latest_analysis(df, stock_code, logger)
                    continue
                
                elif status == 'data_error':
                    logger.warning(f"⚠️ {stock_code}({stock_name}) k线原始数据缺失或k线分析数据有误，需进行核查")
                    if latest_analysis_date and latest_kline_date:
                        logger.warning(f"  分析数据最新日期: {latest_analysis_date}")
                        logger.warning(f"  原始数据最新日期: {latest_kline_date}")
                    error_stocks.append(stock_code)
                    continue
                
                elif status == 'need_update':
                    logger.info(f"🔄 {stock_code}({stock_name}) 需要更新分析数据")
                    if latest_analysis_date:
                        logger.info(f"  分析数据最新日期: {latest_analysis_date}")
                    if latest_kline_date:
                        logger.info(f"  原始数据最新日期: {latest_kline_date}")
                    
                    # 加载原始数据
                    df = load_weekly_data_from_db(conn, stock_code)
                    if df.empty:
                        logger.warning(f"⚠️ {stock_code}({stock_name}) 原始数据为空，跳过")
                        error_stocks.append(stock_code)
                        continue
                    
                    logger.info(f"  加载原始数据: {len(df)} 条记录")
                    
                    # 进行分析
                    analyzed_df = analyze_weekly_data(df)
                    
                    # 保存结果（包含股票名称）
                    save_analysis_to_db(conn, analyzed_df, stock_code, stock_name)
                    logger.info(f"✅ {stock_code}({stock_name}) 分析数据已保存到数据库 (共 {len(analyzed_df)} 条记录)")
                    processed_stocks.append(stock_code)
                    
                    # 显示最新结果
                    print_latest_analysis(analyzed_df, stock_code, logger)
        
        finally:
            conn.close()
        
        # 显示总结信息（在"全部完成"之前）
        logger.info("\n" + "="*60)
        logger.info("📊 处理总结")
        logger.info("="*60)
        if processed_stocks:
            logger.info(f"✅ 成功更新: {len(processed_stocks)} 只股票 - {', '.join(processed_stocks)}")
        else:
            logger.info("✅ 成功更新: 0 只股票")
        
        if skipped_stocks:
            logger.info(f"⏭️  跳过（已是最新）: {len(skipped_stocks)} 只股票 - {', '.join(skipped_stocks)}")
        
        if error_stocks:
            logger.info(f"❌ 处理失败: {len(error_stocks)} 只股票 - {', '.join(error_stocks)}")
        
        logger.info("="*60)
        
        logger.info("\n" + "="*60)
        logger.info("✅ 全部周交易数据分析完成！")
        logger.info("="*60)
    
    except Exception as e:
        logger.error(f"发生未知错误: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
