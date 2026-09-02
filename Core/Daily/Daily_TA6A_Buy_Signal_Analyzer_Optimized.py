#!/usr/bin/env python
# coding: utf-8
r"""
Step 11: Generate buy signals 
Name： Daily_TA6A_Buy_Signal_Analyzer_Optimized.py
Function:
买入信号分析--自动模式 （读取配置文件）
1. 遍历配置文件中的股票代码，进行多任务并行处理。
2. 生成买入信号摘要报告（PDF）。
3. 买入详细信号保存到数据库表 hk_buy_signal_details。


优化版买入信号处理程序 - 完整代码
主要优化点：
1. 数据预加载和共享缓存
2. 信号检测并行化（ThreadPoolExecutor）
3. 向量化计算增强
4. 数据库连接池和批量操作
5. 进程安全的缓存管理
6. 新加坡/北京时区支持 (UTC+8)
7. details列中日期格式统一为 yyyy-mm-dd
8. 修复 database is locked 问题（WAL模式+重试机制）
9. 修复 NaTType does not support strftime 错误
"""

import pandas as pd
import numpy as np
import os
import io
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple, Callable
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from functools import lru_cache, partial, wraps
import math

import logging
import logging.handlers
import multiprocessing as mp
from multiprocessing import Queue
import sqlite3
import time
import traceback
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from queue import Queue as ThreadQueue

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
    print(f"❌ 严重错误：无法导入 utl.stock_analysis_utl 模块: {e}")
    print("=" * 60)
    sys.exit(1)

# === 强制UTF-8编码输出 ===
if 'get_ipython' not in globals():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

setup_windows_encoding()

logger = logging.getLogger(__name__)
DEBUG = False

# ==================== 重试装饰器 ====================

def retry_on_locked(max_retries=5, delay=0.5, backoff=2.0):
    """
    数据库锁重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 退避倍数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    error_msg = str(e).lower()
                    if "database is locked" in error_msg and attempt < max_retries - 1:
                        logger.warning(
                            f"数据库被锁定，等待 {current_delay:.2f}秒后重试 "
                            f"(尝试 {attempt + 1}/{max_retries})"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                        last_exception = e
                    else:
                        raise
                except Exception as e:
                    raise
            
            if last_exception:
                raise last_exception
        return wrapper
    return decorator

# ==================== 时区工具（UTC+8 新加坡/北京时区） ====================
SINGAPORE_OFFSET = timedelta(hours=8)
SINGAPORE_TZ = timezone(SINGAPORE_OFFSET)

def get_singapore_time():
    """获取当前新加坡/北京时间 (UTC+8)"""
    return datetime.now(SINGAPORE_TZ)

def is_na_or_nat(value):
    """检查值是否为 NaT 或 NaN"""
    if value is None:
        return True
    try:
        return pd.isna(value)
    except:
        return False

def sanitize_na_values(obj):
    """
    递归将对象中的所有 NaT/NaN 转换为 None
    适用于整个信号DataFrame或字典
    """
    if isinstance(obj, dict):
        return {k: sanitize_na_values(v) for k, v in obj.items()}
    
    elif isinstance(obj, list):
        return [sanitize_na_values(x) for x in obj]
    
    elif isinstance(obj, pd.DataFrame):
        return obj.where(pd.notna(obj), None)
    
    elif isinstance(obj, pd.Series):
        return obj.where(pd.notna(obj), None)
    
    else:
        try:
            if pd.isna(obj):
                return None
        except:
            pass
        return obj

def date_to_str(date_obj):
    """将日期转换为yyyy-mm-dd格式字符串"""
    # 先检查 NaT/NaN
    if date_obj is None:
        return None
    try:
        if pd.isna(date_obj):
            return None
    except:
        pass
    
    if isinstance(date_obj, (pd.Timestamp, datetime)):
        return date_obj.strftime('%Y-%m-%d')
    
    return str(date_obj)

def convert_dates_in_dict(obj):
    """
    递归转换字典中的所有日期字段为yyyy-mm-dd格式
    正确处理 pd.NaT
    """
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            # 先检查 NaT/NaN（最重要！）
            if is_na_or_nat(value):
                result[key] = None
            elif isinstance(value, (pd.Timestamp, datetime)):
                result[key] = value.strftime('%Y-%m-%d')
            elif isinstance(value, dict):
                result[key] = convert_dates_in_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    convert_dates_in_dict(x) if isinstance(x, (dict, list))
                    else (None if is_na_or_nat(x)
                          else (x.strftime('%Y-%m-%d') if isinstance(x, (pd.Timestamp, datetime)) else x))
                    for x in value
                ]
            else:
                result[key] = value
        return result
    
    elif isinstance(obj, list):
        return [
            convert_dates_in_dict(x) if isinstance(x, (dict, list))
            else (None if is_na_or_nat(x)
                  else (x.strftime('%Y-%m-%d') if isinstance(x, (pd.Timestamp, datetime)) else x))
            for x in obj
        ]
    
    elif is_na_or_nat(obj):
        return None
    
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.strftime('%Y-%m-%d')
    
    return obj

# ==================== 数据库连接池 ====================
class DatabaseConnectionPool:
    """SQLite数据库连接池（线程安全）- 修复版"""
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self._connections = []
        self._max_size = 5  # 减少连接池大小，避免竞争
        self._lock = Lock()
        self._db_path = self._find_db_path()
        self._conn_count = 0
        
    def _find_db_path(self):
        db_path = os.path.join(project_dir, 'SQLiteDB', 'HK_Stock.db')
        if not os.path.exists(db_path):
            alt_paths = [
                os.path.join(project_dir, 'Data', 'HK_Stock.db'),
                os.path.join(project_dir.parent, 'SQLiteDB', 'HK_Stock.db'),
            ]
            for alt in alt_paths:
                if os.path.exists(alt):
                    db_path = alt
                    break
        return db_path
    
    def get_connection(self):
        with self._lock:
            if self._connections:
                conn = self._connections.pop()
                try:
                    conn.execute("SELECT 1").fetchone()
                    return conn
                except:
                    try:
                        conn.close()
                    except:
                        pass
            
            self._conn_count += 1
            conn = sqlite3.connect(
                self._db_path, 
                check_same_thread=False, 
                timeout=60.0,
                isolation_level=None
            )
            conn.row_factory = sqlite3.Row
            
            # 性能优化设置 - 解决 database is locked
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=60000")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=30000000000")
            
            return conn
    
    def return_connection(self, conn):
        if conn is not None:
            with self._lock:
                if len(self._connections) < self._max_size:
                    self._connections.append(conn)
                else:
                    try:
                        conn.close()
                    except:
                        pass
    
    def close_all(self):
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except:
                    pass
            self._connections.clear()

_db_pool = DatabaseConnectionPool()

def get_db_connection():
    return _db_pool.get_connection()

def return_db_connection(conn):
    _db_pool.return_connection(conn)

def close_db_connection():
    _db_pool.close_all()

# ==================== 数据缓存管理 ====================
class DataCache:
    """进程安全的数据缓存"""
    _instance = None
    _lock = Lock()
    _max_size = 200
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self._cache = {}
        self._lock = Lock()
        self._access_count = {}
    
    def get(self, key: str) -> Optional[pd.DataFrame]:
        with self._lock:
            if key in self._cache:
                self._access_count[key] = self._access_count.get(key, 0) + 1
                return self._cache[key].copy()
            return None
    
    def set(self, key: str, df: pd.DataFrame):
        with self._lock:
            if len(self._cache) >= self._max_size:
                if self._access_count:
                    min_key = min(self._access_count, key=self._access_count.get)
                    del self._cache[min_key]
                    del self._access_count[min_key]
            self._cache[key] = df.copy()
            self._access_count[key] = self._access_count.get(key, 0) + 1
    
    def clear(self):
        with self._lock:
            self._cache.clear()
            self._access_count.clear()

_data_cache = DataCache()

# ==================== 股票名称缓存 ====================
_stock_name_cache = {}
_cache_lock = Lock()

def get_stock_name(ticker: str) -> str:
    """
    获取股票名称（带缓存）
    从 hk_stock_info 表查询，如果找不到则返回股票代码
    """
    with _cache_lock:
        if ticker in _stock_name_cache:
            return _stock_name_cache[ticker]
    
    stock_name = ticker
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT stock_name FROM hk_stock_info WHERE stock_code = ?", (ticker,))
            result = cursor.fetchone()
            if result and result[0]:
                stock_name = result[0]
                logger.debug(f"从 hk_stock_info 获取股票名称: {ticker} -> {stock_name}")
            else:
                logger.debug(f"未在 hk_stock_info 中找到股票 {ticker} 的名称，使用代码作为名称")
        finally:
            return_db_connection(conn)
    except Exception as e:
        logger.warning(f"获取股票名称失败，使用代码代替: {e}")
    
    with _cache_lock:
        _stock_name_cache[ticker] = stock_name
    
    return stock_name
    
def refresh_stock_name_cache(ticker: str = None):
    """
    刷新股票名称缓存
    
    Args:
        ticker: 要刷新的股票代码，如果为 None 则清空所有缓存
    """
    global _stock_name_cache
    with _cache_lock:
        if ticker is None:
            _stock_name_cache.clear()
            logger.info("已清空所有股票名称缓存")
        elif ticker in _stock_name_cache:
            del _stock_name_cache[ticker]
            logger.info(f"已刷新股票 {ticker} 的名称缓存")
            

def get_cache_key(ticker: str, period: str) -> str:
    return f"{ticker}_{period}"

# ==================== 核心工具函数 ====================
def find_local_extrema(series: pd.Series, order: int = 5, mode: str = 'min') -> pd.Series:
    """向量化局部极值检测"""
    if mode == 'min':
        return (series == series.rolling(window=2*order+1, center=True, min_periods=1).min())
    elif mode == 'max':
        return (series == series.rolling(window=2*order+1, center=True, min_periods=1).max())
    else:
        raise ValueError("mode must be 'min' or 'max'")

def compute_candle_features(df: pd.DataFrame) -> pd.DataFrame:
    """向量化K线特征计算"""
    body_low = df[['Open', 'Close']].min(axis=1)
    body_high = df[['Open', 'Close']].max(axis=1)
    df['BodyLength'] = (df['Close'] - df['Open']).abs()
    df['LowerShadow'] = body_low - df['Low']
    df['UpperShadow'] = df['High'] - body_high
    return df

def any_within(condition: pd.Series, window: int) -> pd.Series:
    """向量化窗口内任意为真"""
    return condition.rolling(window, min_periods=1).max().fillna(0).astype(bool)

def rolling_all(series: pd.Series, window: int) -> pd.Series:
    """向量化窗口内全部为真"""
    s_int = series.astype(float)
    return (s_int.rolling(window, min_periods=window).sum() == window) & \
           (s_int.rolling(window, min_periods=window).count() == window)

def find_local_extrema_series(series: pd.Series, order: int = 5, mode: str = 'min') -> pd.Series:
    """局部极值检测"""
    if len(series) < 2 * order + 1:
        return pd.Series(False, index=series.index)
    if mode == 'min':
        return (series == series.rolling(window=2*order+1, center=True, min_periods=1).min())
    else:
        return (series == series.rolling(window=2*order+1, center=True, min_periods=1).max())

# ==================== 数据加载函数 ====================
def load_data_with_cache(ticker: str, period: str = 'daily') -> pd.DataFrame:
    """加载数据并缓存"""
    cache_key = get_cache_key(ticker, period)
    
    cached = _data_cache.get(cache_key)
    if cached is not None:
        return cached
    
    conn = get_db_connection()
    try:
        df = _load_data_from_db(conn, ticker, period)
    finally:
        return_db_connection(conn)
    
    df = _compute_extra_indicators(df)
    _data_cache.set(cache_key, df)
    
    return df

def _load_data_from_db(conn, ticker: str, period: str) -> pd.DataFrame:
    """从数据库加载数据"""
    if period == 'daily':
        kline_table = 'hk_daily_kline_analysis'
        moneyflow_table = 'hk_daily_moneyflow_analysis'
    elif period == 'weekly':
        kline_table = 'hk_weekly_kline_analysis'
        moneyflow_table = 'hk_weekly_moneyflow_analysis'
    elif period == 'monthly':
        kline_table = 'hk_monthly_kline_analysis'
        moneyflow_table = 'hk_monthly_moneyflow_analysis'
    else:
        raise ValueError(f"不支持的周期: {period}")
    
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({moneyflow_table})")
    moneyflow_columns = [row[1].lower() for row in cursor.fetchall()]
    
    desired_columns = [
        'institutional_flow', 'individual_flow', 'institutional_net_ratio',
        'individual_net_ratio', 'extra_large', 'large', 'medium', 'small'
    ]
    available_columns = [col for col in desired_columns if col in moneyflow_columns]
    
    select_parts = ["k.*"]
    for col in available_columns:
        select_parts.append(f"m.{col}")
    
    query = f"""
        SELECT {', '.join(select_parts)}
        FROM {kline_table} k
        LEFT JOIN {moneyflow_table} m 
            ON k.stock_code = m.stock_code AND k.date = m.date
        WHERE k.stock_code = ?
        ORDER BY k.date ASC
    """
    
    try:
        df = pd.read_sql_query(query, conn, params=(ticker,))
    except Exception:
        query_simple = f"""
            SELECT * FROM {kline_table}
            WHERE stock_code = ?
            ORDER BY date ASC
        """
        df = pd.read_sql_query(query_simple, conn, params=(ticker,))
    
    if df.empty:
        raise ValueError(f"未找到股票 {ticker} 的 {period} 数据")
    
    df.columns = df.columns.str.lower()
    
    column_mapping = {
        'date': 'Date', 'stock_code': 'stock_code', 'stock_name': 'stock_name',
        'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close',
        'volume': 'Volume', 'turnover_rate': 'Turnover_Rate',
        'change_percent': 'Change_Percent',
        'ema5': 'EMA5', 'ema10': 'EMA10', 'ema20': 'EMA20',
        'ema50': 'EMA50', 'ema60': 'EMA60', 'ema120': 'EMA120',
        'macd_dif': 'MACD_DIF', 'macd_signal': 'MACD_Signal',
        'macd_histogram': 'MACD_Histogram',
        'kdj_k': 'KDJ_K', 'kdj_d': 'KDJ_D', 'kdj_j': 'KDJ_J',
        'rsi14': 'RSI14',
        'bollinger_upper': 'Bollinger_Upper',
        'bollinger_lower': 'Bollinger_Lower',
        'bollinger_middle': 'Bollinger_Middle',
        'vol_ema5': 'VOL_EMA5', 'vol_ema10': 'VOL_EMA10',
        'volume_ratio': 'volume_ratio', 'obv': 'OBV',
        'institutional_flow': 'Institutional_Flow',
        'individual_flow': 'Individual_Flow',
        'institutional_net_ratio': 'Institutional_Net_Ratio',
        'individual_net_ratio': 'Individual_Net_Ratio',
        'extra_large': 'Extra_Large', 'large': 'Large',
        'medium': 'Medium', 'small': 'Small'
    }
    
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns and old_name != new_name:
            df.rename(columns={old_name: new_name}, inplace=True)
    
    df['Date'] = pd.to_datetime(df['Date'])
    
    if 'stock_code' in df.columns:
        df.drop(columns=['stock_code'], inplace=True)
    if 'stock_name' in df.columns:
        df.drop(columns=['stock_name'], inplace=True)
    
    return df.sort_values('Date').reset_index(drop=True)

def _compute_extra_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算额外的技术指标"""
    for span in [3, 5, 10, 20, 21, 50, 60, 63, 120]:
        col = f'EMA{span}'
        if col not in df.columns:
            df[col] = df['Close'].ewm(span=span, adjust=False).mean()
    
    if 'volume_ratio' not in df.columns:
        vol_ema5 = df['Volume'].rolling(5, min_periods=1).mean()
        df['volume_ratio'] = df['Volume'] / vol_ema5
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
    
    if 'VOL_EMA5' not in df.columns:
        df['VOL_EMA5'] = df['Volume'].rolling(5, min_periods=1).mean()
    if 'VOL_EMA10' not in df.columns:
        df['VOL_EMA10'] = df['Volume'].rolling(10, min_periods=1).mean()
    
    if 'MACD_DIF' not in df.columns:
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD_DIF'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD_DIF'] - df['MACD_Signal']
    
    if 'KDJ_K' not in df.columns:
        low_min = df['Low'].rolling(9, min_periods=1).min()
        high_max = df['High'].rolling(9, min_periods=1).max()
        rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
        rsv = rsv.fillna(50)
        df['KDJ_K'] = rsv.ewm(alpha=1/3, adjust=False).mean()
        df['KDJ_D'] = df['KDJ_K'].ewm(alpha=1/3, adjust=False).mean()
        df['KDJ_J'] = 3 * df['KDJ_K'] - 2 * df['KDJ_D']
    
    if 'RSI14' not in df.columns:
        delta = df['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['RSI14'] = 100 - (100 / (1 + rs))
        df['RSI14'] = df['RSI14'].fillna(50)
    
    if 'Bollinger_Lower' not in df.columns:
        window = 20
        middle = df['Close'].rolling(window).mean()
        std = df['Close'].rolling(window).std()
        df['Bollinger_Upper'] = middle + 2 * std
        df['Bollinger_Lower'] = middle - 2 * std
        df['Bollinger_Middle'] = middle
    
    if 'OBV' not in df.columns:
        obv = [0]
        for i in range(1, len(df)):
            if df['Close'].iloc[i] > df['Close'].iloc[i-1]:
                obv.append(obv[-1] + df['Volume'].iloc[i])
            elif df['Close'].iloc[i] < df['Close'].iloc[i-1]:
                obv.append(obv[-1] - df['Volume'].iloc[i])
            else:
                obv.append(obv[-1])
        df['OBV'] = obv
    
    df['Local_Min_5'] = find_local_extrema(df['Low'], order=5, mode='min')
    df['Local_Max_5'] = find_local_extrema(df['High'], order=5, mode='max')
    df['Local_Min_10'] = find_local_extrema(df['Low'], order=10, mode='min')
    df['Local_Max_10'] = find_local_extrema(df['High'], order=10, mode='max')
    
    df = compute_candle_features(df)
    return df

# ==================== 信号评分函数 ====================
BASE_SCORE_MAP = {
    "三线金叉共振1": 9,
    "三线金叉共振（均线+MACD+均量）": 9,
    "黄金买点3": 7,
    "黄金买点4": 7,
    "月线底背离1": 10,
    "月线底背离2": 10,
    "月线底背离3": 10,
    "月线MACD底背离+金叉（多周期嵌套）": 10,
    "周线底背离1": 9,
    "周线底背离2": 9,
    "周线底背离3": 9,
    "周线MACD底背离+金叉": 9,
    "一阳穿五线（均线粘合+MACD金叉）": 8.5,
    "双重底颈线放量突破": 8,
    "头肩底颈线放量突破": 8,
    "21日与63日均线圆弧底突破": 8,
    "底部立桩量（不破最低价）": 7.5,
    "空中加油（缩量回踩关键均线）": 7.5,
    "黄金分割回调（阳线回调至0.382/0.5）": 7,
    "均线多头排列首次金叉": 7,
    "看涨吞没（低位）": 6.5,
    "启明星（低位）": 6.5,
    "均线金叉（单一信号）": 6,
    "布林下轨超卖+反转K线": 6,
    "KDJ低位金叉（单一）": 5.5,
    "RSI超卖区拐头（单一）": 5.5,
    "突破缺口（无其他共振）": 5,
    "金针探底1": 6.5,
    "金针探底2": 6.5,
    "黄金坑": 7,
    "股价与机构资金流底背离": 6,
}

@lru_cache(maxsize=128)
def get_base_score(signal_name: str) -> float:
    return BASE_SCORE_MAP.get(signal_name, 5.0)

def compute_resonance_score(df_signal: pd.Series, daily_data: pd.DataFrame) -> float:
    """计算共振得分"""
    date = df_signal['Date']
    day = daily_data[daily_data['Date'] == date]
    if day.empty:
        return 0
    row = day.iloc[0]
    score = 0
    
    if row.get('MACD_DIF', 0) > row.get('MACD_Signal', 0):
        score += 2
    if (row.get('EMA5', 0) > row.get('EMA10', 0) > row.get('EMA20', 0)):
        score += 2
    if row.get('volume_ratio', 0) > 1.5:
        score += 2
    
    if 'KDJ_K' in row and 'KDJ_D' in row:
        k = row['KDJ_K']
        d = row['KDJ_D']
        if k > d:
            prev = daily_data[daily_data['Date'] < date].iloc[-1] if len(daily_data[daily_data['Date'] < date]) > 0 else None
            if prev is not None and prev.get('KDJ_K', 0) <= prev.get('KDJ_D', 0):
                score += 2
    
    if 'RSI14' in row and row['RSI14'] < 30:
        prev_rsi = daily_data[daily_data['Date'] < date].iloc[-1]['RSI14'] if len(daily_data[daily_data['Date'] < date]) > 0 else 100
        if row['RSI14'] > prev_rsi:
            score += 2
    
    return min(score, 10)

def compute_trend_score(ticker: str, signal_date: datetime) -> float:
    """计算趋势得分"""
    try:
        weekly = load_data_with_cache(ticker, 'weekly')
        monthly = load_data_with_cache(ticker, 'monthly')
    except:
        return 5.0
    
    week_data = weekly[weekly['Date'] <= signal_date].iloc[-1] if not weekly[weekly['Date'] <= signal_date].empty else None
    month_data = monthly[monthly['Date'] <= signal_date].iloc[-1] if not monthly[monthly['Date'] <= signal_date].empty else None
    
    trend_score = 0
    if week_data is not None:
        if week_data.get('EMA10', 0) > week_data.get('EMA20', 0) > week_data.get('EMA50', 0):
            trend_score += 5
        elif week_data.get('EMA10', 0) > week_data.get('EMA20', 0):
            trend_score += 3
        else:
            trend_score += 1
    
    if month_data is not None:
        if month_data.get('EMA10', 0) > month_data.get('EMA20', 0):
            trend_score += 5
        else:
            trend_score += 2
    
    return min(max(trend_score, 0), 10)

def compute_volume_score(df_signal: pd.Series, daily_data: pd.DataFrame) -> float:
    """计算量能得分"""
    date = df_signal['Date']
    day = daily_data[daily_data['Date'] == date]
    if day.empty:
        return 5.0
    
    vol_ratio = day.iloc[0].get('volume_ratio', 1.0)
    if vol_ratio >= 1.5:
        return 10
    elif vol_ratio >= 1.2:
        return 8
    elif vol_ratio >= 1.0:
        return 6
    else:
        return 3

# ==================== 信号检测函数 ====================

def query_triple_golden_cross1(ticker, start_date, end_date, features_to_show):
    """三线金叉共振1"""
    try:
        df = load_data_with_cache(ticker, 'daily')
        
        required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'EMA5', 'EMA20', 'MACD_DIF', 'MACD_Signal',
                         'Volume', 'VOL_EMA5', 'VOL_EMA10', 'volume_ratio']
        
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            if 'EMA5' in missing_cols or 'EMA20' in missing_cols or 'MACD_DIF' in missing_cols:
                return pd.DataFrame()
        
        optional_cols = ['Turnover_Rate', 'Change_Percent', 'Institutional_Flow', 'Individual_Flow']
        for col in optional_cols:
            if col not in df.columns:
                if col in ['Institutional_Flow', 'Individual_Flow']:
                    df[col] = 0.0
                elif col in ['Turnover_Rate', 'Change_Percent']:
                    df[col] = 0.0
        
        mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
        df = df.loc[mask].copy()

        ema_golden = (df['EMA5'] > df['EMA20']) & (df['EMA5'].shift(1) <= df['EMA20'].shift(1))
        macd_golden = (df['MACD_DIF'] > df['MACD_Signal']) & (df['MACD_DIF'].shift(1) <= df['MACD_Signal'].shift(1)) & \
                      (df['MACD_DIF'] < 0.05) & (df['MACD_Signal'] < 0.05)
        vol_golden = (df['VOL_EMA5'] > df['VOL_EMA10']) & (df['VOL_EMA5'].shift(1) <= df['VOL_EMA10'].shift(1))

        def get_last_event_date(condition_series, date_series):
            last_date = pd.NaT
            result = []
            for cond, dt in zip(condition_series, date_series):
                if cond:
                    last_date = dt
                result.append(last_date)
            return pd.Series(result, index=condition_series.index)

        df['Last_EMA_Golden_Date'] = get_last_event_date(ema_golden, df['Date'])
        df['Last_MACD_Golden_Date'] = get_last_event_date(macd_golden, df['Date'])
        df['Last_VOL_Golden_Date'] = get_last_event_date(vol_golden, df['Date'])

        ema_recent = any_within(ema_golden, 3)
        macd_recent = any_within(macd_golden, 3)
        vol_recent = any_within(vol_golden, 3)
        triple_condition = ema_recent & macd_recent & vol_recent

        result_df = df.loc[triple_condition].copy()
        
        base_output_cols = ['Date', 'Close', 'EMA5', 'EMA20', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram',
                            'Volume', 'VOL_EMA5', 'VOL_EMA10', 'volume_ratio',
                            'Last_EMA_Golden_Date', 'Last_MACD_Golden_Date', 'Last_VOL_Golden_Date']
        
        for col in optional_cols:
            if col in result_df.columns:
                base_output_cols.append(col)
        
        output_cols = base_output_cols + [c for c in features_to_show if c not in base_output_cols]
        available_cols = [c for c in output_cols if c in result_df.columns]
        return result_df[available_cols]
    except Exception as e:
        logger.debug(f"query_triple_golden_cross1 执行出错: {e}")
        return pd.DataFrame()

