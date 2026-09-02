#!/usr/bin/env python
# coding: utf-8

"""
Name: Quarterly_TA2B_Calculate_indicators.py
Function: 
计算季线数据技术分析指标。
输入数据表：hk_hist_quarterly_kline
输出数据表：hk_quarterly_kline_analysis
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
    log_file = Path(log_dir) / 'Quarterly_TA2B_Calculate_indicators.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 移除可能存在的旧处理器，避免重复
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # 自定义日期格式，去掉毫秒
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
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


def load_tickers_from_config(config, config_key='tickers'):
    """
    从配置中加载股票代码列表
    参考 Weekly_TA2A_Aggregate_Indicators_akshare.py 的处理方式
    """
    tickers = config.get(config_key, [])
    if not tickers:
        logging.warning(f"配置文件中未找到 {config_key} 配置")
        return []
    
    # 如果 tickers 是字符串，按逗号分割
    if isinstance(tickers, str):
        tickers = [t.strip().zfill(5) for t in tickers.split(',') if t.strip()]
    elif isinstance(tickers, list):
        tickers = [str(t).strip().zfill(5) for t in tickers if str(t).strip()]
    else:
        logging.warning(f"不支持的 tickers 类型: {type(tickers)}")
        return []
    
    logging.info(f"从配置加载了 {len(tickers)} 个股票代码: {tickers[:5]}...")
    return tickers


def load_stock_names_from_json(json_path):
    """
    从stock_list.json加载股票名称映射
    兼容两种字段名格式：code/name 和 stock_code/stock_name
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        stock_name_map = {}
        
        if 'stocks' in data:
            for stock in data['stocks']:
                # 兼容两种字段名格式
                code = stock.get('stock_code', '') or stock.get('code', '')
                name = stock.get('stock_name', '') or stock.get('name', '')
                
                code = code.strip()
                name = name.strip()
                
                if code and name:
                    code = code.zfill(5)
                    stock_name_map[code] = name
        
        logging.info(f"从 {json_path} 加载了 {len(stock_name_map)} 个股票名称映射")
        return stock_name_map
    except Exception as e:
        logging.warning(f"加载股票名称映射时出错: {e}")
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
        FROM hk_hist_quarterly_kline 
        WHERE stock_code = ?
    """, (stock_code,))
    kline_result = cursor.fetchone()
    latest_kline_date = kline_result['latest_date'] if kline_result else None
    
    # 获取分析数据最新日期
    cursor.execute("""
        SELECT MAX(date) as latest_date 
        FROM hk_quarterly_kline_analysis 
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