def query_needle_bottom1(ticker, start_date, end_date, features_to_show=None):
    """金针探底1"""
    df = load_data_with_cache(ticker, 'daily')
    if 'LowerShadow' not in df.columns or 'BodyLength' not in df.columns or 'UpperShadow' not in df.columns:
        df = compute_candle_features(df)
    df['Low_30d'] = df['Low'].rolling(60, min_periods=1).min().shift(1)
    
    for col in ['Extra_Large', 'Large', 'Medium', 'Small']:
        if col not in df.columns:
            df[col] = 0.0
    
    cond = ((df['LowerShadow'] > 1.2 * df['BodyLength']) & (df['LowerShadow'] > df['UpperShadow']) &
            (df['Extra_Large'] > 0) & (df['Large'] > 0) & (df['Medium'] > 0) & (df['Small'] > 0) &
            (df['volume_ratio'] > 1.5) & (df['Close'] < df['EMA20']) & (df['Close'] > df['Low_30d']))
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = cond & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    return result_df

def query_needle_bottom2(ticker, start_date, end_date, features_to_show=None):
    """金针探底2"""
    df = load_data_with_cache(ticker, 'daily')
    if 'LowerShadow' not in df.columns or 'BodyLength' not in df.columns or 'UpperShadow' not in df.columns:
        df = compute_candle_features(df)
    df['Low_30d'] = df['Low'].rolling(60, min_periods=1).min().shift(1)
    
    if 'Institutional_Net_Ratio' not in df.columns:
        df['Institutional_Net_Ratio'] = 0.0
    if 'Individual_Net_Ratio' not in df.columns:
        df['Individual_Net_Ratio'] = 0.0
    
    cond = ((df['LowerShadow'] > 1.2 * df['BodyLength']) & (df['LowerShadow'] > df['UpperShadow']) &
            (df['Institutional_Net_Ratio'] > 0) & (df['Individual_Net_Ratio'] < 0) &
            (df['volume_ratio'] > 1.5) & (df['Close'] < df['EMA20']) & (df['Close'] > df['Low_30d']))
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = cond & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    return result_df

def query_golden_pit(ticker, start_date, end_date, features_to_show=None):
    """黄金坑"""
    df = load_data_with_cache(ticker, 'daily')
    if 'KDJ_K' not in df.columns:
        low_min = df['Low'].rolling(9, min_periods=1).min()
        high_max = df['High'].rolling(9, min_periods=1).max()
        rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
        rsv = rsv.fillna(50)
        df['KDJ_K'] = rsv.ewm(alpha=1/3, adjust=False).mean()
        df['KDJ_D'] = df['KDJ_K'].ewm(alpha=1/3, adjust=False).mean()
        df['KDJ_J'] = 3 * df['KDJ_K'] - 2 * df['KDJ_D']
    
    cond = (any_within((df['Close'] < df['EMA60']).shift(1), 10) &
            (df['Close'] > df['EMA60']) & (df['Close'] > df['Open']) &
            (df['volume_ratio'] > 1.5) &
            any_within((df['KDJ_J'] > 20) & (df['KDJ_J'].shift(1) <= 20), 3) &
            (df['OBV'] > df['OBV'].rolling(10, min_periods=1).min().shift(1)))
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = cond & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    return result_df

def query_price_inst_divergence(ticker, start_date, end_date, features_to_show=None):
    """股价与机构资金流底背离"""
    df = load_data_with_cache(ticker, 'daily')
    
    if 'Change_Percent' not in df.columns:
        df['Change_Percent'] = (df['Close'] - df['Close'].shift(1)) / df['Close'].shift(1) * 100
        df['Change_Percent'] = df['Change_Percent'].fillna(0)
    
    if 'Institutional_Flow' not in df.columns:
        df['Institutional_Flow'] = 0.0
    
    cond_price_down = rolling_all(df['Change_Percent'] < 0, 2)
    cond_inst_inflow = rolling_all(df['Institutional_Flow'] > 0, 2)
    cond = cond_price_down & cond_inst_inflow
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = cond & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    return result_df

def query_golden_buy_point3(ticker, start_date, end_date, features_to_show):
    """黄金买点3"""
    daily_df = load_data_with_cache(ticker, 'daily')
    weekly_df = load_data_with_cache(ticker, 'weekly')
    
    extra_cols = ['week_period', 'weekly_bull', 'daily_golden']
    all_features = list(set(features_to_show + extra_cols))
    daily_cols = ['Date', 'Close', 'EMA5', 'EMA20'] + [c for c in all_features if c not in extra_cols]
    daily_cols = list(set(daily_cols))
    daily_df = daily_df[daily_cols].copy()
    
    if 'EMA10' not in weekly_df.columns or 'EMA50' not in weekly_df.columns:
        raise ValueError("周线文件缺少 EMA10 或 EMA50 列")
    
    weekly_df['weekly_bull'] = weekly_df['EMA10'] > weekly_df['EMA50']
    daily_df['week_period'] = daily_df['Date'].dt.to_period('W-FRI')
    weekly_df['week_period'] = weekly_df['Date'].dt.to_period('W-FRI')
    
    merged = daily_df.merge(weekly_df[['week_period', 'weekly_bull']], on='week_period', how='left')
    with pd.option_context('future.no_silent_downcasting', True):
        merged['weekly_bull'] = merged['weekly_bull'].fillna(False).astype(bool)
    merged['daily_golden'] = (merged['EMA5'] > merged['EMA20']) & (merged['EMA5'].shift(1) <= merged['EMA20'].shift(1))
    
    condition = merged['weekly_bull'] & merged['daily_golden']
    date_mask = (merged['Date'] >= pd.to_datetime(start_date)) & (merged['Date'] <= pd.to_datetime(end_date))
    final_mask = condition & date_mask
    result_df = merged.loc[final_mask].copy()
    
    if result_df.empty:
        return result_df
    cols = ['Date'] + [c for c in result_df.columns if c != 'Date']
    result_df = result_df[cols]
    return result_df

def query_golden_buy_point4(ticker, start_date, end_date, features_to_show):
    """黄金买点4"""
    df = load_data_with_cache(ticker, 'weekly')
    needed_cols = ['Date', 'EMA10', 'EMA50', 'MACD_DIF', 'MACD_Signal', 'Volume', 'VOL_EMA5']
    missing = [c for c in needed_cols if c not in df.columns]
    if missing:
        raise ValueError(f"周线文件缺少列: {missing}")
    
    golden_ema = (df['EMA10'] > df['EMA50']) & (df['EMA10'].shift(1) <= df['EMA50'].shift(1))
    golden_macd = (df['MACD_DIF'] > df['MACD_Signal']) & (df['MACD_DIF'].shift(1) <= df['MACD_Signal'].shift(1))
    volume_surge = df['Volume'] >= df['VOL_EMA5'] * 2
    window_weeks = 6
    
    cond_ema = any_within(golden_ema, window_weeks)
    cond_macd = any_within(golden_macd, window_weeks)
    cond_vol = any_within(volume_surge, window_weeks)
    condition = cond_ema & cond_macd & cond_vol
    
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = condition & date_mask
    result_df = df.loc[final_mask].copy()
    
    if features_to_show:
        available_cols = [c for c in features_to_show if c in result_df.columns]
        return result_df[available_cols] if available_cols else pd.DataFrame()
    return result_df

def _find_bottom_div_details(df, price_col, ind_col, lookback=12, tolerance=1.2, max_gap_days=730):
    """寻找底背离详情"""
    records = []
    for i in range(lookback, len(df)):
        window = df.iloc[i-lookback:i+1]
        curr_idx = window.index[-1]
        low1_idx = window[price_col].idxmin()
        low1_price = window.loc[low1_idx, price_col]
        low1_ind = window.loc[low1_idx, ind_col]
        low1_date = df.loc[low1_idx, 'Date']
        
        if window.loc[curr_idx, 'Close'] > low1_price * tolerance:
            continue
        
        start_date = low1_date - pd.Timedelta(days=max_gap_days)
        prev_data = df.iloc[:low1_idx]
        prev_data = prev_data[prev_data['Date'] >= start_date]
        if len(prev_data) < 3:
            continue
        
        candidates = prev_data[(prev_data[price_col] > low1_price) & (prev_data[ind_col] < low1_ind)]
        if candidates.empty:
            continue
        
        candidates_sorted = candidates.sort_values(by=[price_col, ind_col, 'Date'], ascending=[True, True, False])
        best = candidates_sorted.iloc[0]
        records.append({
            'signal_date': df.loc[curr_idx, 'Date'],
            'low1_date': low1_date,
            'low1_price': low1_price,
            'low1_ind': low1_ind,
            'low2_date': best['Date'],
            'low2_price': best[price_col],
            'low2_ind': best[ind_col],
            'indicator': ind_col.replace('MACD_', '')
        })
    return pd.DataFrame(records)

def query_monthly_divergence1(ticker, start_date, end_date, features_to_show):
    """月线底背离1"""
    df = load_data_with_cache(ticker, 'monthly')
    needed_cols = ['Date', 'Low', 'Close', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram']
    missing = [c for c in needed_cols if c not in df.columns]
    if missing:
        raise ValueError(f"月线文件缺少以下列: {missing}")
    
    dif_divs = _find_bottom_div_details(df, 'Low', 'MACD_DIF', lookback=12)
    hist_divs = _find_bottom_div_details(df, 'Low', 'MACD_Histogram', lookback=12)
    
    all_divs_dict = {}
    for _, row in dif_divs.iterrows():
        key = (row['low1_date'], row['low2_date'])
        all_divs_dict[key] = row.to_dict()
    for _, row in hist_divs.iterrows():
        key = (row['low1_date'], row['low2_date'])
        if key in all_divs_dict:
            existing = all_divs_dict[key]
            existing['indicator'] = '双重'
            existing['hist_low1_ind'] = row['low1_ind']
            existing['hist_low2_ind'] = row['low2_ind']
        else:
            all_divs_dict[key] = row.to_dict()
    
    all_divs = list(all_divs_dict.values())
    if not all_divs:
        return pd.DataFrame()
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    filtered_divs = [d for d in all_divs if start <= d['low1_date'] <= end]
    if not filtered_divs:
        return pd.DataFrame()
    
    rows = []
    for d in filtered_divs:
        row = {
            'Date': d['low1_date'],
            'Close': d['low1_price'],
            'Div_Type': d['indicator'],
            'Div_Low1_Date': d['low1_date'],
            'Div_Price_Low1': d['low1_price'],
            'Div_Ind_Low1': d['low1_ind'],
            'Div_Low2_Date': d['low2_date'],
            'Div_Price_Low2': d['low2_price'],
            'Div_Ind_Low2': d['low2_ind'],
        }
        if d['indicator'] == '双重':
            row['Hist_Low1_Ind'] = d['hist_low1_ind']
            row['Hist_Low2_Ind'] = d['hist_low2_ind']
        elif d['indicator'] == 'Histogram':
            row['Hist_Low1_Ind'] = d['low1_ind']
            row['Hist_Low2_Ind'] = d['low2_ind']
        else:
            hist1 = df.loc[df['Date'] == d['low1_date'], 'MACD_Histogram'].values
            hist2 = df.loc[df['Date'] == d['low2_date'], 'MACD_Histogram'].values
            if len(hist1) and len(hist2):
                row['Hist_Low1_Ind'] = hist1[0]
                row['Hist_Low2_Ind'] = hist2[0]
        rows.append(row)
    
    output_df = pd.DataFrame(rows).sort_values('Date').reset_index(drop=True)
    return output_df

def query_monthly_divergence2(ticker, start_date, end_date, features_to_show):
    """月线底背离2"""
    df = load_data_with_cache(ticker, 'monthly')
    needed_cols = ['Date', 'Low', 'Close', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram', 'KDJ_K', 'KDJ_D', 'Volume', 'EMA5', 'VOL_EMA5']
    missing = [c for c in needed_cols if c not in df.columns]
    if missing:
        raise ValueError(f"月线文件缺少以下列: {missing}")

    def _find_bottom_div_details_local(df, price_col, ind_col, lookback=12, tolerance=1.2, max_gap_days=730):
        records = []
        for i in range(lookback, len(df)):
            window = df.iloc[i-lookback:i+1]
            curr_idx = window.index[-1]
            low1_idx = window[price_col].idxmin()
            low1_price = window.loc[low1_idx, price_col]
            low1_ind = window.loc[low1_idx, ind_col]
            low1_date = df.loc[low1_idx, 'Date']
            if window.loc[curr_idx, 'Close'] > low1_price * tolerance:
                continue
            start_date = low1_date - pd.Timedelta(days=max_gap_days)
            prev_data = df.iloc[:low1_idx]
            prev_data = prev_data[prev_data['Date'] >= start_date]
            if len(prev_data) < 3:
                continue
            candidates = prev_data[(prev_data[price_col] > low1_price) & (prev_data[ind_col] < low1_ind)]
            if candidates.empty:
                continue
            candidates_sorted = candidates.sort_values(by=[price_col, ind_col, 'Date'], ascending=[True, True, False])
            best = candidates_sorted.iloc[0]
            records.append({
                'div_date': df.loc[curr_idx, 'Date'],
                'low1_date': low1_date,
                'price_low1': low1_price,
                'ind_low1': low1_ind,
                'low2_date': best['Date'],
                'price_low2': best[price_col],
                'ind_low2': best[ind_col],
                'indicator': ind_col
            })
        return pd.DataFrame(records)

    dif_div = _find_bottom_div_details_local(df, 'Low', 'MACD_DIF')
    hist_div = _find_bottom_div_details_local(df, 'Low', 'MACD_Histogram')
    all_divs = pd.concat([dif_div, hist_div], ignore_index=True).sort_values('div_date')
    divergence_dates = set(all_divs['div_date']) if not all_divs.empty else set()
    divergence = df['Date'].isin(divergence_dates)
    macd_golden = (df['MACD_DIF'] > df['MACD_Signal']) & (df['MACD_DIF'].shift(1) <= df['MACD_Signal'].shift(1))
    kdj_golden = (df['KDJ_K'] > df['KDJ_D']) & (df['KDJ_K'].shift(1) <= df['KDJ_D'].shift(1))
    gold_cross = macd_golden | kdj_golden
    window_months = 4
    
    divergence_recent = any_within(divergence, window_months)
    gold_cross_recent = any_within(gold_cross, window_months)
    condition = divergence_recent & gold_cross_recent
    
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = condition & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    
    if result_df.empty:
        return pd.DataFrame()

    def months_since_last_event(event_series):
        last_true_idx = None
        months_since = []
        for i, is_event in enumerate(event_series):
            if is_event:
                last_true_idx = i
                months_since.append(0)
            else:
                if last_true_idx is None:
                    months_since.append(np.nan)
                else:
                    months_since.append(i - last_true_idx)
        return months_since

    full_months_div = months_since_last_event(divergence.values)
    full_months_macd = months_since_last_event(macd_golden.values)
    full_months_kdj = months_since_last_event(kdj_golden.values)

    result_df['Months_Since_Divergence'] = result_df.index.map(lambda idx: full_months_div[idx])
    result_df['Months_Since_MACD_Golden'] = result_df.index.map(lambda idx: full_months_macd[idx])
    result_df['Months_Since_KDJ_Golden'] = result_df.index.map(lambda idx: full_months_kdj[idx])

    div_dict = {}
    for _, row in all_divs.iterrows():
        d = row['div_date']
        if d not in div_dict or row['indicator'] == 'MACD_DIF':
            div_dict[d] = row

    result_df['Div_Low1_Date'] = pd.NaT
    result_df['Div_Price_Low1'] = np.nan
    result_df['Div_Ind_Low1'] = np.nan
    result_df['Div_Low2_Date'] = pd.NaT
    result_df['Div_Price_Low2'] = np.nan
    result_df['Div_Ind_Low2'] = np.nan
    result_df['Div_Indicator'] = ''

    date_list = df['Date'].tolist()
    for idx, row in result_df.iterrows():
        current_date = row['Date']
        current_pos = date_list.index(current_date)
        best_div = None
        for offset in range(window_months + 1):
            check_pos = current_pos - offset
            if check_pos < 0:
                continue
            check_date = date_list[check_pos]
            if check_date in div_dict:
                best_div = div_dict[check_date]
                break
        if best_div is not None:
            result_df.loc[idx, 'Div_Low1_Date'] = best_div['low1_date']
            result_df.loc[idx, 'Div_Price_Low1'] = best_div['price_low1']
            result_df.loc[idx, 'Div_Ind_Low1'] = best_div['ind_low1']
            result_df.loc[idx, 'Div_Low2_Date'] = best_div['low2_date']
            result_df.loc[idx, 'Div_Price_Low2'] = best_div['price_low2']
            result_df.loc[idx, 'Div_Ind_Low2'] = best_div['ind_low2']
            result_df.loc[idx, 'Div_Indicator'] = best_div['indicator'].replace('MACD_', '')

    result_df['Has_MACD_Golden'] = result_df['Date'].isin(df.loc[any_within(macd_golden, window_months), 'Date'])
    result_df['Has_KDJ_Golden'] = result_df['Date'].isin(df.loc[any_within(kdj_golden, window_months), 'Date'])
    result_df['Has_Divergence'] = result_df['Date'].isin(df.loc[divergence_recent, 'Date'])

    def build_signal(row):
        parts = []
        if row['Has_MACD_Golden']:
            parts.append('MACD金叉')
        if row['Has_KDJ_Golden']:
            parts.append('KDJ金叉')
        if row['Has_Divergence']:
            parts.append('底背离')
        return '+'.join(parts) if parts else ''

    result_df['Signal_Type'] = result_df.apply(build_signal, axis=1)
    result_df.drop(['Has_MACD_Golden', 'Has_KDJ_Golden', 'Has_Divergence'], axis=1, inplace=True)

    first_row = result_df.iloc[[0]]
    last_row = result_df.iloc[[-1]]
    output_df = pd.concat([first_row, last_row], ignore_index=True)

    desired_cols = ['Date', 'Close', 'Volume', 'EMA5', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram',
                    'KDJ_K', 'KDJ_D', 'VOL_EMA5', 'Signal_Type', 'Div_Indicator',
                    'Div_Low1_Date', 'Div_Price_Low1', 'Div_Ind_Low1',
                    'Div_Low2_Date', 'Div_Price_Low2', 'Div_Ind_Low2',
                    'Months_Since_Divergence', 'Months_Since_MACD_Golden', 'Months_Since_KDJ_Golden']
    available_cols = [c for c in desired_cols if c in output_df.columns]
    return output_df[available_cols]

def query_monthly_divergence3(ticker, start_date, end_date, features_to_show):
    """月线底背离3"""
    df_div2 = query_monthly_divergence2(ticker, start_date, end_date, features_to_show)
    if df_div2.empty:
        valid_dates = set()
    else:
        valid_dates = set(df_div2['Date'].unique())
    
    df = load_data_with_cache(ticker, 'monthly')
    required = ['Low', 'Close', 'Volume', 'EMA5', 'VOL_EMA5', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram', 'KDJ_K', 'KDJ_D']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"月线文件缺少以下列: {missing}")

    def _find_bottom_div_details_local(df, price_col, ind_col, lookback=12, tolerance=1.2, max_gap_days=730):
        records = []
        for i in range(lookback, len(df)):
            window = df.iloc[i-lookback:i+1]
            curr_idx = window.index[-1]
            low1_idx = window[price_col].idxmin()
            low1_price = window.loc[low1_idx, price_col]
            low1_ind = window.loc[low1_idx, ind_col]
            low1_date = df.loc[low1_idx, 'Date']
            if window.loc[curr_idx, 'Close'] > low1_price * tolerance:
                continue
            start_date = low1_date - pd.Timedelta(days=max_gap_days)
            prev_data = df.iloc[:low1_idx]
            prev_data = prev_data[prev_data['Date'] >= start_date]
            if len(prev_data) < 3:
                continue
            candidates = prev_data[(prev_data[price_col] > low1_price) & (prev_data[ind_col] < low1_ind)]
            if candidates.empty:
                continue
            candidates_sorted = candidates.sort_values(by=[price_col, ind_col, 'Date'], ascending=[True, True, False])
            best = candidates_sorted.iloc[0]
            records.append({
                'div_date': df.loc[curr_idx, 'Date'],
                'low1_date': low1_date,
                'price_low1': low1_price,
                'ind_low1': low1_ind,
                'low2_date': best['Date'],
                'price_low2': best[price_col],
                'ind_low2': best[ind_col],
                'indicator': ind_col
            })
        return pd.DataFrame(records)

    dif_div = _find_bottom_div_details_local(df, 'Low', 'MACD_DIF')
    hist_div = _find_bottom_div_details_local(df, 'Low', 'MACD_Histogram')
    all_divs = pd.concat([dif_div, hist_div], ignore_index=True).sort_values('div_date')
    divergence_dates = set(all_divs['div_date']) if not all_divs.empty else set()
    divergence = df['Date'].isin(divergence_dates)

    macd_golden = (df['MACD_DIF'] > df['MACD_Signal']) & (df['MACD_DIF'].shift(1) <= df['MACD_Signal'].shift(1))
    kdj_golden = (df['KDJ_K'] > df['KDJ_D']) & (df['KDJ_K'].shift(1) <= df['KDJ_D'].shift(1))

    condition_div2 = df['Date'].isin(valid_dates)
    above_ma5 = df['Close'] > df['EMA5']
    volume_surge = df['Volume'] >= (df['VOL_EMA5'] * 1.3)

    full_condition = condition_div2 & above_ma5 & volume_surge
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = full_condition & date_mask

    result_df = df.loc[final_mask].copy()
    if result_df.empty:
        return pd.DataFrame()

    result_df = result_df.sort_values('Date')
    
    detail_cols = ['Div_Low1_Date', 'Div_Price_Low1', 'Div_Ind_Low1', 'Div_Low2_Date', 'Div_Price_Low2', 'Div_Ind_Low2', 'Div_Indicator']
    if not df_div2.empty and any(col in df_div2.columns for col in detail_cols):
        div_info = df_div2[['Date'] + [c for c in detail_cols if c in df_div2.columns]].drop_duplicates('Date')
        result_df = result_df.merge(div_info, on='Date', how='left')
    else:
        for col in detail_cols:
            result_df[col] = np.nan

    def months_since_last_event(event_series):
        last_true_idx = None
        months_since = []
        for i, is_event in enumerate(event_series):
            if is_event:
                last_true_idx = i
                months_since.append(0)
            else:
                if last_true_idx is None:
                    months_since.append(np.nan)
                else:
                    months_since.append(i - last_true_idx)
        return months_since

    full_months_div = months_since_last_event(divergence.values)
    full_months_macd = months_since_last_event(macd_golden.values)
    full_months_kdj = months_since_last_event(kdj_golden.values)

    result_df['Months_Since_Divergence'] = result_df.index.map(lambda idx: full_months_div[idx])
    result_df['Months_Since_MACD_Golden'] = result_df.index.map(lambda idx: full_months_macd[idx])
    result_df['Months_Since_KDJ_Golden'] = result_df.index.map(lambda idx: full_months_kdj[idx])

    result_df['Signal_Type'] = '底背离+金叉+价上均线+放量'
    output_df = pd.concat([result_df.iloc[[0]], result_df.iloc[[-1]]], ignore_index=True)

    desired_cols = ['Date', 'Close', 'Volume', 'EMA5', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram',
                    'KDJ_K', 'KDJ_D', 'VOL_EMA5', 'Signal_Type', 'Div_Indicator',
                    'Div_Low1_Date', 'Div_Price_Low1', 'Div_Ind_Low1',
                    'Div_Low2_Date', 'Div_Price_Low2', 'Div_Ind_Low2',
                    'Months_Since_Divergence', 'Months_Since_MACD_Golden', 'Months_Since_KDJ_Golden']
    available_cols = [c for c in desired_cols if c in output_df.columns]
    return output_df[available_cols]

def query_weekly_divergence1(ticker, start_date, end_date, features_to_show):
    """周线底背离1"""
    df = load_data_with_cache(ticker, 'weekly')
    needed_cols = ['Date', 'Low', 'Close', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram']
    missing = [c for c in needed_cols if c not in df.columns]
    if missing:
        raise ValueError(f"周线文件缺少以下列: {missing}")

    def _find_bottom_div_details(df, price_col, ind_col, lookback=30, tolerance=1.2, max_gap_days=365):
        records = []
        for i in range(lookback, len(df)):
            window = df.iloc[i-lookback:i+1]
            curr_idx = window.index[-1]
            low1_idx = window[price_col].idxmin()
            low1_price = window.loc[low1_idx, price_col]
            low1_ind = window.loc[low1_idx, ind_col]
            low1_date = df.loc[low1_idx, 'Date']
            if window.loc[curr_idx, 'Close'] > low1_price * tolerance:
                continue
            start_date = low1_date - pd.Timedelta(days=max_gap_days)
            prev_data = df.iloc[:low1_idx]
            prev_data = prev_data[prev_data['Date'] >= start_date]
            if len(prev_data) < 5:
                continue
            candidates = prev_data[(prev_data[price_col] > low1_price) & (prev_data[ind_col] < low1_ind)]
            if candidates.empty:
                continue
            candidates_sorted = candidates.sort_values(by=[price_col, ind_col, 'Date'], ascending=[True, True, False])
            best = candidates_sorted.iloc[0]
            records.append({
                'signal_date': df.loc[curr_idx, 'Date'],
                'low1_date': low1_date,
                'low1_price': low1_price,
                'low1_ind': low1_ind,
                'low2_date': best['Date'],
                'low2_price': best[price_col],
                'low2_ind': best[ind_col],
                'indicator': ind_col.replace('MACD_', '')
            })
        return pd.DataFrame(records)

    dif_divs = _find_bottom_div_details(df, 'Low', 'MACD_DIF')
    hist_divs = _find_bottom_div_details(df, 'Low', 'MACD_Histogram')
    
    all_divs_dict = {}
    for _, row in dif_divs.iterrows():
        key = (row['low1_date'], row['low2_date'])
        all_divs_dict[key] = row.to_dict()
    for _, row in hist_divs.iterrows():
        key = (row['low1_date'], row['low2_date'])
        if key in all_divs_dict:
            existing = all_divs_dict[key]
            existing['indicator'] = '双重'
            existing['hist_low1_ind'] = row['low1_ind']
            existing['hist_low2_ind'] = row['low2_ind']
        else:
            all_divs_dict[key] = row.to_dict()
    
    all_divs = list(all_divs_dict.values())
    if not all_divs:
        return pd.DataFrame()
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    filtered_divs = [d for d in all_divs if start <= d['low1_date'] <= end]
    if not filtered_divs:
        return pd.DataFrame()
    
    rows = []
    for d in filtered_divs:
        row = {
            'Date': d['low1_date'],
            'Close': d['low1_price'],
            'Div_Type': d['indicator'],
            'Div_Low1_Date': d['low1_date'],
            'Div_Price_Low1': d['low1_price'],
            'Div_Ind_Low1': d['low1_ind'],
            'Div_Low2_Date': d['low2_date'],
            'Div_Price_Low2': d['low2_price'],
            'Div_Ind_Low2': d['low2_ind'],
        }
        if d['indicator'] == '双重':
            row['Hist_Low1_Ind'] = d['hist_low1_ind']
            row['Hist_Low2_Ind'] = d['hist_low2_ind']
        elif d['indicator'] == 'Histogram':
            row['Hist_Low1_Ind'] = d['low1_ind']
            row['Hist_Low2_Ind'] = d['low2_ind']
        else:
            hist1 = df.loc[df['Date'] == d['low1_date'], 'MACD_Histogram'].values
            hist2 = df.loc[df['Date'] == d['low2_date'], 'MACD_Histogram'].values
            if len(hist1) and len(hist2):
                row['Hist_Low1_Ind'] = hist1[0]
                row['Hist_Low2_Ind'] = hist2[0]
        rows.append(row)
    
    output_df = pd.DataFrame(rows).sort_values('Date').reset_index(drop=True)
    return output_df

def query_weekly_divergence2(ticker, start_date, end_date, features_to_show):
    """周线底背离2"""
    df = load_data_with_cache(ticker, 'weekly')
    needed_cols = ['Date', 'Low', 'Close', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram', 'KDJ_K', 'KDJ_D', 'Volume', 'EMA5', 'VOL_EMA5']
    missing = [c for c in needed_cols if c not in df.columns]
    if missing:
        raise ValueError(f"周线文件缺少以下列: {missing}")

    def _find_bottom_div_details_local(df, price_col, ind_col, lookback=30, tolerance=1.2, max_gap_days=365):
        records = []
        for i in range(lookback, len(df)):
            window = df.iloc[i-lookback:i+1]
            curr_idx = window.index[-1]
            low1_idx = window[price_col].idxmin()
            low1_price = window.loc[low1_idx, price_col]
            low1_ind = window.loc[low1_idx, ind_col]
            low1_date = df.loc[low1_idx, 'Date']
            if window.loc[curr_idx, 'Close'] > low1_price * tolerance:
                continue
            start_date = low1_date - pd.Timedelta(days=max_gap_days)
            prev_data = df.iloc[:low1_idx]
            prev_data = prev_data[prev_data['Date'] >= start_date]
            if len(prev_data) < 5:
                continue
            candidates = prev_data[(prev_data[price_col] > low1_price) & (prev_data[ind_col] < low1_ind)]
            if candidates.empty:
                continue
            candidates_sorted = candidates.sort_values(by=[price_col, ind_col, 'Date'], ascending=[True, True, False])
            best = candidates_sorted.iloc[0]
            records.append({
                'div_date': df.loc[curr_idx, 'Date'],
                'low1_date': low1_date,
                'price_low1': low1_price,
                'ind_low1': low1_ind,
                'low2_date': best['Date'],
                'price_low2': best[price_col],
                'ind_low2': best[ind_col],
                'indicator': ind_col
            })
        return pd.DataFrame(records)

    dif_div = _find_bottom_div_details_local(df, 'Low', 'MACD_DIF')
    hist_div = _find_bottom_div_details_local(df, 'Low', 'MACD_Histogram')
    all_divs = pd.concat([dif_div, hist_div], ignore_index=True).sort_values('div_date')
    divergence_dates = set(all_divs['div_date']) if not all_divs.empty else set()
    divergence = df['Date'].isin(divergence_dates)
    macd_golden = (df['MACD_DIF'] > df['MACD_Signal']) & (df['MACD_DIF'].shift(1) <= df['MACD_Signal'].shift(1))
    kdj_golden = (df['KDJ_K'] > df['KDJ_D']) & (df['KDJ_K'].shift(1) <= df['KDJ_D'].shift(1))
    gold_cross = macd_golden | kdj_golden
    window_weeks = 4
    
    divergence_recent = any_within(divergence, window_weeks)
    gold_cross_recent = any_within(gold_cross, window_weeks)
    condition = divergence_recent & gold_cross_recent
    
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = condition & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    
    if result_df.empty:
        return pd.DataFrame()

    def weeks_since_last_event(event_series):
        last_true_idx = None
        weeks_since = []
        for i, is_event in enumerate(event_series):
            if is_event:
                last_true_idx = i
                weeks_since.append(0)
            else:
                if last_true_idx is None:
                    weeks_since.append(np.nan)
                else:
                    weeks_since.append(i - last_true_idx)
        return weeks_since

    full_weeks_div = weeks_since_last_event(divergence.values)
    full_weeks_macd = weeks_since_last_event(macd_golden.values)
    full_weeks_kdj = weeks_since_last_event(kdj_golden.values)

    result_df['Weeks_Since_Divergence'] = result_df.index.map(lambda idx: full_weeks_div[idx])
    result_df['Weeks_Since_MACD_Golden'] = result_df.index.map(lambda idx: full_weeks_macd[idx])
    result_df['Weeks_Since_KDJ_Golden'] = result_df.index.map(lambda idx: full_weeks_kdj[idx])

    div_dict = {}
    for _, row in all_divs.iterrows():
        d = row['div_date']
        if d not in div_dict or row['indicator'] == 'MACD_DIF':
            div_dict[d] = row

    result_df['Div_Low1_Date'] = pd.NaT
    result_df['Div_Price_Low1'] = np.nan
    result_df['Div_Ind_Low1'] = np.nan
    result_df['Div_Low2_Date'] = pd.NaT
    result_df['Div_Price_Low2'] = np.nan
    result_df['Div_Ind_Low2'] = np.nan
    result_df['Div_Indicator'] = ''

    date_list = df['Date'].tolist()
    for idx, row in result_df.iterrows():
        current_date = row['Date']
        current_pos = date_list.index(current_date)
        best_div = None
        for offset in range(window_weeks + 1):
            check_pos = current_pos - offset
            if check_pos < 0:
                continue
            check_date = date_list[check_pos]
            if check_date in div_dict:
                best_div = div_dict[check_date]
                break
        if best_div is not None:
            result_df.loc[idx, 'Div_Low1_Date'] = best_div['low1_date']
            result_df.loc[idx, 'Div_Price_Low1'] = best_div['price_low1']
            result_df.loc[idx, 'Div_Ind_Low1'] = best_div['ind_low1']
            result_df.loc[idx, 'Div_Low2_Date'] = best_div['low2_date']
            result_df.loc[idx, 'Div_Price_Low2'] = best_div['price_low2']
            result_df.loc[idx, 'Div_Ind_Low2'] = best_div['ind_low2']
            result_df.loc[idx, 'Div_Indicator'] = best_div['indicator'].replace('MACD_', '')

    result_df['Has_MACD_Golden'] = result_df['Date'].isin(df.loc[any_within(macd_golden, window_weeks), 'Date'])
    result_df['Has_KDJ_Golden'] = result_df['Date'].isin(df.loc[any_within(kdj_golden, window_weeks), 'Date'])
    result_df['Has_Divergence'] = result_df['Date'].isin(df.loc[divergence_recent, 'Date'])

    def build_signal(row):
        parts = []
        if row['Has_MACD_Golden']:
            parts.append('MACD金叉')
        if row['Has_KDJ_Golden']:
            parts.append('KDJ金叉')
        if row['Has_Divergence']:
            parts.append('底背离')
        return '+'.join(parts) if parts else ''

    result_df['Signal_Type'] = result_df.apply(build_signal, axis=1)
    result_df.drop(['Has_MACD_Golden', 'Has_KDJ_Golden', 'Has_Divergence'], axis=1, inplace=True)

    first_row = result_df.iloc[[0]]
    last_row = result_df.iloc[[-1]]
    output_df = pd.concat([first_row, last_row], ignore_index=True)

    desired_cols = ['Date', 'Close', 'Volume', 'EMA5', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram',
                    'KDJ_K', 'KDJ_D', 'VOL_EMA5', 'Signal_Type', 'Div_Indicator',
                    'Div_Low1_Date', 'Div_Price_Low1', 'Div_Ind_Low1',
                    'Div_Low2_Date', 'Div_Price_Low2', 'Div_Ind_Low2',
                    'Weeks_Since_Divergence', 'Weeks_Since_MACD_Golden', 'Weeks_Since_KDJ_Golden']
    available_cols = [c for c in desired_cols if c in output_df.columns]
    return output_df[available_cols]

def query_weekly_divergence3(ticker, start_date, end_date, features_to_show):
    """周线底背离3"""
    df_div2 = query_weekly_divergence2(ticker, start_date, end_date, features_to_show)
    if df_div2.empty:
        valid_dates = set()
    else:
        valid_dates = set(df_div2['Date'].unique())
    
    df = load_data_with_cache(ticker, 'weekly')
    required = ['Low', 'Close', 'Volume', 'EMA5', 'VOL_EMA5', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram', 'KDJ_K', 'KDJ_D']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"周线文件缺少以下列: {missing}")

    def _find_bottom_div_details_local(df, price_col, ind_col, lookback=30, tolerance=1.2, max_gap_days=365):
        records = []
        for i in range(lookback, len(df)):
            window = df.iloc[i-lookback:i+1]
            curr_idx = window.index[-1]
            low1_idx = window[price_col].idxmin()
            low1_price = window.loc[low1_idx, price_col]
            low1_ind = window.loc[low1_idx, ind_col]
            low1_date = df.loc[low1_idx, 'Date']
            if window.loc[curr_idx, 'Close'] > low1_price * tolerance:
                continue
            start_date = low1_date - pd.Timedelta(days=max_gap_days)
            prev_data = df.iloc[:low1_idx]
            prev_data = prev_data[prev_data['Date'] >= start_date]
            if len(prev_data) < 5:
                continue
            candidates = prev_data[(prev_data[price_col] > low1_price) & (prev_data[ind_col] < low1_ind)]
            if candidates.empty:
                continue
            candidates_sorted = candidates.sort_values(by=[price_col, ind_col, 'Date'], ascending=[True, True, False])
            best = candidates_sorted.iloc[0]
            records.append({
                'div_date': df.loc[curr_idx, 'Date'],
                'low1_date': low1_date,
                'price_low1': low1_price,
                'ind_low1': low1_ind,
                'low2_date': best['Date'],
                'price_low2': best[price_col],
                'ind_low2': best[ind_col],
                'indicator': ind_col
            })
        return pd.DataFrame(records)

    dif_div = _find_bottom_div_details_local(df, 'Low', 'MACD_DIF')
    hist_div = _find_bottom_div_details_local(df, 'Low', 'MACD_Histogram')
    all_divs = pd.concat([dif_div, hist_div], ignore_index=True).sort_values('div_date')
    divergence_dates = set(all_divs['div_date']) if not all_divs.empty else set()
    divergence = df['Date'].isin(divergence_dates)

    macd_golden = (df['MACD_DIF'] > df['MACD_Signal']) & (df['MACD_DIF'].shift(1) <= df['MACD_Signal'].shift(1))
    kdj_golden = (df['KDJ_K'] > df['KDJ_D']) & (df['KDJ_K'].shift(1) <= df['KDJ_D'].shift(1))

    condition_div2 = df['Date'].isin(valid_dates)
    above_ma5 = df['Close'] > df['EMA5']
    volume_surge = df['Volume'] >= (df['VOL_EMA5'] * 1.3)

    full_condition = condition_div2 & above_ma5 & volume_surge
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = full_condition & date_mask

    result_df = df.loc[final_mask].copy()
    if result_df.empty:
        return pd.DataFrame()

    result_df = result_df.sort_values('Date')
    
    detail_cols = ['Div_Low1_Date', 'Div_Price_Low1', 'Div_Ind_Low1', 'Div_Low2_Date', 'Div_Price_Low2', 'Div_Ind_Low2', 'Div_Indicator']
    if not df_div2.empty and any(col in df_div2.columns for col in detail_cols):
        div_info = df_div2[['Date'] + [c for c in detail_cols if c in df_div2.columns]].drop_duplicates('Date')
        result_df = result_df.merge(div_info, on='Date', how='left')
    else:
        for col in detail_cols:
            result_df[col] = np.nan

    def weeks_since_last_event(event_series):
        last_true_idx = None
        weeks_since = []
        for i, is_event in enumerate(event_series):
            if is_event:
                last_true_idx = i
                weeks_since.append(0)
            else:
                if last_true_idx is None:
                    weeks_since.append(np.nan)
                else:
                    weeks_since.append(i - last_true_idx)
        return weeks_since

    full_weeks_div = weeks_since_last_event(divergence.values)
    full_weeks_macd = weeks_since_last_event(macd_golden.values)
    full_weeks_kdj = weeks_since_last_event(kdj_golden.values)

    result_df['Weeks_Since_Divergence'] = result_df.index.map(lambda idx: full_weeks_div[idx])
    result_df['Weeks_Since_MACD_Golden'] = result_df.index.map(lambda idx: full_weeks_macd[idx])
    result_df['Weeks_Since_KDJ_Golden'] = result_df.index.map(lambda idx: full_weeks_kdj[idx])

    result_df['Signal_Type'] = '底背离+金叉+价上均线+放量'
    output_df = pd.concat([result_df.iloc[[0]], result_df.iloc[[-1]]], ignore_index=True)

    desired_cols = ['Date', 'Close', 'Volume', 'EMA5', 'MACD_DIF', 'MACD_Signal', 'MACD_Histogram',
                    'KDJ_K', 'KDJ_D', 'VOL_EMA5', 'Signal_Type', 'Div_Indicator',
                    'Div_Low1_Date', 'Div_Price_Low1', 'Div_Ind_Low1',
                    'Div_Low2_Date', 'Div_Price_Low2', 'Div_Ind_Low2',
                    'Weeks_Since_Divergence', 'Weeks_Since_MACD_Golden', 'Weeks_Since_KDJ_Golden']
    available_cols = [c for c in desired_cols if c in output_df.columns]
    return output_df[available_cols]

def query_one_yang_through_five_lines(ticker, start_date, end_date, features_to_show):
    """一阳穿五线"""
    df = load_data_with_cache(ticker, 'daily')
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'EMA5', 'EMA10', 'EMA20', 'EMA50', 'EMA60',
                     'MACD_DIF', 'MACD_Signal', 'MACD_Histogram', 'volume_ratio']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"日线文件缺少 {missing} 列")
    
    df['vol_ema5'] = df['Volume'].rolling(5, min_periods=1).mean()
    df['Body'] = (df['Close'] - df['Open']).abs()
    df['UpperShadow'] = df['High'] - df[['Open', 'Close']].max(axis=1)

    cond1 = (df['Close'] > df['Open']) & (df['Close'] / df['Open'] - 1 >= 0.025) & (df['UpperShadow'] / df['Body'] < 0.3)
    cond2 = (df['Close'] > df['EMA5']) & (df['Close'] > df['EMA10']) & (df['Close'] > df['EMA20']) & (df['Close'] > df['EMA50']) & (df['Close'] > df['EMA60'])
    ma_cols = ['EMA5', 'EMA10', 'EMA20', 'EMA50', 'EMA60']
    df['MA_Max'] = df[ma_cols].max(axis=1)
    df['MA_Min'] = df[ma_cols].min(axis=1)
    df['MA_Spread_Ratio'] = (df['MA_Max'] - df['MA_Min']) / df['Close']
    sticky = df['MA_Spread_Ratio'] < 0.03
    cond3 = any_within(sticky, 5)
    cond4 = df['Volume'] > (df['vol_ema5'] * 1.2)
    macd_golden = (df['MACD_DIF'] > df['MACD_Signal']) & (df['MACD_DIF'].shift(1) <= df['MACD_Signal'].shift(1))
    near_zero = (df['MACD_DIF'].abs() < 0.05) & (df['MACD_Signal'].abs() < 0.05)
    hist_up = df['MACD_Histogram'] > df['MACD_Histogram'].shift(1)
    cond5 = macd_golden & near_zero | hist_up
    final_condition = cond1 & cond2 & cond3 & cond4 & cond5
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = final_condition & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    
    if result_df.empty:
        return pd.DataFrame()
    result_df['MACD_Golden_Flag'] = result_df.index.isin(df.loc[macd_golden].index)
    result_df['Hist_Up_Flag'] = result_df.index.isin(df.loc[hist_up].index)
    return result_df

def query_double_bottom_breakout(ticker, start_date, end_date, features_to_show, lookback=120, vol_ratio_min=1.5,
                                 right_bottom_tolerance=0.97, debug=True):
    """双重底颈线放量突破"""
    df = load_data_with_cache(ticker, 'daily')
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'volume_ratio', 'VOL_EMA5']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"日线文件缺少以下列: {missing}")
    
    df['Local_Min'] = find_local_extrema(df['Low'], order=5, mode='min')
    df['Left_Bottom_Volume'] = df['Volume'] > df['VOL_EMA5'] * 1.2
    raw_signals = []
    
    for idx in range(lookback, len(df)):
        if not df.loc[idx, 'Local_Min']:
            continue
        right_low = df.loc[idx, 'Low']
        right_date = df.loc[idx, 'Date']
        start = max(0, idx - lookback)
        window = df.iloc[start:idx+1]
        left_candidates = window[window['Local_Min']].index
        best_left = None
        best_left_score = -1
        for left_idx in left_candidates:
            if left_idx >= idx:
                continue
            left_low = df.loc[left_idx, 'Low']
            if right_low < left_low * right_bottom_tolerance:
                continue
            if not df.loc[left_idx, 'Left_Bottom_Volume']:
                continue
            if idx - left_idx < 10:
                continue
            price_score = 1 / (left_low + 0.001)
            distance_score = 1 / (idx - left_idx + 1)
            vol_score = df.loc[left_idx, 'Volume'] / df.loc[left_idx, 'VOL_EMA5']
            total_score = price_score * 0.4 + distance_score * 0.3 + vol_score * 0.3
            if total_score > best_left_score:
                best_left_score = total_score
                best_left = left_idx
        if best_left is None:
            continue
        between = df.iloc[best_left+1:idx]
        if between.empty:
            continue
        neckline = between['Close'].max()
        if pd.isna(neckline):
            continue
        for future in range(idx+1, len(df)):
            close_future = df.loc[future, 'Close']
            vol_ratio = df.loc[future, 'volume_ratio']
            if close_future > neckline and vol_ratio >= vol_ratio_min:
                signal_score = (vol_ratio - vol_ratio_min) + (1 - (right_low / left_low)) * 10
                raw_signals.append({
                    'break_date': df.loc[future, 'Date'],
                    'break_price': close_future,
                    'neckline': neckline,
                    'vol_ratio': vol_ratio,
                    'left_date': df.loc[best_left, 'Date'],
                    'left_price': df.loc[best_left, 'Low'],
                    'right_date': right_date,
                    'right_price': right_low,
                    'score': signal_score
                })
                break
    
    if not raw_signals:
        return pd.DataFrame()
    
    signals_df = pd.DataFrame(raw_signals)
    best_per_day = signals_df.loc[signals_df.groupby('break_date')['score'].idxmax()]
    best_per_day = best_per_day.sort_values('break_date').reset_index(drop=True)
    result_df = best_per_day[['break_date', 'break_price', 'neckline', 'vol_ratio',
                              'left_date', 'left_price', 'right_date', 'right_price']].copy()
    result_df.rename(columns={'break_date': 'Signal_Date', 'break_price': 'Break_Price',
                              'neckline': 'Neckline', 'vol_ratio': 'Volume_Ratio',
                              'left_date': 'Left_Bottom_Date', 'left_price': 'Left_Bottom_Price',
                              'right_date': 'Right_Bottom_Date', 'right_price': 'Right_Bottom_Price'}, inplace=True)
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    result_df = result_df[(result_df['Signal_Date'] >= start_dt) & (result_df['Signal_Date'] <= end_dt)]
    return result_df

def query_head_shoulders_bottom_breakout(ticker, start_date, end_date, features_to_show, lookback=120,
                                         vol_ratio_min=1.5, vol_shrink_ratio=0.7, neckline_tolerance=0.02, debug=True):
    """头肩底颈线放量突破"""
    df = load_data_with_cache(ticker, 'daily')
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'volume_ratio']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"日线文件缺少以下列: {missing}")
    
    if 'VOL_EMA5' not in df.columns:
        df['VOL_EMA5'] = df['Volume'].rolling(5, min_periods=1).mean()
    df['Local_Min'] = find_local_extrema(df['Low'], order=5, mode='min')
    df['Vol_MA20'] = df['Volume'].rolling(20, min_periods=1).mean()
    df['Right_Shoulder_Shrink'] = df['Volume'] < df['Vol_MA20'] * vol_shrink_ratio
    signals = []
    
    for idx in range(lookback, len(df)):
        if not df.loc[idx, 'Local_Min']:
            continue
        head_low = df.loc[idx, 'Low']
        head_date = df.loc[idx, 'Date']
        left_candidates = []
        for left_idx in range(max(0, idx - lookback), idx):
            if not df.loc[left_idx, 'Local_Min']:
                continue
            left_low = df.loc[left_idx, 'Low']
            if left_low > head_low * 0.98:
                between_left_head = df.iloc[left_idx+1:idx]
                if between_left_head.empty:
                    continue
                left_peak = between_left_head['High'].max()
                left_peak_date = between_left_head.loc[between_left_head['High'].idxmax(), 'Date'] if not between_left_head.empty else pd.NaT
                left_candidates.append({
                    'left_idx': left_idx,
                    'left_low': left_low,
                    'left_date': df.loc[left_idx, 'Date'],
                    'left_peak': left_peak,
                    'left_peak_date': left_peak_date
                })
        if not left_candidates:
            continue
        left_candidates.sort(key=lambda x: (x['left_low'], -x['left_peak']), reverse=True)
        best_left = left_candidates[0]
        after_head = df.iloc[idx+1:min(idx+60, len(df))]
        if after_head.empty:
            continue
        head_peak = after_head['High'].max()
        head_peak_idx = after_head['High'].idxmax()
        head_peak_date = df.loc[head_peak_idx, 'Date']
        if pd.isna(best_left['left_peak']) or pd.isna(head_peak):
            continue
        x1 = best_left['left_peak_date'].timestamp()
        y1 = best_left['left_peak']
        x2 = head_peak_date.timestamp()
        y2 = head_peak
        slope = (y2 - y1) / (x2 - x1) if x2 != x1 else 0
        intercept = y1 - slope * x1
        right_shoulder_idx = None
        for r_idx in range(idx+1, min(idx+90, len(df))):
            if df.loc[r_idx, 'Local_Min']:
                if df.loc[r_idx, 'Low'] > head_low * 0.98:
                    if df.loc[r_idx, 'Right_Shoulder_Shrink'] or df.loc[r_idx, 'volume_ratio'] < 0.8:
                        right_shoulder_idx = r_idx
                        break
        if right_shoulder_idx is None:
            continue
        right_low = df.loc[right_shoulder_idx, 'Low']
        right_date = df.loc[right_shoulder_idx, 'Date']
        for future in range(right_shoulder_idx+1, len(df)):
            close_future = df.loc[future, 'Close']
            vol_ratio = df.loc[future, 'volume_ratio']
            x_future = df.loc[future, 'Date'].timestamp()
            neckline_price = slope * x_future + intercept
            if close_future > neckline_price * (1 - neckline_tolerance) and vol_ratio >= vol_ratio_min:
                signals.append({
                    'break_date': df.loc[future, 'Date'],
                    'break_price': close_future,
                    'neckline': neckline_price,
                    'vol_ratio': vol_ratio,
                    'left_date': best_left['left_date'],
                    'left_price': best_left['left_low'],
                    'left_peak': best_left['left_peak'],
                    'head_date': head_date,
                    'head_price': head_low,
                    'head_peak': head_peak,
                    'right_date': right_date,
                    'right_price': right_low,
                })
                break
    
    if not signals:
        return pd.DataFrame()
    
    result_df = pd.DataFrame(signals)
    result_df = result_df.drop_duplicates(subset='break_date', keep='first')
    result_df = result_df.sort_values('break_date').reset_index(drop=True)
    result_df.rename(columns={'break_date': 'Signal_Date', 'break_price': 'Break_Price',
                              'neckline': 'Neckline', 'vol_ratio': 'Volume_Ratio',
                              'left_date': 'Left_Shoulder_Date', 'left_price': 'Left_Shoulder_Low',
                              'left_peak': 'Left_Shoulder_Peak', 'head_date': 'Head_Date',
                              'head_price': 'Head_Low', 'head_peak': 'Head_Peak',
                              'right_date': 'Right_Shoulder_Date', 'right_price': 'Right_Shoulder_Low'}, inplace=True)
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    result_df = result_df[(result_df['Signal_Date'] >= start_dt) & (result_df['Signal_Date'] <= end_dt)]
    return result_df