def load_quarterly_data_from_db(conn, stock_code):
    """从数据库加载季线数据"""
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
        FROM hk_hist_quarterly_kline
        WHERE stock_code = ?
        ORDER BY date ASC
    """
    df = pd.read_sql_query(query, conn, params=(stock_code,))
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        # 确保数值列是数值类型
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount', 
                          'amplitude', 'change_percent', 'change_amount', 'turnover_rate',
                          'ema5', 'ema10', 'ema20', 'ema50', 'ema100', 'ema200',
                          'dif', 'dea', 'macd']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def create_quarterly_analysis_table_if_not_exists(conn):
    """确保 hk_quarterly_kline_analysis 分析结果表存在"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hk_quarterly_kline_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            turnover_rate REAL,
            amplitude REAL,
            change_amount REAL,
            change_percent REAL,
            ema5 REAL,
            ema10 REAL,
            ema20 REAL,
            ema50 REAL,
            ema100 REAL,
            ema200 REAL,
            macd_dif REAL,
            macd_signal REAL,
            macd_histogram REAL,
            ema5_10_status TEXT,
            ema5_10_streak INTEGER,
            ema5_20_status TEXT,
            ema5_20_streak INTEGER,
            ema10_50_status TEXT,
            ema10_50_streak INTEGER,
            ema20_50_status TEXT,
            ema20_50_streak INTEGER,
            golden_triangle INTEGER,
            death_triangle INTEGER,
            macd_cross TEXT,
            macd_status TEXT,
            macd_golden_streak INTEGER,
            macd_death_streak INTEGER,
            kdj_k REAL,
            kdj_d REAL,
            kdj_j REAL,
            vol_ema5 REAL,
            volume_ratio REAL,
            gain REAL,
            loss REAL,
            avg_gain REAL,
            avg_loss REAL,
            rs REAL,
            rsi14 REAL
        )
    """)
    conn.commit()


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
    
    # 确保分析结果表存在
    create_quarterly_analysis_table_if_not_exists(conn)
    
    # 先删除该股票已有的分析数据
    cursor.execute("DELETE FROM hk_quarterly_kline_analysis WHERE stock_code = ?", (stock_code,))
    
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
        # 处理状态字段 - 确保是字符串类型
        ema5_10_status = row.get('ema5_10_status', '')
        ema5_20_status = row.get('ema5_20_status', '')
        ema10_50_status = row.get('ema10_50_status', '')
        ema20_50_status = row.get('ema20_50_status', '')
        macd_cross = row.get('macd_cross', '')
        macd_status = row.get('macd_status', '')
        high_quality_golden = row.get('high_quality_golden', '')
        
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
            'ema5_10_status': ema5_10_status if ema5_10_status else None,
            'ema5_10_streak': row.get('ema5_10_streak'),
            'ema5_20_status': ema5_20_status if ema5_20_status else None,
            'ema5_20_streak': row.get('ema5_20_streak'),
            'ema10_50_status': ema10_50_status if ema10_50_status else None,
            'ema10_50_streak': row.get('ema10_50_streak'),
            'ema20_50_status': ema20_50_status if ema20_50_status else None,
            'ema20_50_streak': row.get('ema20_50_streak'),
            'golden_triangle': 1 if row.get('golden_triangle') else 0,
            'death_triangle': 1 if row.get('death_triangle') else 0,
            'macd_cross': macd_cross if macd_cross else None,
            'macd_status': macd_status if macd_status else None,
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
        insert_sql = f"INSERT INTO hk_quarterly_kline_analysis ({columns_str}) VALUES ({placeholders})"
        
        # 准备数据元组列表
        data_tuples = []
        for record in records:
            data_tuple = tuple(record.get(col) for col in columns)
            data_tuples.append(data_tuple)
        
        cursor.executemany(insert_sql, data_tuples)
        conn.commit()


def analyze_quarterly_data(df):
    """
    分析季线数据，计算技术指标
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
    
    # 7. 计算季线 KDJ
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
    """打印最新一个季度分析结果 - 优化版，过滤空行"""
    if len(df) == 0:
        logger.info(f"股票 {stock_code} 没有数据")
        return
    
    latest_month = df.iloc[-1]
    
    # 构建信息列表，只添加非空内容
    info_lines = []
    info_lines.append(f"\n{'='*60}")
    info_lines.append(f"📊 股票 {stock_code} 最新季线分析结果")
    info_lines.append(f"{'='*60}")
    
    if pd.notna(latest_month.get('date')):
        info_lines.append(f"日期: {latest_month['date'].strftime('%Y-%m-%d')}")
    if pd.notna(latest_month.get('close')):
        close_val = latest_month['close']
        if isinstance(close_val, (int, float)):
            info_lines.append(f"收盘价: {close_val:.4f}")
        else:
            info_lines.append(f"收盘价: {close_val}")
    
    # EMA数值
    ema_values = []
    for ema in ['ema5', 'ema10', 'ema20', 'ema50', 'ema100', 'ema200']:
        if ema in df.columns and pd.notna(latest_month.get(ema)):
            val = latest_month[ema]
            if isinstance(val, (int, float)):
                ema_values.append(f"{ema.upper()}: {val:.4f}")
            else:
                ema_values.append(f"{ema.upper()}: {val}")
    if ema_values:
        info_lines.append("")
        info_lines.append("[EMA数值]")
        info_lines.extend(ema_values)
    
    # VOL_EMA5数值
    if 'vol_ema5' in df.columns and pd.notna(latest_month.get('vol_ema5')):
        vol_val = latest_month['vol_ema5']
        if isinstance(vol_val, (int, float)):
            info_lines.append("")
            info_lines.append("[VOL_EMA5数值]")
            info_lines.append(f"VOL_EMA5: {vol_val:.2f}")
    
    # RSI14数值 - 修复类型错误
    if 'rsi14' in df.columns:
        info_lines.append("")
        info_lines.append("[RSI14数值]")
        rsi_value = latest_month.get('rsi14')
        
        # 检查是否为数值类型
        if pd.notna(rsi_value) and isinstance(rsi_value, (int, float)):
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
    golden = latest_month.get('golden_triangle', False)
    death = latest_month.get('death_triangle', False)
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
        if status_col in df.columns and pd.notna(latest_month.get(status_col)):
            status = latest_month[status_col]
            if status and status != '':
                ema_pair_name = f"{short_col[3:]}/{long_col[3:]}"
                streak = latest_month.get(streak_col, 0)
                if isinstance(streak, (int, float)):
                    streak_int = int(streak)
                else:
                    streak_int = 0
                ema_status_lines.append(f"{ema_pair_name}状态: {status} (已持续 {streak_int} 个季度)")
    if ema_status_lines:
        info_lines.extend(ema_status_lines)
    
    # MACD分析
    info_lines.append("")
    info_lines.append("[MACD分析]")
    if 'macd_status' in df.columns and pd.notna(latest_month.get('macd_status')):
        macd_status = latest_month['macd_status']
        if macd_status and macd_status != '':
            if "金叉" in macd_status:
                streak = latest_month.get('macd_golden_streak', 0)
            else:
                streak = latest_month.get('macd_death_streak', 0)
            
            if isinstance(streak, (int, float)):
                streak_int = int(streak)
            else:
                streak_int = 0
            info_lines.append(f"MACD状态: {macd_status} (已持续 {streak_int} 个季度)")
    
    if 'dif' in df.columns and pd.notna(latest_month.get('dif')):
        dif_val = latest_month['dif']
        if isinstance(dif_val, (int, float)):
            info_lines.append(f"DIF: {dif_val:.4f}")
        else:
            info_lines.append(f"DIF: {dif_val}")
    
    if 'dea' in df.columns and pd.notna(latest_month.get('dea')):
        dea_val = latest_month['dea']
        if isinstance(dea_val, (int, float)):
            info_lines.append(f"DEA: {dea_val:.4f}")
        else:
            info_lines.append(f"DEA: {dea_val}")
    
    # KDJ数值
    info_lines.append("")
    info_lines.append("[KDJ数值]")
    k_val = latest_month.get('kdj_k')
    d_val = latest_month.get('kdj_d')
    j_val = latest_month.get('kdj_j')
    if pd.notna(k_val) and isinstance(k_val, (int, float)):
        info_lines.append(f"K: {k_val:.2f}, D: {d_val:.2f}, J: {j_val:.2f}")
        if k_val > 80 and d_val > 80:
            info_lines.append("状态: 超买区 (K>80且D>80)")
        elif k_val < 20 and d_val < 20:
            info_lines.append("状态: 超卖区 (K<20且D<20)")
        else:
            info_lines.append("状态: 正常区间")
    else:
        info_lines.append("KDJ: 数据不足（需至少9个季度数据）")
    
    # 高质量信号
    if 'high_quality_golden' in df.columns:
        info_lines.append("")
        info_lines.append("[高质量信号]")
        hqg = latest_month.get('high_quality_golden', '')
        info_lines.append(f"高质量金叉: {hqg if hqg else '否'}")
    
    # 成交量分析
    if all(col in df.columns for col in ['volume', 'vol_ema5', 'volume_ratio']):
        if pd.notna(latest_month.get('volume')):
            info_lines.append("")
            info_lines.append("[成交量分析]")
            volume = latest_month['volume']
            ema5_volume = latest_month.get('vol_ema5', 0)
            volume_ratio = latest_month.get('volume_ratio', 0)
            
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
            if isinstance(volume_ratio, (int, float)):
                info_lines.append(f"成交量: {volume_msg} (比率: {volume_ratio:.2f}x) vs 5个季度均量: {ma5_msg}")
            else:
                info_lines.append(f"成交量: {volume_msg} vs 5个季度均量: {ma5_msg}")
    
    info_lines.append(f"{'='*60}")
    
    # 过滤空行并输出
    for line in info_lines:
        if line.strip():  # 跳过空行
            logger.info(line)