def query_21_63_arc_bottom_break(ticker, start_date, end_date, features_to_show):
    """21日与63日均线圆弧底突破"""
    df = load_data_with_cache(ticker, 'daily')
    if 'EMA21' not in df.columns:
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    if 'EMA63' not in df.columns:
        df['EMA63'] = df['Close'].ewm(span=63, adjust=False).mean()
    df['vol_ema5'] = df['Volume'].rolling(5, min_periods=1).mean()
    df['VOL_MIN20'] = df['Volume'].rolling(20, min_periods=1).min()
    df['MA_Spread'] = (df['EMA63'] - df['EMA21']).abs()
    df['MA_Spread_Ratio'] = df['MA_Spread'] / df['Close']
    df['Slope_21'] = df['EMA21'] - df['EMA21'].shift(5)
    df['Slope_63'] = df['EMA63'] - df['EMA63'].shift(5)
    df['Turning_Up'] = (df['Slope_21'] > 0) & (df['Slope_21'].shift(1) <= 0)
    df['Volume_Shrink'] = df['Volume'] <= df['VOL_MIN20'] * 1.2
    df['Volume_WarmUp'] = (df['Volume'] > df['vol_ema5']) & (df['Volume'] <= df['vol_ema5'] * 1.5)
    df['Volume_Surge'] = df['Volume'] > df['vol_ema5'] * 1.5
    golden_cross = (df['EMA21'] > df['EMA63']) & (df['EMA21'].shift(1) <= df['EMA63'].shift(1))
    up_trend = (df['EMA21'] > df['EMA21'].shift(1)) & (df['EMA63'] > df['EMA63'].shift(1))
    spread_widen = (df['EMA21'] - df['EMA63']) > (df['EMA21'].shift(1) - df['EMA63'].shift(1))
    divergence_up = (df['EMA21'] > df['EMA63']) & up_trend & spread_widen
    df['divergence_up'] = divergence_up
    
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    df_period = df[date_mask].copy()
    result_rows = []
    
    for idx, row in df_period.iterrows():
        if not golden_cross.loc[idx]:
            continue
        pre_start = max(0, idx-30)
        pre_window = df.iloc[pre_start:idx]
        if len(pre_window) < 10:
            continue
        early_slope_neg = (pre_window['Slope_21'].iloc[:10] < 0).any()
        late_slope_rise = (pre_window['Slope_21'].iloc[-5:] > pre_window['Slope_21'].iloc[:5].max()).any()
        spread_narrow = (pre_window['MA_Spread_Ratio'].iloc[-5:].mean() < pre_window['MA_Spread_Ratio'].iloc[:5].mean())
        has_shrink = pre_window['Volume_Shrink'].any()
        turning_near = pre_window['Turning_Up'].iloc[-10:].any()
        warmup_near = pre_window['Volume_WarmUp'].iloc[-10:].any()
        if not (early_slope_neg and late_slope_rise and spread_narrow and has_shrink and turning_near and warmup_near):
            continue
        volume_confirm = df.loc[idx, 'Volume_Surge'] or (df.loc[idx, 'Volume'] > df.loc[idx-1, 'Volume'] * 1.3)
        if not volume_confirm:
            continue
        post_end = min(len(df)-1, idx+10)
        post_window = df.iloc[idx:post_end+1]
        if not post_window['divergence_up'].any():
            continue
        confirm_row = post_window[post_window['divergence_up']].iloc[0]
        result_rows.append({
            'Date': row['Date'],
            'Confirm_Date': confirm_row['Date'],
            'Close': row['Close'],
            'Volume': row['Volume'],
            'Volume_Ratio': row['Volume'] / row['vol_ema5'] if row['vol_ema5'] != 0 else np.nan,
            'EMA21': row['EMA21'],
            'EMA63': row['EMA63'],
            'Spread_Ratio': row['MA_Spread_Ratio']
        })
    
    if not result_rows:
        return pd.DataFrame()
    
    result_df = pd.DataFrame(result_rows)
    result_df = result_df.sort_values('Date').reset_index(drop=True)
    return result_df

def query_standing_pole_volume(ticker, start_date, end_date, features_to_show, debug=True):
    """底部立桩量"""
    df = load_data_with_cache(ticker, 'daily')
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'volume_ratio',
                     'EMA5', 'EMA10', 'EMA20', 'EMA60', 'EMA120', 'MACD_DIF', 'MACD_Signal']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"日线文件缺少 {col} 列")
    
    window = 250
    df['High_250d'] = df['Close'].rolling(window, min_periods=1).max()
    df['High_250d_Date'] = df['Close'].rolling(window, min_periods=1).apply(
        lambda x: x.idxmax() if len(x) > 0 else np.nan, raw=False)
    df['High_250d_Date'] = pd.to_datetime(df['High_250d_Date'], errors='coerce')
    df['Drawdown'] = (df['High_250d'] - df['Close']) / df['High_250d']
    cond_drawdown = df['Drawdown'] >= 0.35
    
    df['Slope_60'] = df['EMA60'] - df['EMA60'].shift(5)
    df['Slope_120'] = df['EMA120'] - df['EMA120'].shift(5)
    df['Slope_60_prev'] = df['Slope_60'].shift(5)
    df['Slope_120_prev'] = df['Slope_120'].shift(5)
    down_60 = df['Slope_60'] < 0
    down_120 = df['Slope_120'] < 0
    flatten_60 = (df['Slope_60'] > df['Slope_60_prev']) | (df['Slope_60'] > -0.01)
    flatten_120 = (df['Slope_120'] > df['Slope_120_prev']) | (df['Slope_120'] > -0.01)
    cond_bottom = cond_drawdown & down_60 & down_120 & flatten_60 & flatten_120
    
    cond_vol_ratio = df['volume_ratio'] > 1.5
    df['Pct_Change'] = (df['Close'] - df['Open']) / df['Open']
    cond_big_yang = df['Pct_Change'] >= 0.025
    body = (df['Close'] - df['Open']).abs()
    lower_shadow = df[['Open', 'Close']].min(axis=1) - df['Low']
    upper_shadow = df['High'] - df[['Open', 'Close']].max(axis=1)
    cond_hammer = (lower_shadow > 2 * body) & (upper_shadow < 0.3 * body) & (body > 0)
    cond_candle = cond_big_yang | cond_hammer
    cond_next_vol_gt1 = df['volume_ratio'].shift(-1) > 1.0
    cond_volume = cond_vol_ratio & cond_candle & cond_next_vol_gt1
    
    low_shift1 = df['Low'].shift(-1)
    low_shift2 = df['Low'].shift(-2)
    cond_defense = (low_shift1 >= df['Low']) & (low_shift2 >= df['Low'])
    cond_defense = cond_defense & (~low_shift1.isna()) & (~low_shift2.isna())
    
    cond_above_ema20 = df['Close'] > df['EMA20']
    cond_macd_bull = df['MACD_DIF'] > df['MACD_Signal']
    cond_resonance = cond_above_ema20 & cond_macd_bull
    
    final_condition = cond_bottom & cond_volume & cond_defense & cond_resonance
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = final_condition & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    
    if result_df.empty:
        return pd.DataFrame()
    
    result_df['EMA10_gt_EMA20'] = result_df['EMA10'] > result_df['EMA20']
    result_df['Cond_MACD_Bull'] = result_df['MACD_DIF'] > result_df['MACD_Signal']
    if 'High_250d_Date' in result_df.columns:
        result_df['High_250d_Date_Str'] = result_df['High_250d_Date'].dt.strftime('%Y-%m-%d')
    return result_df

def query_air_refueling(ticker, start_date, end_date, features_to_show, debug=True,
                        wave_gain_min=0.20, wave_gain_max=0.50, retrace_max=0.382,
                        shrink_ratio=0.30, support_ma='EMA20', require_stop_candle=False,
                        launch_pct=0.01, launch_vol_ratio=1.0, require_launch=True,
                        window_days=3, confirm_days=3):
    """空中加油"""
    df = load_data_with_cache(ticker, 'daily')
    for ma in ['EMA5', 'EMA10', 'EMA20', 'EMA60']:
        if ma not in df.columns:
            span = int(ma.replace('EMA', ''))
            df[ma] = df['Close'].ewm(span=span, adjust=False).mean()
    if 'volume_ratio' not in df.columns:
        vol_ema5 = df['Volume'].rolling(5, min_periods=1).mean()
        df['volume_ratio'] = df['Volume'] / vol_ema5
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
    
    df['Local_Min'] = find_local_extrema(df['Low'], order=3, mode='min')
    df['Local_Max'] = find_local_extrema(df['High'], order=3, mode='max')
    
    last_low_idx = (df['Local_Min'].cumsum() > 0).astype(int) * df.index
    last_low_idx = last_low_idx.where(df['Local_Min']).ffill().fillna(-1).astype(int)
    last_high_idx = (df['Local_Max'].cumsum() > 0).astype(int) * df.index
    last_high_idx = last_high_idx.where(df['Local_Max']).ffill().fillna(-1).astype(int)

    def is_stop_candle(row):
        body = abs(row['Close'] - row['Open'])
        lower_shadow = min(row['Open'], row['Close']) - row['Low']
        upper_shadow = row['High'] - max(row['Open'], row['Close'])
        if body < (row['High'] - row['Low']) * 0.1:
            return True
        if lower_shadow >= 2 * body and upper_shadow < body * 0.3:
            return True
        return False

    close = df['Close'].values
    low = df['Low'].values
    high = df['High'].values
    vol = df['Volume'].values
    ema5 = df['EMA5'].values
    ema20 = df['EMA20'].values
    ema60 = df['EMA60'].values
    macd_dif = df['MACD_DIF'].values
    macd_signal = df['MACD_Signal'].values
    vol_ratio = df['volume_ratio'].values
    support_line = df[support_ma].values if support_ma in df.columns else ema20

    n = len(df)
    cond_wave = np.zeros(n, dtype=bool)
    cond_trend = np.zeros(n, dtype=bool)
    cond_retrace = np.zeros(n, dtype=bool)
    cond_shrink = np.zeros(n, dtype=bool)
    cond_support = np.zeros(n, dtype=bool)
    cond_launch = np.zeros(n, dtype=bool)

    for i in range(1, n):
        low_idx = last_low_idx[i]
        high_idx = last_high_idx[i]
        if low_idx == -1 or high_idx == -1 or high_idx <= low_idx:
            continue
        low_price = low[low_idx]
        high_price = high[high_idx]
        wave_gain = (high_price - low_price) / low_price
        if wave_gain_min <= wave_gain <= wave_gain_max:
            cond_wave[i] = True
        after_low = df.iloc[low_idx:high_idx+1]
        above_ma60 = (after_low['Close'] > after_low['EMA60']).any()
        ma_bull = (after_low['EMA5'] > after_low['EMA20']).all() and (after_low['EMA20'] > after_low['EMA60']).all()
        if above_ma60 or ma_bull:
            cond_trend[i] = True
        curr_close = close[i]
        retrace = (high_price - curr_close) / (high_price - low_price) if high_price > low_price else 1.0
        if retrace <= retrace_max:
            cond_retrace[i] = True
        if high_idx + 1 <= i - 1:
            back_vol = vol[high_idx+1:i]
            if len(back_vol) >= 2:
                wave_vol = vol[low_idx:high_idx] if high_idx > low_idx else np.array([])
                if len(wave_vol) >= 3:
                    wave_avg = wave_vol.mean()
                    back_avg = back_vol.mean()
                    if back_avg <= wave_avg * shrink_ratio:
                        cond_shrink[i] = True
        check_idx = i-1 if i>0 else i
        support_ok = (close[check_idx] >= support_line[check_idx]) or (curr_close >= support_line[check_idx])
        if require_stop_candle:
            if not (is_stop_candle(df.iloc[check_idx]) or is_stop_candle(df.iloc[i])):
                support_ok = False
        if support_ok:
            cond_support[i] = True
        if require_launch:
            prev_close = close[i-1] if i>0 else df.iloc[i]['Open']
            pct_change = (curr_close - prev_close) / prev_close
            if (pct_change >= launch_pct) and (vol_ratio[i] >= launch_vol_ratio) and \
               (curr_close > ema5[i]) and (macd_dif[i] > macd_signal[i]):
                cond_launch[i] = True
        else:
            cond_launch[i] = True

    cond_df = pd.DataFrame({
        'wave': cond_wave, 'trend': cond_trend, 'retrace': cond_retrace,
        'shrink': cond_shrink, 'support': cond_support, 'launch': cond_launch
    }, index=df.index)

    rolled = cond_df.rolling(window_days, min_periods=window_days).max()
    all_cond = (rolled['wave'] == 1) & (rolled['trend'] == 1) & (rolled['retrace'] == 1) & \
               (rolled['shrink'] == 1) & (rolled['support'] == 1) & (rolled['launch'] == 1)
    signal_dates = df.loc[all_cond, 'Date']

    result_rows = []
    for sig_date in signal_dates:
        sig_pos = df[df['Date'] == sig_date].index[0]
        sig_row = df.iloc[sig_pos]
        if sig_row['Close'] <= sig_row['Open']:
            continue
        mid_price = (sig_row['Open'] + sig_row['Close']) / 2
        if sig_pos + confirm_days >= n:
            continue
        future_lows = df['Low'].iloc[sig_pos+1 : sig_pos+1+confirm_days]
        if (future_lows < mid_price).any():
            continue
        start = max(0, sig_pos - window_days + 1)
        window_cond = cond_df.iloc[start : sig_pos+1]
        def last_date(col):
            m = window_cond[col] == 1
            if m.any():
                return df.loc[m[m].index[-1], 'Date']
            return pd.NaT
        result_rows.append({
            'Signal_Date': sig_date,
            'Close': sig_row['Close'],
            'volume_ratio': sig_row['volume_ratio'],
            'Last_Wave_Date': last_date('wave'),
            'Last_Trend_Date': last_date('trend'),
            'Last_Retrace_Date': last_date('retrace'),
            'Last_Shrink_Date': last_date('shrink'),
            'Last_Support_Date': last_date('support'),
            'Last_Launch_Date': last_date('launch'),
        })

    if not result_rows:
        return pd.DataFrame()

    result_df = pd.DataFrame(result_rows).sort_values('Signal_Date').reset_index(drop=True)
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    filtered_df = result_df[(result_df['Signal_Date'] >= start_dt) & (result_df['Signal_Date'] <= end_dt)]
    if filtered_df.empty:
        return pd.DataFrame()
    date_cols = ['Signal_Date', 'Last_Wave_Date', 'Last_Trend_Date', 'Last_Retrace_Date',
                 'Last_Shrink_Date', 'Last_Support_Date', 'Last_Launch_Date']
    for col in date_cols:
        if col in filtered_df.columns:
            filtered_df[col] = filtered_df[col].dt.strftime('%Y-%m-%d')
    return filtered_df