# ==================== 主程序 ====================
def main():
    """主函数，程序的入口点"""
    # ★★★ 在函数开始时就设置 logger，避免异常时 logging 未定义 ★★★
    logger = None
    
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
        
        # ★★★ 先设置基本的日志，以便在配置加载过程中有日志记录 ★★★
        # 使用临时日志目录
        temp_log_dir = Path(project_dir) / 'Log'
        temp_log_dir.mkdir(parents=True, exist_ok=True)
        logger = setup_logging(temp_log_dir)
        
        # 加载 stock_data_analysis.par 配置
        par_config_path = os.path.join(project_dir, 'config', 'stock_data_analysis.par')
        CONFIG = load_config(par_config_path, project_dir)
        
        if not CONFIG:
            logger.error(f"配置文件加载失败或为空: {par_config_path}")
            return
        
        # 更新全局配置
        GlobalConfig.full_data_dir = Path(project_dir) / CONFIG.get('data_dir', 'Data')
        GlobalConfig.full_report_dir = Path(project_dir) / CONFIG.get('report_dir', 'Report')
        GlobalConfig.full_log_dir = Path(project_dir) / CONFIG.get('log_dir', 'Log')
        GlobalConfig.full_temp_dir = Path(project_dir) / CONFIG.get('temp_dir', 'Temp')
        GlobalConfig.full_sqlite_dir = Path(project_dir) / CONFIG.get('sqlite_dir', 'SQLiteDB')
        GlobalConfig.db_name = CONFIG.get('db_name', 'HK_Stock.db')
        GlobalConfig.full_db_path = GlobalConfig.full_sqlite_dir / GlobalConfig.db_name
        
        # ★★★ 重新设置日志，使用正确的日志目录 ★★★
        logger = setup_logging(GlobalConfig.full_log_dir)
        
        logger.info("="*70)
        logger.info("✅ 运行版本: v3.2 - 从stock_data_analysis.par读取股票列表")
        logger.info("="*70)
        logger.info("="*60)
        logger.info("Quarterly_TA2B_Calculate_indicators 启动")
        logger.info("="*60)
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件位置: {par_config_path}")
        logger.info(f"日志文件位置: {GlobalConfig.full_log_dir / 'Quarterly_TA2B_Calculate_indicators.log'}")
        logger.info(f"数据库路径: {GlobalConfig.full_db_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        
        # 从配置中加载股票代码列表
        tickers = load_tickers_from_config(CONFIG, 'tickers')

        if not tickers:
            logger.error("无法从stock_data_analysis.par加载股票代码列表")
            # 尝试从stock_list.json加载作为备选
            logger.info("尝试从stock_list.json加载股票代码...")
            stock_list_path = os.path.join(project_dir, 'config', 'stock_list.json')
            stock_name_map = load_stock_names_from_json(stock_list_path)
            # 从 stock_name_map 的 keys 获取股票代码
            tickers = list(stock_name_map.keys())
            if tickers:
                logger.info(f"从stock_list.json加载了 {len(tickers)} 个股票代码")
            else:
                logger.error("所有来源都无法加载股票代码列表")
                return

        logger.info(f"股票代码列表 (前5个): {tickers[:5] if len(tickers) > 5 else tickers}")
        logger.info(f"共 {len(tickers)} 个股票")
        
        # 加载股票名称映射（从stock_list.json获取名称）
        stock_list_path = os.path.join(project_dir, 'config', 'stock_list.json')
        stock_name_map = load_stock_names_from_json(stock_list_path)
        
        # 连接数据库
        db_path = GlobalConfig.full_db_path
        if not os.path.exists(db_path):
            logger.error(f"数据库文件不存在: {db_path}")
            return
            
        conn = get_db_connection(db_path)
        logger.info(f"成功连接到数据库: {db_path}")

        # 确保分析结果表存在（首次运行时自动建表）
        create_quarterly_analysis_table_if_not_exists(conn)
        
        # 收集所有处理结果
        processed_stocks = []
        skipped_stocks = []
        error_stocks = []
        
        try:
            # 处理每个股票
            for stock_code in tickers:
                stock_code = str(stock_code).zfill(5)
                
                logger.info(f"\n{'='*60}")
                logger.info(f"处理股票: {stock_code}")
                logger.info(f"{'='*60}")
                
                # 获取股票名称
                stock_name = stock_name_map.get(stock_code, '')
                if not stock_name:
                    logger.warning(f"⚠️ 未找到股票 {stock_code} 的名称，请检查 stock_list.json")
                    # 使用股票代码作为名称的备选
                    stock_name = stock_code
                
                # 检查分析状态
                status, latest_analysis_date, latest_kline_date = check_analysis_status(conn, stock_code)
                
                if status == 'up_to_date':
                    logger.info(f"✅ {stock_code} 季线分析数据已存在，无需重复计算")
                    skipped_stocks.append(stock_code)
                    # 加载已有分析数据用于显示
                    df = load_quarterly_data_from_db(conn, stock_code)
                    if not df.empty:
                        print_latest_analysis(df, stock_code, logger)
                    continue
                
                elif status == 'data_error':
                    logger.warning(f"⚠️ {stock_code} 季线原始数据缺失或分析数据有误，需进行核查")
                    if latest_analysis_date and latest_kline_date:
                        logger.warning(f"  分析数据最新日期: {latest_analysis_date}")
                        logger.warning(f"  原始数据最新日期: {latest_kline_date}")
                    error_stocks.append(stock_code)
                    continue
                
                elif status == 'need_update':
                    logger.info(f"🔄 {stock_code} 需要更新分析数据")
                    if latest_analysis_date:
                        logger.info(f"  分析数据最新日期: {latest_analysis_date}")
                    if latest_kline_date:
                        logger.info(f"  原始数据最新日期: {latest_kline_date}")
                    
                    # 加载原始数据
                    df = load_quarterly_data_from_db(conn, stock_code)
                    if df.empty:
                        logger.warning(f"⚠️ {stock_code} 原始数据为空，跳过")
                        error_stocks.append(stock_code)
                        continue
                    
                    logger.info(f"  加载原始数据: {len(df)} 条记录")
                    
                    # 进行分析
                    analyzed_df = analyze_quarterly_data(df)
                    
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
        logger.info("✅ 全部季度交易数据分析完成！")
        logger.info("="*60)
    
    except Exception as e:
        # ★★★ 使用 logger 如果已初始化，否则使用 print ★★★
        if logger:
            logger.error(f"发生未知错误: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
        else:
            print(f"发生未知错误: {type(e).__name__}: {e}")
            print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