def query_golden_fibonacci_retracement(ticker, start_date, end_date, features_to_show):
    """黄金分割回调"""
    df = load_data_with_cache(ticker, 'daily')
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    all_needed = list(set(required_cols + features_to_show))
    try:
        df = df[all_needed].copy()
        if 'EMA3' not in df.columns:
            df['EMA3'] = df['Close'].ewm(span=3, adjust=False).mean()
        for col in ['Close', 'Volume', 'EMA3']:
            if col not in df.columns:
                raise ValueError(f"日线文件缺少 {col} 列")
    except Exception as e:
        raise ValueError(f"读取日线文件失败: {str(e)}")
    
    df['vol_ema5'] = df['Volume'].rolling(5, min_periods=1).mean()
    order_low = 10
    df['Local_Low'] = find_local_extrema(df['Low'], order=order_low, mode='min')
    min_rise_pct = 0.15
    max_band_days = 180
    tolerance = 0.035
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    df_period = df[date_mask].copy()
    result_rows = []
    
    for idx, row in df_period.iterrows():
        current_idx = df.index.get_loc(idx)
        current_date = row['Date']
        high_start = max(0, current_idx - 249)
        high_window = df.iloc[high_start:current_idx+1]
        if high_window.empty:
            continue
        high_idx = high_window['High'].idxmax()
        high_row = df.loc[high_idx]
        high_price, high_date = high_row['High'], high_row['Date']
        low_start = max(0, df.index.get_loc(high_row.name) - max_band_days)
        low_end = df.index.get_loc(high_row.name)
        low_window = df.iloc[low_start:low_end].copy()
        low_candidates = low_window[low_window['Local_Low']]
        found_low = None
        lowest_price = np.inf
        candidate_list = []
        for _, low_row in low_candidates.iterrows():
            rise_pct = (high_price - low_row['Low']) / low_row['Low']
            if rise_pct >= min_rise_pct:
                candidate_list.append((low_row['Date'], low_row['Low'], rise_pct))
                if low_row['Low'] < lowest_price:
                    lowest_price = low_row['Low']
                    found_low = low_row
        if found_low is None:
            continue
        low_price, low_date = found_low['Low'], found_low['Date']
        rise_pct = (high_price - low_price) / low_price
        fib_382 = high_price - (high_price - low_price) * 0.382
        fib_500 = high_price - (high_price - low_price) * 0.500
        close = row['Close']
        dev_382 = abs(close - fib_382) / fib_382
        dev_500 = abs(close - fib_500) / fib_500
        if dev_382 <= tolerance and dev_500 <= tolerance:
            if dev_382 <= dev_500:
                fib_level = fib_382
                retrace_type = '0.382'
            else:
                fib_level = fib_500
                retrace_type = '0.500'
        elif dev_382 <= tolerance:
            fib_level = fib_382
            retrace_type = '0.382'
        elif dev_500 <= tolerance:
            fib_level = fib_500
            retrace_type = '0.500'
        else:
            continue
        volume_surge = row['Volume'] > row['vol_ema5'] * 1.2
        is_yang = row['Close'] > row['Open']
        if not (volume_surge and is_yang):
            continue
        if close < fib_level:
            continue
        start_idx = max(0, current_idx - 2)
        three_day_closes = df.iloc[start_idx:current_idx+1]['Close']
        stand_firm_3 = (three_day_closes >= fib_level).all()
        prev_idx = current_idx - 1
        yang_bao_yin = False
        if prev_idx >= 0:
            prev_row = df.iloc[prev_idx]
            yang_bao_yin = (prev_row['Close'] < prev_row['Open']) and (row['Close'] > prev_row['Open'])
        result_rows.append({
            'Date': row['Date'],
            'Close': row['Close'],
            'Volume': row['Volume'],
            'Volume_Ratio': row['Volume'] / row['vol_ema5'] if row['vol_ema5'] != 0 else np.nan,
            'EMA3': row['EMA3'],
            'Retrace_Type': retrace_type,
            'Fib_382_Price': fib_382,
            'Fib_500_Price': fib_500,
            'Band_Low_Date': low_date,
            'Band_Low_Price': low_price,
            'Band_High_Date': high_date,
            'Band_High_Price': high_price,
            'Yang_Bao_Yin': yang_bao_yin,
            'Stand_3Days': stand_firm_3
        })
    
    if not result_rows:
        return pd.DataFrame()
    result_df = pd.DataFrame(result_rows).sort_values('Date').reset_index(drop=True)
    return result_df

def query_bullish_ma_first_golden_cross(ticker, start_date, end_date, features_to_show, window_days=5, debug=True):
    """均线多头排列首次金叉"""
    df = load_data_with_cache(ticker, 'daily')
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'EMA5', 'EMA10', 'EMA20', 'EMA60',
                     'volume_ratio', 'MACD_DIF', 'MACD_Signal', 'KDJ_K', 'KDJ_D']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"日线文件缺少 {col} 列")
    
    FIRST_CROSS_WINDOW = 10
    VOL_RATIO_MIN = 1.3
    VOL_NEXT_RATIO_MIN = 0.7
    GAIN_FROM_LOW_MAX = 0.25
    STICKY_THRESHOLD = 0.03
    YEARS_BACK = 1

    df['Golden_Cross'] = (df['EMA5'] > df['EMA10']) & (df['EMA5'].shift(1) <= df['EMA10'].shift(1))
    df['Golden_Cross_PrevN'] = df['Golden_Cross'].rolling(FIRST_CROSS_WINDOW, min_periods=1).sum().shift(1).fillna(0)
    cond_first_cross = (df['Golden_Cross']) & (df['Golden_Cross_PrevN'] == 0)
    cond_above_ema20 = (df['EMA5'] > df['EMA20']) & (df['EMA10'] > df['EMA20'])
    cond_close_above_ema20 = df['Close'] > df['EMA20']
    ma_bull_core = (df['EMA5'] > df['EMA10']) & (df['EMA10'] > df['EMA20'])
    ema60_slope = df['EMA60'] - df['EMA60'].shift(5)
    ema60_flat_up = ema60_slope >= 0
    cond_ma_bull = ma_bull_core & ema60_flat_up
    ma_cols = ['EMA5', 'EMA10', 'EMA20']
    df['MA_Max'] = df[ma_cols].max(axis=1)
    df['MA_Min'] = df[ma_cols].min(axis=1)
    df['MA_Spread_Ratio'] = (df['MA_Max'] - df['MA_Min']) / df['Close']
    sticky = df['MA_Spread_Ratio'] < STICKY_THRESHOLD
    cond_sticky = any_within(sticky, 5)
    below_ema20 = (df['EMA5'] < df['EMA20']) | (df['EMA10'] < df['EMA20'])
    cond_below_before = any_within(below_ema20.shift(1), 10)
    ema60_slope_neg_to_flat = (ema60_slope.shift(1) < 0) & (ema60_slope >= 0)
    cond_flat_turn = cond_below_before & ema60_slope_neg_to_flat
    cond_pre_state = cond_sticky | cond_flat_turn
    cond_vol_ratio = df['volume_ratio'] > VOL_RATIO_MIN
    next1 = df['volume_ratio'].shift(-1)
    next2 = df['volume_ratio'].shift(-2)
    cond_vol_next = (next1 > VOL_NEXT_RATIO_MIN) & (next2 > VOL_NEXT_RATIO_MIN)
    cond_vol_next = cond_vol_next | ((next1 > VOL_NEXT_RATIO_MIN) & next2.isna())

    def calc_3y_low_info(current_date):
        three_years_ago = current_date - pd.Timedelta(days=365 * YEARS_BACK)
        mask = (df['Date'] >= three_years_ago) & (df['Date'] <= current_date)
        past_df = df.loc[mask]
        if past_df.empty:
            return np.nan, pd.NaT
        min_idx = past_df['Low'].idxmin()
        return past_df.loc[min_idx, 'Low'], past_df.loc[min_idx, 'Date']

    low_info = df['Date'].apply(calc_3y_low_info)
    df['Low_3Y'] = [info[0] for info in low_info]
    df['Gain_From_3Y_Low'] = (df['Close'] - df['Low_3Y']) / df['Low_3Y']
    cond_low_position = df['Gain_From_3Y_Low'] <= GAIN_FROM_LOW_MAX

    win_first_cross = any_within(cond_first_cross, window_days)
    win_above_ema20 = any_within(cond_above_ema20, window_days)
    win_close_above = any_within(cond_close_above_ema20, window_days)
    win_ma_bull = any_within(cond_ma_bull, window_days)
    win_vol_ratio = any_within(cond_vol_ratio, window_days)
    win_vol_next = any_within(cond_vol_next, window_days)
    win_low_position = any_within(cond_low_position, window_days)

    condition = (win_first_cross & win_above_ema20 & win_close_above & win_ma_bull &
                 win_vol_ratio & win_vol_next & win_low_position)
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = condition & date_mask
    signal_series = pd.Series(final_mask, index=df.index)
    shifted = signal_series.shift(-1)
    window_end_mask = signal_series & (~shifted.where(shifted.notna(), False))
    final_mask = window_end_mask
    result_df = df.loc[final_mask].copy()
    if result_df.empty:
        return pd.DataFrame()
    result_df = result_df.sort_values('Date').reset_index(drop=True)

    def last_occurrence_date(cond_series, date_series):
        last_date = pd.NaT
        result = []
        for cond, dt in zip(cond_series, date_series):
            if cond:
                last_date = dt
            result.append(last_date)
        return pd.Series(result, index=cond_series.index)

    result_df['Last_FirstCross_Date'] = last_occurrence_date(cond_first_cross, df['Date']).loc[result_df.index]
    result_df['Last_AboveEMA20_Date'] = last_occurrence_date(cond_above_ema20, df['Date']).loc[result_df.index]
    result_df['Last_MABull_Date'] = last_occurrence_date(cond_ma_bull, df['Date']).loc[result_df.index]
    result_df['Last_VolRatio_Date'] = last_occurrence_date(cond_vol_ratio, df['Date']).loc[result_df.index]
    result_df['Last_VolNext_Date'] = last_occurrence_date(cond_vol_next, df['Date']).loc[result_df.index]
    result_df['Low_3Y'], result_df['Low_3Y_Date'] = zip(*result_df['Date'].apply(calc_3y_low_info))
    result_df['Gain_From_3Y_Low'] = (result_df['Close'] - result_df['Low_3Y']) / result_df['Low_3Y']
    return result_df

def query_bullish_engulfing(ticker, start_date, end_date, features_to_show, debug=True):
    """看涨吞没形态"""
    df = load_data_with_cache(ticker, 'daily')
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'EMA20', 'volume_ratio']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"日线文件缺少以下列: {missing}")
    
    df['Body'] = (df['Close'] - df['Open']).abs()
    df['Body_MA5'] = df['Body'].rolling(5, min_periods=1).mean().shift(1)
    df['Prev_Open'] = df['Open'].shift(1)
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_Body'] = df['Body'].shift(1)
    df['Prev_Body_MA5'] = df['Body_MA5'].shift(1)
    close_below_ema20 = df['Close'] < df['EMA20']
    df['Below_EMA20_Count'] = close_below_ema20.rolling(10, min_periods=5).sum()
    df['EMA20_Slope'] = df['EMA20'] - df['EMA20'].shift(5)
    cond_trend = (df['Below_EMA20_Count'] >= 6) & (df['EMA20_Slope'] < 0)
    cond_prev_bear = (df['Prev_Close'] < df['Prev_Open']) & (df['Prev_Body'] > df['Prev_Body_MA5'])
    cond_curr_bull = (df['Close'] > df['Open']) & (df['Open'] <= df['Prev_Close']) & (df['Close'] >= df['Prev_Open'])
    cond_vol = df['volume_ratio'] >= 1.0
    final_condition = cond_trend & cond_prev_bear & cond_curr_bull & cond_vol
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = final_condition & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    if result_df.empty:
        return pd.DataFrame()
    result_df['Body_Ratio'] = result_df['Body'] / result_df['Body_MA5']
    return result_df

def query_morning_star(ticker, start_date, end_date, features_to_show, debug=True):
    """启明星形态"""
    df = load_data_with_cache(ticker, 'daily')
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'EMA20', 'volume_ratio',
                     'BodyLength', 'LowerShadow', 'UpperShadow']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"日线文件缺少以下列: {missing}")
    
    df['Prev1_Open'] = df['Open'].shift(1)
    df['Prev1_Close'] = df['Close'].shift(1)
    df['Prev1_High'] = df['High'].shift(1)
    df['Prev1_Low'] = df['Low'].shift(1)
    df['Prev1_BodyLength'] = df['BodyLength'].shift(1)
    df['Prev1_LowerShadow'] = df['LowerShadow'].shift(1)
    df['Prev1_UpperShadow'] = df['UpperShadow'].shift(1)
    df['Prev1_volume_ratio'] = df['volume_ratio'].shift(1)
    df['Prev2_Open'] = df['Open'].shift(2)
    df['Prev2_Close'] = df['Close'].shift(2)
    df['Prev2_High'] = df['High'].shift(2)
    df['Prev2_Low'] = df['Low'].shift(2)
    df['Prev2_BodyLength'] = df['BodyLength'].shift(2)
    df['BodyLength_MA5'] = df['BodyLength'].rolling(5, min_periods=1).mean().shift(1)
    close_below_ema20 = df['Close'] < df['EMA20']
    df['Below_EMA20_Count'] = close_below_ema20.rolling(10, min_periods=5).sum()
    df['EMA20_Slope'] = df['EMA20'] - df['EMA20'].shift(5)
    cond_trend = (df['Below_EMA20_Count'] >= 6) & (df['EMA20_Slope'] < 0)
    cond_day1_bear = (df['Prev2_Close'] < df['Prev2_Open']) & (df['Prev2_BodyLength'] > df['BodyLength_MA5'].shift(2))
    cond_day2_small_body = df['Prev1_BodyLength'] < 0.4 * df['Prev2_BodyLength']
    cond_day2_long_shadow = (df['Prev1_LowerShadow'] > 0.8 * df['Prev1_BodyLength']) | (df['Prev1_UpperShadow'] > 0.8 * df['Prev1_BodyLength'])
    cond_day2_low_vol = df['Prev1_volume_ratio'] < 1.0
    cond_day2_star = cond_day2_small_body & (cond_day2_long_shadow | cond_day2_low_vol)
    cond_day3_bull = (df['Close'] > df['Open']) & (df['BodyLength'] > df['BodyLength_MA5']) & \
                     (df['Close'] > df['Prev2_Open'] - 0.5 * df['Prev2_BodyLength']) & (df['volume_ratio'] > 1.2)
    gap_down = df['Prev1_High'] < df['Prev2_Low']
    gap_up = df['Low'] > df['Prev1_High']
    cond_gap = gap_down | gap_up
    final_condition = cond_trend & cond_day1_bear & cond_day2_star & cond_day3_bull
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = final_condition & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    if result_df.empty:
        return pd.DataFrame()
    result_df['Has_Gap'] = gap_down.loc[result_df.index] | gap_up.loc[result_df.index]
    return result_df

def query_moving_average_golden_cross(ticker, start_date, end_date, features_to_show, debug=True):
    """均线金叉"""
    df = load_data_with_cache(ticker, 'daily')
    required_ema = ['EMA5', 'EMA10', 'EMA20', 'EMA60', 'EMA120']
    missing_ema = [m for m in required_ema if m not in df.columns]
    if missing_ema:
        raise ValueError(f"数据文件缺少以下 EMA 列: {missing_ema}")
    if 'volume_ratio' not in df.columns:
        raise ValueError("数据文件缺少 volume_ratio 列")

    def golden_cross(fast, slow):
        return (fast > slow) & (fast.shift(1) <= slow.shift(1))

    cond_ema5_cross_ema10 = golden_cross(df['EMA5'], df['EMA10'])
    cond_ema5_cross_ema20 = golden_cross(df['EMA5'], df['EMA20'])
    cond_ema10_cross_ema20 = golden_cross(df['EMA10'], df['EMA20'])
    cond_ema20_cross_ema60 = golden_cross(df['EMA20'], df['EMA60'])
    cond_ema60_cross_ema120 = golden_cross(df['EMA60'], df['EMA120'])

    ema_cols = ['EMA5', 'EMA10', 'EMA20']
    df['EMA_Max'] = df[ema_cols].max(axis=1)
    df['EMA_Min'] = df[ema_cols].min(axis=1)
    df['EMA_Spread_Ratio'] = (df['EMA_Max'] - df['EMA_Min']) / df['Close']
    sticky = df['EMA_Spread_Ratio'] < 0.03
    sticky_consecutive = (sticky.rolling(3, min_periods=3).sum() == 3)
    ma_bull_order = (df['EMA5'] > df['EMA10']) & (df['EMA10'] > df['EMA20'])
    ema5_slope = df['EMA5'] - df['EMA5'].shift(3)
    ema10_slope = df['EMA10'] - df['EMA10'].shift(3)
    ema20_slope = df['EMA20'] - df['EMA20'].shift(3)
    ema_slope_up = (ema5_slope > 0) & (ema10_slope > 0) & (ema20_slope > 0)
    today_divergence = ma_bull_order & ema_slope_up
    yesterday_divergence = ma_bull_order.shift(1) & ema_slope_up.shift(1)
    first_divergence = today_divergence & ~yesterday_divergence
    cond_triple_diverge = sticky_consecutive.shift(1) & first_divergence

    signal_types = []
    signal_strengths = []
    signal_durations = []
    for idx in df.index:
        types = []
        strengths = []
        durations = []
        if cond_ema5_cross_ema10.loc[idx]:
            types.append('EMA5金叉EMA10'); strengths.append('⭐⭐'); durations.append('1-3天')
        if cond_ema5_cross_ema20.loc[idx]:
            types.append('EMA5金叉EMA20'); strengths.append('⭐⭐⭐'); durations.append('3-10天')
        if cond_ema10_cross_ema20.loc[idx]:
            types.append('EMA10金叉EMA20'); strengths.append('⭐⭐⭐'); durations.append('5-15天')
        if cond_ema20_cross_ema60.loc[idx]:
            types.append('EMA20金叉EMA60'); strengths.append('⭐⭐⭐⭐'); durations.append('1-3个月')
        if cond_ema60_cross_ema120.loc[idx]:
            types.append('EMA60金叉EMA120'); strengths.append('⭐⭐⭐⭐⭐'); durations.append('3-6个月')
        if cond_triple_diverge.loc[idx]:
            types.append('三线粘合向上发散'); strengths.append('⭐⭐⭐⭐⭐'); durations.append('中长期')
        if types:
            signal_types.append('；'.join(types))
            signal_strengths.append('；'.join(strengths))
            signal_durations.append('；'.join(durations))
        else:
            signal_types.append(''); signal_strengths.append(''); signal_durations.append('')

    df['Signal_Type'] = signal_types
    df['Signal_Strength'] = signal_strengths
    df['Signal_Duration'] = signal_durations

    final_condition = (cond_ema5_cross_ema10 | cond_ema5_cross_ema20 | cond_ema10_cross_ema20 |
                       cond_ema20_cross_ema60 | cond_ema60_cross_ema120 | cond_triple_diverge)
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = final_condition & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date').reset_index(drop=True)
    return result_df

def query_bollinger_oversold_reversal(ticker, start_date, end_date, features_to_show, debug=True):
    """布林下轨超卖+反转K线"""
    df = load_data_with_cache(ticker, 'daily')
    if 'Bollinger_Lower' not in df.columns:
        window = 20
        std = df['Close'].rolling(window).std()
        df['Bollinger_Middle'] = df['Close'].rolling(window).mean()
        df['Bollinger_Upper'] = df['Bollinger_Middle'] + 2 * std
        df['Bollinger_Lower'] = df['Bollinger_Middle'] - 2 * std
    if 'MACD_Histogram' not in df.columns:
        df['MACD_Histogram'] = 0.0
    if 'KDJ_K' not in df.columns:
        df['KDJ_K'] = 50.0
        df['KDJ_D'] = 50.0
    if 'RSI14' not in df.columns:
        df['RSI14'] = 50.0
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Bollinger_Lower',
                     'MACD_Histogram', 'KDJ_K', 'KDJ_D', 'RSI14']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"文件缺少以下列: {missing}")

    def is_hammer(row):
        body = abs(row['Close'] - row['Open'])
        if body == 0:
            return False
        lower_shadow = min(row['Open'], row['Close']) - row['Low']
        upper_shadow = row['High'] - max(row['Open'], row['Close'])
        return lower_shadow >= 2 * body and upper_shadow < 0.3 * body

    def is_inverted_hammer(row):
        body = abs(row['Close'] - row['Open'])
        if body == 0:
            return False
        upper_shadow = row['High'] - max(row['Open'], row['Close'])
        lower_shadow = min(row['Open'], row['Close']) - row['Low']
        return upper_shadow >= 2 * body and lower_shadow < 0.3 * body

    def is_doji(row):
        high_low = row['High'] - row['Low']
        if high_low == 0:
            return False
        body = abs(row['Close'] - row['Open'])
        return body / high_low < 0.1

    def is_bullish_engulfing(df, idx):
        if idx == 0:
            return False
        prev = df.iloc[idx-1]
        curr = df.iloc[idx]
        prev_bear = prev['Close'] < prev['Open']
        curr_bull = curr['Close'] > curr['Open']
        if not (prev_bear and curr_bull):
            return False
        return curr['Open'] <= prev['Close'] and curr['Close'] >= prev['Open']

    def is_morning_star(df, idx):
        if idx < 2:
            return False
        day1 = df.iloc[idx-2]
        day2 = df.iloc[idx-1]
        day3 = df.iloc[idx]
        body1 = abs(day1['Close'] - day1['Open'])
        body_ma5 = abs(df['Close'] - df['Open']).rolling(5, min_periods=1).mean().shift(1).iloc[idx]
        if pd.isna(body_ma5):
            return False
        cond1 = day1['Close'] < day1['Open'] and body1 > body_ma5
        body2 = abs(day2['Close'] - day2['Open'])
        cond2 = body2 < 0.4 * body1
        cond3 = day3['Close'] > day3['Open'] and day3['Close'] > day1['Open'] - 0.5 * body1
        return cond1 and cond2 and cond3

    def get_reversal_pattern(df, idx):
        row = df.iloc[idx]
        if is_hammer(row):
            return "锤子线", True
        if is_inverted_hammer(row):
            return "倒锤子线", True
        if is_doji(row):
            return "十字星", True
        if is_bullish_engulfing(df, idx):
            return "看涨吞没", True
        if is_morning_star(df, idx):
            return "启明星", True
        return "", False

    result_rows = []
    for i in range(len(df)):
        close_today = df.loc[i, 'Close']
        lower = df.loc[i, 'Bollinger_Lower']
        pos_confirmed_today = close_today <= lower * 1.02
        if pos_confirmed_today:
            pattern, is_reversal = get_reversal_pattern(df, i)
            if is_reversal:
                close_above_lower = df.loc[i, 'Close'] >= lower * 0.98
                vol_surge = df.loc[i, 'Volume'] > df.loc[i-1, 'Volume'] if i > 0 else False
                hist = df.loc[i, 'MACD_Histogram']
                hist_prev = df.loc[i-1, 'MACD_Histogram'] if i > 0 else hist
                macd_green_shrink = hist > hist_prev and hist_prev < 0
                kdj_k = df.loc[i, 'KDJ_K']
                kdj_d = df.loc[i, 'KDJ_D']
                kdj_golden = (kdj_k < 20) and (kdj_k > kdj_d) and (df.loc[i-1, 'KDJ_K'] <= df.loc[i-1, 'KDJ_D'] if i > 0 else False)
                rsi = df.loc[i, 'RSI14']
                rsi_turn_up = (rsi < 30) and (rsi > df.loc[i-1, 'RSI14'] if i > 0 else False)
                resonance = macd_green_shrink and kdj_golden and rsi_turn_up
                if close_above_lower and vol_surge and resonance:
                    result_rows.append({
                        'Signal_Date': df.loc[i, 'Date'],
                        'Close': df.loc[i, 'Close'],
                        'Bollinger_Lower': lower,
                        'Reversal_Pattern': pattern,
                        'Volume_Ratio': df.loc[i, 'Volume'] / df.loc[i-1, 'Volume'] if i > 0 else 1.0,
                        'MACD_Histogram': hist,
                        'KDJ_K': kdj_k,
                        'RSI14': rsi,
                        'Signal_Source': '当日反转'
                    })
                    continue
        if i > 0:
            prev_close = df.loc[i-1, 'Close']
            prev_lower = df.loc[i-1, 'Bollinger_Lower']
            pos_confirmed_prev = prev_close <= prev_lower * 1.02
            if pos_confirmed_prev:
                pattern, is_reversal = get_reversal_pattern(df, i)
                if is_reversal:
                    close_above_lower = df.loc[i, 'Close'] >= prev_lower * 0.98
                    vol_surge = df.loc[i, 'Volume'] > df.loc[i-1, 'Volume']
                    hist = df.loc[i, 'MACD_Histogram']
                    hist_prev = df.loc[i-1, 'MACD_Histogram']
                    macd_green_shrink = hist > hist_prev and hist_prev < 0
                    kdj_k = df.loc[i, 'KDJ_K']
                    kdj_d = df.loc[i, 'KDJ_D']
                    kdj_golden = (kdj_k < 20) and (kdj_k > kdj_d) and (df.loc[i-1, 'KDJ_K'] <= df.loc[i-1, 'KDJ_D'])
                    rsi = df.loc[i, 'RSI14']
                    rsi_turn_up = (rsi < 30) and (rsi > df.loc[i-1, 'RSI14'])
                    resonance = macd_green_shrink and kdj_golden and rsi_turn_up
                    if close_above_lower and vol_surge and resonance:
                        result_rows.append({
                            'Signal_Date': df.loc[i, 'Date'],
                            'Close': df.loc[i, 'Close'],
                            'Bollinger_Lower': prev_lower,
                            'Reversal_Pattern': pattern,
                            'Volume_Ratio': df.loc[i, 'Volume'] / df.loc[i-1, 'Volume'],
                            'MACD_Histogram': hist,
                            'KDJ_K': kdj_k,
                            'RSI14': rsi,
                            'Signal_Source': '次日反转'
                        })
    
    if not result_rows:
        return pd.DataFrame()
    
    result_df = pd.DataFrame(result_rows).sort_values('Signal_Date').reset_index(drop=True)
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    result_df = result_df[(result_df['Signal_Date'] >= start_dt) & (result_df['Signal_Date'] <= end_dt)]
    return result_df

def query_kdj_low_golden_cross(ticker, start_date, end_date, features_to_show, debug=True):
    """KDJ低位金叉"""
    df = load_data_with_cache(ticker, 'daily')
    if 'KDJ_K' not in df.columns or 'KDJ_D' not in df.columns:
        low_min = df['Low'].rolling(9, min_periods=1).min()
        high_max = df['High'].rolling(9, min_periods=1).max()
        rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
        rsv = rsv.fillna(50)
        df['KDJ_K'] = rsv.ewm(alpha=1/3, adjust=False).mean()
        df['KDJ_D'] = df['KDJ_K'].ewm(alpha=1/3, adjust=False).mean()
        df['KDJ_J'] = 3 * df['KDJ_K'] - 2 * df['KDJ_D']
    
    k_up_cross_d = (df['KDJ_K'] > df['KDJ_D']) & (df['KDJ_K'].shift(1) <= df['KDJ_D'].shift(1))
    death = (df['KDJ_K'] < df['KDJ_D']) & (df['KDJ_K'].shift(1) >= df['KDJ_D'].shift(1))
    cond_single = (df['KDJ_K'] < 20) & (df['KDJ_D'] < 20) & k_up_cross_d
    cond_second = pd.Series(False, index=df.index)
    lookback = 20
    for i in range(1, len(df)):
        if cond_single.iloc[i]:
            continue
        start = max(0, i - lookback)
        window_gold = k_up_cross_d.iloc[start:i]
        gold_positions = window_gold[window_gold].index
        if len(gold_positions) == 0:
            continue
        last_gold_pos = gold_positions[-1]
        if not death.iloc[last_gold_pos:i].any():
            continue
        if df.loc[i, 'KDJ_K'] >= 30 or df.loc[i, 'KDJ_D'] >= 30:
            continue
        low_k_after_gold = df.loc[last_gold_pos:i, 'KDJ_K'].min()
        k_at_gold = df.loc[last_gold_pos, 'KDJ_K']
        if low_k_after_gold >= k_at_gold - 5:
            cond_second.iloc[i] = True
    
    n = 20
    df['Low_N'] = df['Low'].rolling(n, min_periods=1).min()
    k_at_low = df['KDJ_K'].where(df['Low'] == df['Low_N'], np.nan)
    df['K_at_Low'] = k_at_low.ffill()
    price_lower = df['Low'] < df['Low_N'].shift(1)
    k_higher = df['KDJ_K'] > df['K_at_Low'].shift(1)
    cond_divergence = price_lower & k_higher & k_up_cross_d
    
    j_below_neg10 = df['KDJ_J'] < -10
    j_rise_cross0 = (df['KDJ_J'] > 0) & (df['KDJ_J'].shift(1) <= 0)
    cond_j_lead = pd.Series(False, index=df.index)
    for i in range(len(df)):
        if j_rise_cross0.iloc[i]:
            for j in range(1, 4):
                if i + j >= len(df):
                    break
                if k_up_cross_d.iloc[i + j]:
                    cond_j_lead.iloc[i + j] = True
                    break
    
    final_condition = cond_single | cond_second | cond_divergence | cond_j_lead
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = final_condition & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    result_df['Golden_Type'] = ''
    for idx in result_df.index:
        if cond_single.loc[idx]:
            result_df.loc[idx, 'Golden_Type'] = '低位一次金叉'
        elif cond_second.loc[idx]:
            result_df.loc[idx, 'Golden_Type'] = '低位二次金叉'
        elif cond_divergence.loc[idx]:
            result_df.loc[idx, 'Golden_Type'] = '底背离金叉'
        elif cond_j_lead.loc[idx]:
            result_df.loc[idx, 'Golden_Type'] = 'J值领先金叉'
    if result_df.empty:
        return pd.DataFrame()
    return result_df

def query_rsi_oversold_turn(ticker, start_date, end_date, features_to_show, debug=True):
    """RSI超卖区拐头"""
    df = load_data_with_cache(ticker, 'daily')
    if 'volume_ratio' not in df.columns:
        vol_ema5 = df['Volume'].rolling(5, min_periods=1).mean()
        df['volume_ratio'] = df['Volume'] / vol_ema5
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
    if 'RSI14' not in df.columns:
        delta = df['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['RSI14'] = 100 - (100 / (1 + rs))
        df['RSI14'] = df['RSI14'].fillna(50)
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'volume_ratio', 'RSI14']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"日线文件缺少以下列: {missing}")
    
    df['RSI_Local_Min'] = find_local_extrema(df['RSI14'], order=5, mode='min')
    rsi_below30 = df['RSI14'] < 30
    rsi_above30 = df['RSI14'] >= 30
    rsi_rise_cross30 = rsi_above30 & rsi_below30.shift(1)
    rsi_min5 = df['RSI14'].rolling(5, min_periods=1).min()
    cond_v = rsi_rise_cross30 & (rsi_min5 < 30) & ((df['RSI14'] - rsi_min5) > 10)
    cond_w = pd.Series(False, index=df.index)
    for i in range(20, len(df)):
        window = df.iloc[i-20:i+1].copy()
        local_mins = window[window['RSI_Local_Min']].index
        if len(local_mins) < 2:
            continue
        low2_idx = local_mins[-1]
        low1_idx = local_mins[-2]
        rsi_low1 = df.loc[low1_idx, 'RSI14']
        rsi_low2 = df.loc[low2_idx, 'RSI14']
        if rsi_low2 > rsi_low1 and rsi_low2 < 30 and rsi_low1 < 30:
            if df.loc[i, 'RSI14'] > rsi_low2 + 5 and df.loc[i, 'RSI14'] > df.loc[i-1, 'RSI14']:
                cond_w.iloc[i] = True
    
    n = 20
    df['Low_N'] = df['Low'].rolling(n, min_periods=1).min()
    rsi_at_low = df['RSI14'].where(df['Low'] == df['Low_N'], np.nan)
    df['RSI_at_Low'] = rsi_at_low.ffill()
    price_lower = df['Low'] < df['Low_N'].shift(1)
    rsi_higher = df['RSI14'] > df['RSI_at_Low'].shift(1)
    rsi_turn_up = (df['RSI14'] > df['RSI14'].shift(1)) & (df['RSI14'] < 35)
    cond_divergence = price_lower & rsi_higher & rsi_turn_up
    
    rsi_below20 = df['RSI14'] < 20
    rsi_std5 = df['RSI14'].rolling(5, min_periods=5).std()
    cond_sideways = rsi_below20 & (rsi_std5 < 2)
    sideways_consecutive = cond_sideways.rolling(4, min_periods=4).sum() >= 4
    breakout = rsi_rise_cross30 & (df['volume_ratio'] > 1.2)
    cond_stagnation = sideways_consecutive.shift(1) & breakout
    
    final_condition = cond_v | cond_w | cond_divergence | cond_stagnation
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = final_condition & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    result_df['Signal_Type'] = ''
    result_df['Signal_Strength'] = ''
    for idx in result_df.index:
        if cond_v.loc[idx]:
            result_df.loc[idx, 'Signal_Type'] = 'V型拐头'
            result_df.loc[idx, 'Signal_Strength'] = '⭐⭐⭐'
        elif cond_w.loc[idx]:
            result_df.loc[idx, 'Signal_Type'] = '双底拐头'
            result_df.loc[idx, 'Signal_Strength'] = '⭐⭐⭐⭐'
        elif cond_divergence.loc[idx]:
            result_df.loc[idx, 'Signal_Type'] = '底背离拐头'
            result_df.loc[idx, 'Signal_Strength'] = '⭐⭐⭐⭐⭐'
        elif cond_stagnation.loc[idx]:
            result_df.loc[idx, 'Signal_Type'] = '钝化后拐头'
            result_df.loc[idx, 'Signal_Strength'] = '⭐⭐⭐⭐'
    if result_df.empty:
        return pd.DataFrame()
    return result_df

def query_breakout_gap(ticker, start_date, end_date, features_to_show, gap_min_pct=0.01, require_confirmation=True, debug=True):
    """突破缺口"""
    df = load_data_with_cache(ticker, 'daily')
    if 'EMA60' not in df.columns:
        df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
    if 'EMA120' not in df.columns:
        df['EMA120'] = df['Close'].ewm(span=120, adjust=False).mean()
    if 'volume_ratio' not in df.columns:
        vol_ema5 = df['Volume'].rolling(5, min_periods=1).mean()
        df['volume_ratio'] = df['Volume'] / vol_ema5
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'EMA60', 'EMA120', 'volume_ratio']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"日线文件缺少以下列: {missing}")
    
    cond_gap = df['Low'] > df['High'].shift(1)
    gap_ratio = (df['Low'] - df['High'].shift(1)) / df['High'].shift(1)
    cond_gap_size = gap_ratio >= gap_min_pct
    cond_break_60 = df['Close'] > df['EMA60']
    cond_break_120 = df['Close'] > df['EMA120']
    df['High_60d_max'] = df['High'].rolling(60, min_periods=1).max()
    cond_new_high = df['High'] >= df['High_60d_max'] * 0.98
    df['High_20d_max'] = df['High'].rolling(20, min_periods=1).max().shift(1)
    cond_break_20_high = (df['High'] > df['High_20d_max']) & (df['High_20d_max'].notna())
    cond_position = cond_break_60 | cond_break_120 | cond_new_high | cond_break_20_high
    cond_core = cond_gap & cond_gap_size & cond_position
    
    if require_confirmation:
        cond_confirm = pd.Series(False, index=df.index)
        for i in range(len(df) - 3):
            if cond_core.iloc[i]:
                gap_high = df.loc[i, 'High']
                future_lows = df['Low'].iloc[i+1:i+4]
                if len(future_lows) == 3 and (future_lows > gap_high).all():
                    cond_confirm.iloc[i] = True
        final_condition = cond_confirm
    else:
        final_condition = cond_core
    
    date_mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    final_mask = final_condition & date_mask
    result_df = df.loc[final_mask].copy()
    result_df = result_df.sort_values('Date')
    result_df['Gap_Ratio'] = gap_ratio.loc[result_df.index]
    result_df['Volume_Surge'] = (df['volume_ratio'] > 1.2).loc[result_df.index]
    result_df['Break_MA60'] = cond_break_60.loc[result_df.index]
    result_df['Break_MA120'] = cond_break_120.loc[result_df.index]
    result_df['Break_New_High60'] = cond_new_high.loc[result_df.index]
    result_df['Break_20High'] = cond_break_20_high.loc[result_df.index]
    result_df['Confirmed'] = final_condition.loc[result_df.index] if require_confirmation else True
    return result_df

# ==================== 并行信号执行器 ====================
class SignalExecutor:
    """并行信号执行器"""
    
    def __init__(self, ticker: str, start_date: str, end_date: str, max_workers: int = 8):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.max_workers = max_workers
        self._signal_functions = self._get_signal_functions()
    
    @staticmethod
    def _get_signal_functions() -> List[Tuple[str, Callable]]:
        """获取所有信号检测函数"""
        indicators = [
            ("三线金叉共振1", query_triple_golden_cross1),
            ("黄金买点3", query_golden_buy_point3),
            ("黄金买点4", query_golden_buy_point4),
            ("月线底背离1", query_monthly_divergence1),
            ("月线底背离2", query_monthly_divergence2),
            ("月线底背离3", query_monthly_divergence3),
            ("周线底背离1", query_weekly_divergence1),
            ("周线底背离2", query_weekly_divergence2),
            ("周线底背离3", query_weekly_divergence3),
            ("一阳穿五线（均线粘合+MACD金叉）", query_one_yang_through_five_lines),
            ("双重底颈线放量突破", query_double_bottom_breakout),
            ("头肩底颈线放量突破", query_head_shoulders_bottom_breakout),
            ("21日与63日均线圆弧底突破", query_21_63_arc_bottom_break),
            ("底部立桩量（不破最低价）", query_standing_pole_volume),
            ("空中加油（缩量回踩关键均线）", query_air_refueling),
            ("黄金分割回调（阳线回调至0.382/0.5）", query_golden_fibonacci_retracement),
            ("均线多头排列首次金叉", query_bullish_ma_first_golden_cross),
            ("看涨吞没（低位）", query_bullish_engulfing),
            ("启明星（低位）", query_morning_star),
            ("均线金叉（单一信号）", query_moving_average_golden_cross),
            ("布林下轨超卖+反转K线", query_bollinger_oversold_reversal),
            ("KDJ低位金叉（单一）", query_kdj_low_golden_cross),
            ("RSI超卖区拐头（单一）", query_rsi_oversold_turn),
            ("突破缺口（无其他共振）", query_breakout_gap),
            ("金针探底1", query_needle_bottom1),
            ("金针探底2", query_needle_bottom2),
            ("黄金坑", query_golden_pit),
            ("股价与机构资金流底背离", query_price_inst_divergence),
        ]
        return indicators
    
    def execute_all(self) -> Tuple[pd.DataFrame, Dict]:
        """并行执行所有信号检测"""
        all_signals = []
        detailed_dfs = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_name = {
                executor.submit(func, self.ticker, self.start_date, self.end_date, []): name
                for name, func in self._signal_functions
            }
            
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    df = future.result(timeout=120)
                    if df is not None and not df.empty:
                        if 'Date' not in df.columns and 'Signal_Date' in df.columns:
                            df = df.rename(columns={'Signal_Date': 'Date'})
                        for _, row in df.iterrows():
                            date_val = row['Date']
                            if not isinstance(date_val, (pd.Timestamp, datetime)):
                                date_val = pd.to_datetime(date_val)
                            all_signals.append({
                                'Date': date_val,
                                'Signal_Name': name,
                                'Details': row.to_dict()
                            })
                        detailed_dfs[name] = df.copy()
                        logger.debug(f"[{self.ticker}] {name}: 发现 {len(df)} 个信号")
                except Exception as e:
                    logger.warning(f"[{self.ticker}] {name} 执行失败: {e}")
                    if DEBUG:
                        logger.error(f"{name} 错误详情", exc_info=True)
        
        signals_df = pd.DataFrame(all_signals) if all_signals else pd.DataFrame()
        return signals_df, detailed_dfs

# ==================== 批量保存到数据库 ====================
@retry_on_locked(max_retries=5, delay=0.5, backoff=2.0)
def batch_save_signals_to_db(ticker: str, stock_name: str, signals_df: pd.DataFrame) -> int:
    """批量保存信号到数据库（带重试机制）"""
    if signals_df is None or signals_df.empty:
        return 0
    
    # 清理所有 NaT/NaN
    signals_df = sanitize_na_values(signals_df)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 确保表存在
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hk_buy_signal_details (
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                signal_type TEXT NOT NULL DEFAULT 'buy',
                signal_date TEXT NOT NULL,
                signal_name TEXT NOT NULL,
                details TEXT,
                base_score REAL,
                resonance_score REAL,
                trend_score REAL,
                volume_score REAL,
                composite_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (stock_code, signal_date, signal_name)
            )
        """)
        
        # 删除旧记录
        cursor.execute("DELETE FROM hk_buy_signal_details WHERE stock_code = ?", (ticker,))
        
        # 准备批量插入
        insert_sql = """
            INSERT OR REPLACE INTO hk_buy_signal_details 
            (stock_code, stock_name, signal_type, signal_date, signal_name, details,
             base_score, resonance_score, trend_score, volume_score, composite_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        now_singapore = get_singapore_time()
        now_str = now_singapore.strftime('%Y-%m-%d %H:%M:%S')
        
        batch_data = []
        for _, row in signals_df.iterrows():
            signal_date = row.get('Date')
            if signal_date is None:
                signal_date = row.get('Signal_Date')
            if signal_date is None:
                continue
            
            signal_date_str = date_to_str(signal_date)
            if signal_date_str is None:
                continue
            
            signal_name = row.get('Signal_Name', '')
            if not signal_name:
                continue
            
            details_dict = row.get('Details', {})
            if isinstance(details_dict, dict):
                # 先清理 NaT/NaN，再转换日期
                details_dict = sanitize_na_values(details_dict)
                details_dict = convert_dates_in_dict(details_dict)
                details_json = json.dumps(details_dict, ensure_ascii=False, default=str)
            else:
                details_json = str(details_dict) if details_dict else ''
            
            batch_data.append((
                ticker, stock_name, 'buy', signal_date_str, signal_name, details_json,
                float(row.get('BaseScore', 0.0)) if row.get('BaseScore') is not None else 0.0,
                float(row.get('ResonanceScore', 0.0)) if row.get('ResonanceScore') is not None else 0.0,
                float(row.get('TrendScore', 0.0)) if row.get('TrendScore') is not None else 0.0,
                float(row.get('VolumeScore', 0.0)) if row.get('VolumeScore') is not None else 0.0,
                float(row.get('CompositeScore', 0.0)) if row.get('CompositeScore') is not None else 0.0,
                now_str
            ))
        
        if batch_data:
            # 分批插入，每批500条
            batch_size = 500
            total_saved = 0
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i+batch_size]
                cursor.executemany(insert_sql, batch)
                conn.commit()
                total_saved += len(batch)
            
            logger.info(f"{ticker} 批量保存了 {total_saved} 条信号到数据库 (新加坡时间: {now_str})")
            return total_saved
        
        conn.commit()
        return 0
        
    except Exception as e:
        logger.error(f"保存信号到数据库失败: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise
    finally:
        if conn:
            return_db_connection(conn)

# ==================== PDF 摘要报告生成 ====================
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape
import math

try:
    font_path = "C:/Windows/Fonts/simhei.ttf"
    pdfmetrics.registerFont(TTFont('SimHei', font_path))
    FONT_NAME = 'SimHei'
except:
    FONT_NAME = 'Helvetica'

def generate_summary_pdf(ticker: str, start_date: str, end_date: str, 
                         last_3weeks_start, last_3weeks_end, 
                         signals_df: pd.DataFrame, output_path: str):
    """生成买入信号摘要报告（PDF）"""
    ALLOWED_KEYS = {'Date', 'Close', 'Volume', 'EMA20', 'volume_ratio'}

    def format_details(obj):
        """格式化详情，确保日期为yyyy-mm-dd格式"""
        if obj is None or (isinstance(obj, float) and math.isnan(obj)):
            return "null"
        if isinstance(obj, dict):
            filtered = {}
            for k, v in obj.items():
                if k in ALLOWED_KEYS:
                    if isinstance(v, (pd.Timestamp, datetime)):
                        filtered[k] = v.strftime('%Y-%m-%d')
                    else:
                        filtered[k] = v
            items = []
            for k, v in filtered.items():
                if isinstance(k, str) and k.lower() in ('volume', 'amount'):
                    try:
                        num = float(v) if isinstance(v, (int, float)) else float(str(v))
                        if math.isnan(num) or math.isinf(num):
                            v = str(v)
                        else:
                            v = f"{num / 1e6:.2f}M"
                    except:
                        pass
                items.append(f"{k}: {format_details(v)}")
            return "{" + ", ".join(items) + "}"
        elif isinstance(obj, list):
            return "[" + ", ".join(format_details(item) for item in obj) + "]"
        elif isinstance(obj, (pd.Timestamp, datetime)):
            return f"'{obj.strftime('%Y-%m-%d')}'"
        elif isinstance(obj, (int, float)):
            if math.isnan(obj):
                return "null"
            if isinstance(obj, float) and obj != int(obj):
                return f"{obj:.2f}"
            return str(int(obj)) if isinstance(obj, float) and obj == int(obj) else str(obj)
        else:
            return str(obj)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    doc = SimpleDocTemplate(output_path, pagesize=landscape(A4),
                            rightMargin=36, leftMargin=36,
                            topMargin=72, bottomMargin=72)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='Title', parent=styles['Title'], fontName=FONT_NAME, fontSize=16, alignment=1, spaceAfter=12)
    heading_style = ParagraphStyle(name='Heading', parent=styles['Heading2'], fontName=FONT_NAME, fontSize=12, spaceAfter=6)
    normal_style = ParagraphStyle(name='Normal', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10, leading=14)
    detail_style = ParagraphStyle(name='Detail', parent=normal_style, fontName=FONT_NAME, fontSize=9, leading=12, alignment=0, wordWrap='CJK')

    story.append(Paragraph(f"{ticker} 买入信号分析报告（摘要）", title_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(f"股票代码：{ticker}", normal_style))
    story.append(Paragraph(f"分析期间：{start_date} 至 {end_date}", normal_style))
    story.append(Paragraph(f"最后3周范围：{last_3weeks_start.strftime('%Y-%m-%d')} 至 {last_3weeks_end.strftime('%Y-%m-%d')}", normal_style))
    story.append(Spacer(1, 0.2*inch))

    if signals_df.empty:
        story.append(Paragraph("最近3周内没有检测到任何买入信号。", heading_style))
        doc.build(story)
        return

    total_base = signals_df['BaseScore'].sum()
    story.append(Paragraph(f"基础评分总分：{total_base:.2f}", heading_style))
    story.append(Spacer(1, 0.1*inch))

    table_data = [["信号日期", "买入信号", "基础分", "共振分", "趋势分", "量能分", "综合分", "详情"]]
    for _, row in signals_df.iterrows():
        date_str = row['Date'].strftime('%Y-%m-%d')
        details_str = format_details(row['Details'])
        if len(details_str) > 200:
            details_str = details_str[:200] + "..."
        detail_para = Paragraph(escape(details_str), detail_style)
        table_data.append([
            date_str, row['Signal_Name'], f"{row['BaseScore']:.1f}", f"{row['ResonanceScore']:.1f}",
            f"{row['TrendScore']:.1f}", f"{row['VolumeScore']:.1f}", f"{row['CompositeScore']:.2f}", detail_para
        ])
    
    col_widths = [70, 130, 45, 45, 45, 45, 55, 200]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME), ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.grey), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('LEADING', (0,0), (-1,-1), 12),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("综合得分计算方法要点", heading_style))
    method_text = """
    综合得分 = 买入信号基础分 × 0.3 + 共振得分 × 0.3 + 趋势得分 × 0.2 + 量能得分 × 0.2<br/>
    - 买入信号基础分：根据买入信号类型的历史胜率，预设固定分数。<br/>
    - 共振得分：基于信号日检测 MACD金叉、均线多头、量比>1.5、KDJ金叉、RSI拐头，每项+2分，上限10分。<br/>
    - 趋势得分：依据周线和月线的均线排列评分，归一化至0-10。<br/>
    - 量能得分：用量比评分，>1.5得10分，1.2-1.5得8分，1.0-1.2得6分，<1.0得3分。
    """
    story.append(Paragraph(method_text, normal_style))
    doc.build(story)

# ==================== 主处理函数 ====================
def process_one_stock_optimized(ticker, start_date, end_date, start_dt, end_dt, report_dir):
    """优化后的单股票处理函数"""
    try:
        start_time_sg = get_singapore_time()
        logger.info(f"[{ticker}] 开始处理 (新加坡时间: {start_time_sg.strftime('%Y-%m-%d %H:%M:%S')})")
        
        # 获取股票名称（从 hk_stock_info 表）
        stock_name = get_stock_name(ticker)
        logger.info(f"处理股票: {ticker} ({stock_name})")
        
        # 计算最后3周范围
        try:
            weekly_df = load_data_with_cache(ticker, 'weekly')
            weekly_df = weekly_df[weekly_df['Date'] <= end_dt]
            if len(weekly_df) >= 3:
                last_3weeks_start = weekly_df['Date'].iloc[-3]
            else:
                last_3weeks_start = weekly_df['Date'].min() if not weekly_df.empty else start_dt
        except Exception as e:
            logger.warning(f"无法获取周线数据: {e}")
            last_3weeks_start = start_dt
        last_3weeks_end = end_dt
        
        logger.debug(f"[{ticker}] 最后3周范围: {last_3weeks_start.strftime('%Y-%m-%d')} 至 {last_3weeks_end.strftime('%Y-%m-%d')}")
        
        # 并行执行信号检测
        executor = SignalExecutor(ticker, start_date, end_date, max_workers=8)
        signals_df, detailed_dfs = executor.execute_all()
        
        if not signals_df.empty:
            # 计算评分
            daily_data = load_data_with_cache(ticker, 'daily')
            
            signals_df['BaseScore'] = signals_df['Signal_Name'].apply(get_base_score)
            signals_df['ResonanceScore'] = signals_df.apply(
                lambda row: compute_resonance_score(row, daily_data), axis=1
            )
            signals_df['TrendScore'] = signals_df['Date'].apply(
                lambda d: compute_trend_score(ticker, d)
            )
            signals_df['VolumeScore'] = signals_df.apply(
                lambda row: compute_volume_score(row, daily_data), axis=1
            )
            signals_df['CompositeScore'] = (
                signals_df['BaseScore'] * 0.3 + 
                signals_df['ResonanceScore'] * 0.3 + 
                signals_df['TrendScore'] * 0.2 + 
                signals_df['VolumeScore'] * 0.2
            )
            
            # 批量保存到数据库
            saved_count = batch_save_signals_to_db(ticker, stock_name, signals_df)
            logger.info(f"[{ticker}] 已保存 {saved_count} 条信号到数据库")
            
            # 过滤最近信号
            recent_signals = signals_df[
                (signals_df['Date'] >= last_3weeks_start) & 
                (signals_df['Date'] <= last_3weeks_end)
            ]
        else:
            recent_signals = pd.DataFrame()
            logger.info(f"[{ticker}] 未发现任何信号")
        
        # 生成PDF报告
        summary_path = os.path.join(report_dir, f"{ticker}_buy_signal_analysis_sum.pdf")
        generate_summary_pdf(
            ticker, start_date, end_date,
            last_3weeks_start, last_3weeks_end,
            recent_signals, summary_path
        )
        
        end_time_sg = get_singapore_time()
        elapsed = (end_time_sg - start_time_sg).total_seconds()
        logger.info(f"[{ticker}] 处理完成，发现 {len(recent_signals)} 个近期信号，用时 {elapsed:.2f} 秒 (新加坡时间: {end_time_sg.strftime('%Y-%m-%d %H:%M:%S')})")
        
    except Exception as e:
        logger.error(f"[{ticker}] 处理时发生错误: {e}", exc_info=True)
        raise        

def find_project_root(start_path=None, config_dir_name='config'):
    if start_path is None:
        if '__file__' in globals():
            start_path = os.path.dirname(os.path.abspath(__file__))
        else:
            start_path = os.getcwd()
    start_path = os.path.abspath(start_path)
    current = start_path
    while True:
        if os.path.isdir(os.path.join(current, config_dir_name)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return start_path

def setup_logging(log_dir, log_filename="Daily_TA6A_Buy_Signal_Analyzer_Optimized.log"):
    """
    配置日志系统，同时输出到控制台和日志文件
    参考 Daily_TA5_MergePDF.py 中的 setup_logging 方法
    
    参数:
    log_dir (str): 日志文件目录
    log_filename (str): 日志文件名
    """
    global logger
    
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
        ],
        force=True
    )
    
    # 获取全局logger
    logger = logging.getLogger(__name__)
    logger.info(f"日志系统初始化完成，日志文件: {log_filepath}")
    return log_filepath

# ==================== 主函数 ====================
def main():
    """主函数"""
    global logger
    
    try:
        # ========== 主程序路径配置 ==========        
        # 构建配置文件路径：父目录下的config文件夹中的stock_data_analysis.par
        config_path = os.path.join(project_dir, 'Config', 'stock_data_analysis.par')

        # ========== 加载配置 ==========
        # 使用load_config函数加载配置
        CONFIG = load_config(config_path, project_dir)
        logger.info(f"配置文件加载成功: {config_path}")

        # 更新全局路径配置
        GlobalConfig.update_paths(CONFIG, project_dir)
        
        # ========== 初始化日志系统 ==========
        # 在更新路径后初始化日志系统
        log_filepath = setup_logging(
            GlobalConfig.full_log_dir, 
            "Daily_TA6A_Buy_Signal_Analyzer_Optimized.log"
        )
        
        # ========== 打印配置信息 ==========
        logger.info("=" * 60)
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件位置: {config_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"报告目录: {GlobalConfig.full_report_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        logger.info(f"日志文件: {log_filepath}")
        logger.info("优化版买入信号分析程序启动")
        logger.info("=" * 60)
        
        # ===== 支持从 stock_list.json 读取股票列表 =====
        # 优先从配置文件中的 stock_list_data 获取股票列表
        tickers = []
        
        if 'stock_list_data' in CONFIG and CONFIG['stock_list_data']:
            stock_data = CONFIG['stock_list_data']
            if 'stocks' in stock_data:
                # 使用 stock_code 字段
                tickers = [stock['stock_code'] for stock in stock_data['stocks']]
                logger.info(f"从 stock_list.json 加载了 {len(tickers)} 只股票")
            else:
                logger.warning("stock_list.json 中没有 stocks 字段，使用备用列表")
        
        # 如果没有从 stock_list_data 获取到，尝试从 tickers 配置获取
        if not tickers:
            tickers = CONFIG.get('tickers', [])
            if tickers:
                logger.info(f"从配置文件加载了 {len(tickers)} 只股票")
        
        # 如果 tickers 仍然为空，尝试直接从 stock_list.json 加载
        if not tickers:
            stock_list_path = os.path.join(project_dir, 'Config', 'stock_list.json')
            if os.path.exists(stock_list_path):
                import json
                try:
                    with open(stock_list_path, 'r', encoding='utf-8') as f:
                        stock_data = json.load(f)
                    if 'stocks' in stock_data:
                        # 使用 stock_code 字段
                        tickers = [stock['stock_code'] for stock in stock_data['stocks']]
                        logger.info(f"直接从 stock_list.json 加载了 {len(tickers)} 只股票")
                        # 同时保存到 CONFIG 供后续使用
                        CONFIG['stock_list_data'] = stock_data
                except Exception as e:
                    logger.error(f"加载 stock_list.json 失败: {e}")
        
        # 如果仍然没有股票列表，报错退出
        if not tickers:
            logger.error("没有配置股票代码，请检查 Config/stock_list.json 文件")
            return
        
        start_date, end_date = get_validated_dates(CONFIG, project_dir)
        
        logger.info(f"股票数量: {len(tickers)}")
        logger.info(f"股票列表: {', '.join(tickers[:5])}{'...' if len(tickers) > 5 else ''}")
        logger.info(f"日期范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        report_dir = GlobalConfig.full_report_dir
        os.makedirs(report_dir, exist_ok=True)
        
        start_time = time.time()
        
        use_multiprocessing = CONFIG.get('use_multiprocessing', True)
        max_workers = CONFIG.get('max_workers', max(1, os.cpu_count() - 1))
        
        if use_multiprocessing and max_workers > 1 and len(tickers) > 1:
            logger.info(f"使用多进程处理，进程数: {min(max_workers, len(tickers))}")
            
            with mp.Pool(processes=min(max_workers, len(tickers))) as pool:
                results = []
                for ticker in tickers:
                    result = pool.apply_async(
                        process_one_stock_optimized,
                        (ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'),
                         start_dt, end_dt, report_dir)
                    )
                    results.append(result)
                
                for i, result in enumerate(results):
                    try:
                        result.get(timeout=600)
                        logger.info(f"股票 {tickers[i]} 处理完成")
                    except Exception as e:
                        logger.error(f"股票 {tickers[i]} 处理失败: {e}")
        else:
            logger.info("使用单进程处理")
            for ticker in tickers:
                process_one_stock_optimized(
                    ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'),
                    start_dt, end_dt, report_dir
                )
        
        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"✅ 所有股票处理完成，总用时: {elapsed:.2f} 秒")
        logger.info(f"📁 报告目录: {report_dir}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"主程序错误: {e}", exc_info=True)
    finally:
        close_db_connection()
        logger.info("数据库连接已关闭")
        
if __name__ == "__main__":
    if sys.platform.startswith('win'):
        mp.freeze_support()
    main()