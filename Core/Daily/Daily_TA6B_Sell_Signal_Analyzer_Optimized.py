#!/usr/bin/env python
# coding: utf-8
r"""
Name: Daily_TA6B_Sell_Signal_Analyzer_Optimized.py
Function: 卖出信号分析--自动模式（读取配置文件）
1. 遍历配置文件中的股票代码，进行多任务并行处理。
2. 生成卖出信号摘要报告（PDF）。
3. 卖出详细信号保存到数据库表 hk_sell_signal_details。

优化版卖出信号处理程序 - 完整代码
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

# 全局logger变量
logger = logging.getLogger(__name__)
DEBUG = False


# ==================== 日志系统配置（参考 Daily_TA5_MergePDF.py） ====================
def setup_logging(log_dir, log_filename="Daily_TA6B_Sell_Signal_Analyzer_Optimized.log"):
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
        self._max_size = 5
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
    """获取股票名称（带缓存）"""
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
        finally:
            return_db_connection(conn)
    except Exception as e:
        logger.warning(f"获取股票名称失败，使用代码代替: {e}")
    
    with _cache_lock:
        _stock_name_cache[ticker] = stock_name
    
    return stock_name

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

def rolling_all(condition: pd.Series, window: int) -> pd.Series:
    """向量化窗口内全部为真"""
    s_int = condition.astype(float)
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
    # === 均线计算 ===
    for span in [3, 5, 10, 20, 21, 50, 60, 63, 120]:
        col = f'EMA{span}'
        if col not in df.columns:
            df[col] = df['Close'].ewm(span=span, adjust=False).mean()
    
    # === 成交量相关指标 ===
    if 'volume_ratio' not in df.columns:
        vol_ema5 = df['Volume'].rolling(5, min_periods=1).mean()
        df['volume_ratio'] = df['Volume'] / vol_ema5
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
    
    if 'VOL_EMA5' not in df.columns:
        df['VOL_EMA5'] = df['Volume'].rolling(5, min_periods=1).mean()
    if 'VOL_EMA10' not in df.columns:
        df['VOL_EMA10'] = df['Volume'].rolling(10, min_periods=1).mean()
    
    # === MACD指标 ===
    if 'MACD_DIF' not in df.columns:
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD_DIF'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD_DIF'] - df['MACD_Signal']
    
    # === KDJ指标 ===
    if 'KDJ_K' not in df.columns:
        low_min = df['Low'].rolling(9, min_periods=1).min()
        high_max = df['High'].rolling(9, min_periods=1).max()
        rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
        rsv = rsv.fillna(50)
        df['KDJ_K'] = rsv.ewm(alpha=1/3, adjust=False).mean()
        df['KDJ_D'] = df['KDJ_K'].ewm(alpha=1/3, adjust=False).mean()
        df['KDJ_J'] = 3 * df['KDJ_K'] - 2 * df['KDJ_D']
    
    # === RSI指标 ===
    if 'RSI14' not in df.columns:
        delta = df['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['RSI14'] = 100 - (100 / (1 + rs))
        df['RSI14'] = df['RSI14'].fillna(50)
    
    # === 布林带 ===
    if 'Bollinger_Lower' not in df.columns:
        window = 20
        middle = df['Close'].rolling(window).mean()
        std = df['Close'].rolling(window).std()
        df['Bollinger_Upper'] = middle + 2 * std
        df['Bollinger_Lower'] = middle - 2 * std
        df['Bollinger_Middle'] = middle
    
    # === OBV指标 ===
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
    
    # === 局部极值检测（完整版） ===
    # 定义所有需要的局部极值配置
    extrema_configs = [
        ('Local_Min_3', 'Low', 3, 'min'),
        ('Local_Max_3', 'High', 3, 'max'),
        ('Local_Min_5', 'Low', 5, 'min'),
        ('Local_Max_5', 'High', 5, 'max'),
        ('Local_Min_7', 'Low', 7, 'min'),
        ('Local_Max_7', 'High', 7, 'max'),
        ('Local_Min_10', 'Low', 10, 'min'),
        ('Local_Max_10', 'High', 10, 'max'),
        ('Local_Min_14', 'Low', 14, 'min'),
        ('Local_Max_14', 'High', 14, 'max'),
        ('Local_Min_20', 'Low', 20, 'min'),
        ('Local_Max_20', 'High', 20, 'max'),
    ]
    
    for col_name, source_col, order, mode in extrema_configs:
        df[col_name] = find_local_extrema(df[source_col], order=order, mode=mode)
    
    # === K线特征计算 ===
    df = compute_candle_features(df)
    
    return df
    
@lru_cache(maxsize=128)
def get_sell_base_score(signal_name: str) -> float:
    """获取卖出信号基础分"""
    SELL_BASE_SCORE_MAP = {
        "头肩顶": 10.0,
        "圆弧顶": 10.0,
        "双顶": 9.0,
        "三重顶": 9.0,
        "菱形顶": 9.0,
        "MACD顶背离 + 均线死叉": 8.0,
        "MACD顶背离 + 成交量萎缩": 8.0,
        "MACD顶背离 + 均线死叉 + 成交量放大破位": 9.5,
        "RSI顶背离 + 均线死叉": 8.0,
        "RSI顶背离 + 成交量萎缩": 8.0,
        "RSI顶背离 + 均线死叉 + 放量跌破支撑 / 看跌K线": 9.5,
        "均线死叉": 8.0,
        "空头排列": 8.0,
        "趋势线跌破": 8.0
    }
    return SELL_BASE_SCORE_MAP.get(signal_name, 5.0)

def compute_sell_resonance_score(df_signal: pd.Series, daily_data: pd.DataFrame) -> float:
    """计算卖出共振得分"""
    date = df_signal['Date']
    day = daily_data[daily_data['Date'] == date]
    if day.empty:
        return 0
    row = day.iloc[0]
    score = 0
    
    if row.get('EMA5', 0) < row.get('EMA20', 0):
        score += 2
    if row.get('MACD_DIF', 0) < row.get('MACD_Signal', 0):
        score += 2
    if row.get('KDJ_K', 0) < row.get('KDJ_D', 0):
        score += 2
    if row.get('volume_ratio', 0) > 1.5 and row.get('Close', 0) < row.get('Open', 0):
        score += 2
    if row.get('Close', 0) < row.get('EMA20', 0):
        score += 2
    
    return min(score, 10)

def compute_sell_trend_score(ticker: str, signal_date: datetime) -> float:
    """计算卖出趋势得分"""
    try:
        weekly = load_data_with_cache(ticker, 'weekly')
        monthly = load_data_with_cache(ticker, 'monthly')
    except:
        return 5.0
    
    week_data = weekly[weekly['Date'] <= signal_date].iloc[-1] if not weekly[weekly['Date'] <= signal_date].empty else None
    month_data = monthly[monthly['Date'] <= signal_date].iloc[-1] if not monthly[monthly['Date'] <= signal_date].empty else None
    
    trend_score = 0
    if week_data is not None:
        if week_data.get('EMA10', 0) < week_data.get('EMA20', 0) < week_data.get('EMA50', 0):
            trend_score += 5
        elif week_data.get('EMA10', 0) < week_data.get('EMA20', 0):
            trend_score += 3
        else:
            trend_score += 1
    
    if month_data is not None:
        if month_data.get('EMA10', 0) < month_data.get('EMA20', 0):
            trend_score += 5
        else:
            trend_score += 2
    
    return min(max(trend_score, 0), 10)

def compute_sell_volume_score(df_signal: pd.Series, daily_data: pd.DataFrame) -> float:
    """计算卖出量能得分"""
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


# ==================== 信号检测函数（卖出 - 优化版） ====================

def query_head_shoulders_top(ticker, start_date, end_date, features_to_show=None):
    """头肩顶"""
    df = load_data_with_cache(ticker, 'daily')
    if len(df) < 120:
        return pd.DataFrame()
    
    peaks = df[df['Local_Max_5']].index.tolist()
    if len(peaks) < 3:
        return pd.DataFrame()
    
    signals = []
    for i in range(len(peaks) - 2):
        head_idx = peaks[i+1]
        left_idx = peaks[i]
        right_idx = peaks[i+2]
        
        if right_idx - left_idx > 120 or head_idx - left_idx < 5 or right_idx - head_idx < 5:
            continue
        
        head_price = df.loc[head_idx, 'High']
        left_price = df.loc[left_idx, 'High']
        right_price = df.loc[right_idx, 'High']
        
        if left_price >= head_price * 0.98 or right_price >= head_price * 0.98:
            continue
        
        between_left_head = df.iloc[left_idx+1:head_idx]
        if between_left_head.empty:
            continue
        neck_left_idx = between_left_head['Low'].idxmin()
        neck_left_price = df.loc[neck_left_idx, 'Low']
        neck_left_date = df.loc[neck_left_idx, 'Date']
        
        between_head_right = df.iloc[head_idx+1:right_idx+1]
        if between_head_right.empty:
            continue
        neck_right_idx = between_head_right['Low'].idxmin()
        neck_right_price = df.loc[neck_right_idx, 'Low']
        neck_right_date = df.loc[neck_right_idx, 'Date']
        
        if neck_left_price <= 0 or neck_right_price <= 0:
            continue
        
        x1 = neck_left_date.timestamp()
        y1 = neck_left_price
        x2 = neck_right_date.timestamp()
        y2 = neck_right_price
        if x2 == x1:
            continue
        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - slope * x1
        
        vol_left = df.loc[left_idx, 'Volume']
        vol_right = df.loc[right_idx, 'Volume']
        if vol_right >= vol_left:
            continue
        
        for future in range(right_idx + 1, len(df)):
            future_date = df.loc[future, 'Date']
            neck_val = slope * future_date.timestamp() + intercept
            if df.loc[future, 'Close'] < neck_val and df.loc[future, 'volume_ratio'] >= 1.5:
                signals.append({
                    'Date': future_date,
                    'Close': df.loc[future, 'Close'],
                    'Break_Price': df.loc[future, 'Close'],
                    'Neckline': neck_val,
                    'Volume_Ratio': df.loc[future, 'volume_ratio'],
                    'Left_Shoulder_Date': df.loc[left_idx, 'Date'],
                    'Left_Shoulder_Price': left_price,
                    'Head_Date': df.loc[head_idx, 'Date'],
                    'Head_Price': head_price,
                    'Right_Shoulder_Date': df.loc[right_idx, 'Date'],
                    'Right_Shoulder_Price': right_price,
                })
                break
    
    if not signals:
        return pd.DataFrame()
    result_df = pd.DataFrame(signals).drop_duplicates(subset='Date').reset_index(drop=True)
    return result_df

def query_rounding_top(ticker, start_date, end_date, features_to_show=None):
    """圆弧顶"""
    df = load_data_with_cache(ticker, 'daily')
    if len(df) < 30:
        return pd.DataFrame()
    
    peaks = df[df['Local_Max_7']].index.tolist()
    troughs = df[df['Local_Min_5']].index.tolist()
    if len(peaks) < 3 or len(troughs) < 2:
        return pd.DataFrame()
    
    signals = []
    for i in range(len(peaks) - 2):
        p1, p2, p3 = peaks[i], peaks[i+1], peaks[i+2]
        if p3 - p1 < 30:
            continue
        
        h1, h2, h3 = df.loc[p1, 'High'], df.loc[p2, 'High'], df.loc[p3, 'High']
        if h2 < h1 * 0.98 or h3 < h2 * 0.98:
            continue
        
        top_high = df.loc[p1:p3, 'High'].max()
        top_low = df.loc[p1:p3, 'Low'].min()
        if (top_high - top_low) / top_low > 0.03:
            continue
        
        vol_before = df.loc[p1:p2, 'Volume'].mean()
        vol_after = df.loc[p2:p3, 'Volume'].mean()
        if vol_before > 0 and vol_after > vol_before * 0.7:
            continue
        
        left_trough = next((t for t in reversed(troughs) if t < p1), None)
        right_trough = next((t for t in troughs if t > p3), None)
        if left_trough is None or right_trough is None:
            continue
        
        neckline = min(df.loc[left_trough, 'Low'], df.loc[right_trough, 'Low'])
        for j in range(right_trough + 1, len(df)):
            if df.loc[j, 'Close'] < neckline and df.loc[j, 'volume_ratio'] >= 1.2:
                signals.append({
                    'Date': df.loc[j, 'Date'],
                    'Break_Price': df.loc[j, 'Close'],
                    'Neckline': neckline,
                    'Volume_Ratio': df.loc[j, 'volume_ratio'],
                    'Start_Date': df.loc[p1, 'Date'],
                    'End_Date': df.loc[j, 'Date'],
                    'Duration': p3 - p1,
                    'Top_Amplitude': (top_high - top_low) / top_low,
                    'Vol_Shrink_Ratio': vol_after / vol_before if vol_before > 0 else 1.0
                })
                break
    
    if not signals:
        return pd.DataFrame()
    result_df = pd.DataFrame(signals).drop_duplicates(subset='Date').reset_index(drop=True)
    return result_df

def query_double_top(ticker, start_date, end_date, features_to_show=None):
    """双顶"""
    df = load_data_with_cache(ticker, 'daily')
    if len(df) < 60:
        return pd.DataFrame()
    
    peaks = df[df['Local_Max_5']].index.tolist()
    signals = []
    
    for i in range(len(peaks) - 1):
        left_idx, right_idx = peaks[i], peaks[i+1]
        if right_idx - left_idx < 10 or right_idx - left_idx > 60:
            continue
        
        left_price = df.loc[left_idx, 'High']
        right_price = df.loc[right_idx, 'High']
        if abs(left_price - right_price) / left_price > 0.03:
            continue
        
        valley_idx = df.iloc[left_idx:right_idx+1]['Low'].idxmin()
        neckline = df.loc[valley_idx, 'Low']
        
        for future in range(right_idx + 1, len(df)):
            if df.loc[future, 'Close'] < neckline and df.loc[future, 'volume_ratio'] >= 1.5:
                signals.append({
                    'Date': df.loc[future, 'Date'],
                    'Break_Price': df.loc[future, 'Close'],
                    'Neckline': neckline,
                    'Volume_Ratio': df.loc[future, 'volume_ratio'],
                    'Left_Peak_Date': df.loc[left_idx, 'Date'],
                    'Left_Peak_Price': left_price,
                    'Right_Peak_Date': df.loc[right_idx, 'Date'],
                    'Right_Peak_Price': right_price,
                    'Valley_Date': df.loc[valley_idx, 'Date'],
                    'Valley_Price': neckline
                })
                break
    
    if not signals:
        return pd.DataFrame()
    result_df = pd.DataFrame(signals).drop_duplicates(subset='Date').reset_index(drop=True)
    return result_df

def query_triple_top(ticker, start_date, end_date, features_to_show=None):
    """三重顶"""
    df = load_data_with_cache(ticker, 'daily')
    if len(df) < 120:
        return pd.DataFrame()
    
    peaks = df[df['Local_Max_5']].index.tolist()
    signals = []
    
    for i in range(len(peaks) - 2):
        p1, p2, p3 = peaks[i], peaks[i+1], peaks[i+2]
        if p3 - p1 > 120:
            continue
        
        prices = [df.loc[p, 'High'] for p in [p1, p2, p3]]
        if max(prices) - min(prices) > 0.05 * np.mean(prices):
            continue
        if p2 - p1 <= 1 or p3 - p2 <= 1:
            continue
        
        valley1_idx = df.iloc[p1+1:p2]['Low'].idxmin()
        valley2_idx = df.iloc[p2+1:p3]['Low'].idxmin()
        neckline = min(df.loc[valley1_idx, 'Low'], df.loc[valley2_idx, 'Low'])
        
        for future in range(p3 + 1, len(df)):
            if df.loc[future, 'Close'] < neckline and df.loc[future, 'volume_ratio'] >= 1.5:
                signals.append({
                    'Date': df.loc[future, 'Date'],
                    'Break_Price': df.loc[future, 'Close'],
                    'Neckline': neckline,
                    'Volume_Ratio': df.loc[future, 'volume_ratio'],
                    'Peak1_Date': df.loc[p1, 'Date'],
                    'Peak1_Price': df.loc[p1, 'High'],
                    'Peak2_Date': df.loc[p2, 'Date'],
                    'Peak2_Price': df.loc[p2, 'High'],
                    'Peak3_Date': df.loc[p3, 'Date'],
                    'Peak3_Price': df.loc[p3, 'High']
                })
                break
    
    if not signals:
        return pd.DataFrame()
    result_df = pd.DataFrame(signals).drop_duplicates(subset='Date').reset_index(drop=True)
    return result_df

def query_diamond_top(ticker, start_date, end_date, features_to_show=None):
    """菱形顶"""
    df = load_data_with_cache(ticker, 'daily')
    min_duration = 45
    if len(df) < min_duration:
        return pd.DataFrame()
    
    signals = []
    for end in range(min_duration, len(df)):
        for start in range(max(0, end - min_duration*2), end - min_duration + 1):
            duration = end - start
            if duration < min_duration:
                continue
            
            window = df.iloc[start:end+1]
            mid = len(window) // 2
            if mid < 5:
                continue
            
            left = window.iloc[:mid]
            right = window.iloc[mid:]
            
            if len(left) >= 3:
                x = np.arange(len(left))
                slope_h_left, _ = np.polyfit(x, left['High'].values, 1)
                slope_l_left, _ = np.polyfit(x, left['Low'].values, 1)
                if slope_h_left < -0.001 or slope_l_left > 0.001:
                    continue
            
            if len(right) >= 3:
                x = np.arange(len(right))
                slope_h_right, _ = np.polyfit(x, right['High'].values, 1)
                slope_l_right, _ = np.polyfit(x, right['Low'].values, 1)
                if slope_h_right > -0.001 or slope_l_right < 0.001:
                    continue
            
            recent_low = df['Low'].iloc[max(0, start):end].min()
            if df.loc[end, 'Close'] < recent_low:
                signals.append({
                    'Date': df.loc[end, 'Date'],
                    'Break_Price': df.loc[end, 'Close'],
                    'Confirm_Type': '跌破近期低点',
                    'Volume_Ratio': df.loc[end, 'volume_ratio'],
                    'Start_Date': df.loc[start, 'Date'],
                    'End_Date': df.loc[end, 'Date'],
                    'Duration': duration
                })
                break
    
    if not signals:
        return pd.DataFrame()
    result_df = pd.DataFrame(signals).drop_duplicates(subset='Date').reset_index(drop=True)
    return result_df

def _macd_divergence_vectorized(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """向量化MACD顶背离检测"""
    n = len(df)
    if n < lookback * 2:
        return pd.Series(False, index=df.index)
    
    diff_div = pd.Series(False, index=df.index)
    
    close_values = df['Close'].values
    macd_dif_values = df['MACD_DIF'].values
    macd_hist_values = df['MACD_Histogram'].values
    
    for i in range(lookback*2, n):
        window_start = i - lookback
        window_end = i + 1
        
        price_window = close_values[window_start:window_end]
        price_high_idx = window_start + np.argmax(price_window)
        price_high = close_values[price_high_idx]
        ind_at_high = macd_dif_values[price_high_idx]
        
        prev_start = max(0, i - 2*lookback)
        prev_end = i - lookback
        if prev_end - prev_start < 5:
            continue
        
        prev_price_window = close_values[prev_start:prev_end]
        prev_price_high_idx = prev_start + np.argmax(prev_price_window)
        prev_price_high = close_values[prev_price_high_idx]
        prev_ind_at_high = macd_dif_values[prev_price_high_idx]
        
        if prev_price_high > 0 and price_high > prev_price_high * 1.02:
            if ind_at_high < prev_ind_at_high:
                diff_div.iloc[i] = True
    
    return diff_div

def query_macd_divergence_death_cross(ticker, start_date, end_date, features_to_show=None):
    """MACD顶背离 + 均线死叉"""
    df = load_data_with_cache(ticker, 'daily')
    divergence = _macd_divergence_vectorized(df, 20)
    
    death_cross = (df['EMA5'] < df['EMA20']) & (df['EMA5'].shift(1) >= df['EMA20'].shift(1))
    death_cross_forward = death_cross.rolling(3, min_periods=1).max().shift(-2).fillna(0).astype(bool)
    condition = divergence & death_cross_forward
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt) & condition
    result_df = df.loc[mask, ['Date', 'Close', 'EMA5', 'EMA20', 'MACD_DIF', 'MACD_Histogram', 'volume_ratio']].copy()
    if not result_df.empty:
        result_df.rename(columns={'Date': 'Date'}, inplace=True)
    return result_df

def query_macd_divergence_vol_shrink(ticker, start_date, end_date, features_to_show=None):
    """MACD顶背离 + 成交量萎缩"""
    df = load_data_with_cache(ticker, 'daily')
    divergence = _macd_divergence_vectorized(df, 20)
    vol_shrink = df['Volume'] < df['VOL_EMA10'] * 0.8
    condition = divergence & vol_shrink
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt) & condition
    result_df = df.loc[mask, ['Date', 'Close', 'MACD_DIF', 'MACD_Histogram', 'Volume', 'volume_ratio']].copy()
    if not result_df.empty:
        result_df.rename(columns={'Date': 'Date'}, inplace=True)
    return result_df

def query_macd_divergence_death_cross_volume(ticker, start_date, end_date, features_to_show=None):
    """MACD顶背离 + 均线死叉 + 成交量放大破位"""
    df = load_data_with_cache(ticker, 'daily')
    divergence = _macd_divergence_vectorized(df, 20)
    
    death_cross = (df['EMA5'] < df['EMA20']) & (df['EMA5'].shift(1) >= df['EMA20'].shift(1))
    result_idx = []
    
    for idx in df[divergence].index:
        for j in range(idx+1, min(idx+8, len(df))):
            if death_cross.iloc[j]:
                for k in range(j, min(j+5, len(df))):
                    if df.loc[k, 'volume_ratio'] >= 1.5 and df.loc[k, 'Close'] < df.loc[j, 'Close']:
                        result_idx.append(k)
                        break
                break
    
    condition = pd.Series(False, index=df.index)
    if result_idx:
        condition.iloc[result_idx] = True
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt) & condition
    result_df = df.loc[mask, ['Date', 'Close', 'EMA5', 'EMA20', 'MACD_DIF', 'MACD_Histogram', 'volume_ratio']].copy()
    if not result_df.empty:
        result_df.rename(columns={'Date': 'Date'}, inplace=True)
    return result_df

def _rsi_divergence_vectorized(df: pd.DataFrame, lookback: int = 25) -> pd.Series:
    """向量化RSI顶背离检测"""
    n = len(df)
    if n < lookback * 2:
        return pd.Series(False, index=df.index)
    
    rsi_div = pd.Series(False, index=df.index)
    close_values = df['Close'].values
    rsi_values = df['RSI14'].values
    
    for i in range(lookback*2, n):
        window_start = i - lookback
        window_end = i + 1
        
        price_window = close_values[window_start:window_end]
        price_high_idx = window_start + np.argmax(price_window)
        price_high = close_values[price_high_idx]
        rsi_at_high = rsi_values[price_high_idx]
        
        prev_start = max(0, i - 2*lookback)
        prev_end = i - lookback
        if prev_end - prev_start < 5:
            continue
        
        prev_price_window = close_values[prev_start:prev_end]
        prev_price_high_idx = prev_start + np.argmax(prev_price_window)
        prev_price_high = close_values[prev_price_high_idx]
        prev_rsi = rsi_values[prev_price_high_idx]
        
        if prev_price_high > 0 and price_high > prev_price_high * 1.01:
            if rsi_at_high < prev_rsi and rsi_at_high > 60:
                rsi_div.iloc[i] = True
    
    return rsi_div

def query_rsi_divergence_death_cross(ticker, start_date, end_date, features_to_show=None):
    """RSI顶背离 + 均线死叉"""
    df = load_data_with_cache(ticker, 'daily')
    rsi_div = _rsi_divergence_vectorized(df, 25)
    
    death_cross = (df['EMA5'] < df['EMA20']) & (df['EMA5'].shift(1) >= df['EMA20'].shift(1))
    death_cross_forward = death_cross.rolling(5, min_periods=1).max().shift(-4).fillna(0).astype(bool)
    condition = rsi_div & death_cross_forward
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt) & condition
    result_df = df.loc[mask, ['Date', 'Close', 'EMA5', 'EMA20', 'RSI14', 'volume_ratio']].copy()
    if not result_df.empty:
        result_df.rename(columns={'Date': 'Date'}, inplace=True)
    return result_df

def query_rsi_divergence_vol_shrink(ticker, start_date, end_date, features_to_show=None):
    """RSI顶背离 + 成交量萎缩"""
    df = load_data_with_cache(ticker, 'daily')
    rsi_div = _rsi_divergence_vectorized(df, 25)
    vol_shrink = df['Volume'] < df['VOL_EMA10'] * 0.95
    condition = rsi_div & vol_shrink
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt) & condition
    result_df = df.loc[mask, ['Date', 'Close', 'RSI14', 'Volume', 'volume_ratio']].copy()
    if not result_df.empty:
        result_df.rename(columns={'Date': 'Date'}, inplace=True)
    return result_df

def query_rsi_divergence_death_cross_break(ticker, start_date, end_date, features_to_show=None):
    """RSI顶背离 + 均线死叉 + 放量跌破支撑 / 看跌K线"""
    df = load_data_with_cache(ticker, 'daily')
    rsi_div = _rsi_divergence_vectorized(df, 25)
    
    death_cross = (df['EMA5'] < df['EMA20']) & (df['EMA5'].shift(1) >= df['EMA20'].shift(1))
    
    body = (df['Close'] - df['Open']).abs()
    upper_shadow = df['High'] - df[['Open', 'Close']].max(axis=1)
    bearish_candle = (upper_shadow > 2 * body)
    
    prev_body = body.shift(1)
    prev_close = df['Close'].shift(1)
    prev_open = df['Open'].shift(1)
    engulfing = (prev_close > prev_open) & (df['Close'] < df['Open']) & \
                (df['Open'] <= prev_close) & (df['Close'] >= prev_open)
    
    df['bearish_candle'] = bearish_candle | engulfing
    
    result_idx = []
    for idx in df[rsi_div].index:
        death_day = None
        for j in range(idx+1, min(idx+10, len(df))):
            if death_cross.iloc[j]:
                death_day = j
                break
        if death_day is None:
            continue
        for k in range(death_day+1, min(death_day+8, len(df))):
            if (df.loc[k, 'volume_ratio'] >= 1.2 and 
                df.loc[k, 'Close'] < df.loc[death_day, 'Close']) or df.loc[k, 'bearish_candle']:
                result_idx.append(k)
                break
    
    condition = pd.Series(False, index=df.index)
    if result_idx:
        condition.iloc[result_idx] = True
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt) & condition
    result_df = df.loc[mask, ['Date', 'Close', 'EMA5', 'EMA20', 'RSI14', 'volume_ratio']].copy()
    if not result_df.empty:
        result_df.rename(columns={'Date': 'Date'}, inplace=True)
    return result_df

def query_ma_death_cross(ticker, start_date, end_date, features_to_show=None):
    """均线死叉"""
    df = load_data_with_cache(ticker, 'daily')
    death_cross = (df['EMA5'] < df['EMA20']) & (df['EMA5'].shift(1) >= df['EMA20'].shift(1))
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt) & death_cross
    result_df = df.loc[mask, ['Date', 'Close', 'EMA5', 'EMA20', 'volume_ratio']].copy()
    if not result_df.empty:
        result_df.rename(columns={'Date': 'Date'}, inplace=True)
    return result_df

def query_ma_bearish_arrangement(ticker, start_date, end_date, features_to_show=None):
    """空头排列"""
    df = load_data_with_cache(ticker, 'daily')
    mas = [5, 10, 20, 60]
    
    cond_arrange = True
    for i in range(len(mas)-1):
        cond_arrange &= df[f'EMA{mas[i]}'] < df[f'EMA{mas[i+1]}']
    
    cond_down = True
    for m in mas:
        cond_down &= df[f'EMA{m}'] < df[f'EMA{m}'].shift(5)
    
    final_cond = cond_arrange & cond_down
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt) & final_cond
    cols = ['Date', 'Close'] + [f'EMA{m}' for m in mas] + ['volume_ratio']
    result_df = df.loc[mask, cols].copy()
    if not result_df.empty:
        result_df.rename(columns={'Date': 'Date'}, inplace=True)
    return result_df

def query_trendline_break(ticker, start_date, end_date, features_to_show=None):
    """趋势线跌破"""
    df = load_data_with_cache(ticker, 'daily')
    trough_indices = df[df['Local_Min_5']].index.tolist()
    if len(trough_indices) < 2:
        return pd.DataFrame()
    
    signals = []
    for i in range(1, len(trough_indices)):
        p1, p2 = trough_indices[i-1], trough_indices[i]
        if p2 - p1 < 5:
            continue
        
        x1 = df.loc[p1, 'Date'].timestamp()
        y1 = df.loc[p1, 'Low']
        x2 = df.loc[p2, 'Date'].timestamp()
        y2 = df.loc[p2, 'Low']
        if x2 - x1 == 0:
            continue
        
        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - slope * x1
        
        for j in range(p2+1, len(df)):
            curr_date = df.loc[j, 'Date']
            trend_val = slope * curr_date.timestamp() + intercept
            close = df.loc[j, 'Close']
            if close < trend_val:
                signals.append({
                    'Date': curr_date,
                    'Break_Price': round(close, 2),
                    'Trendline_Value': round(trend_val, 2),
                    'Volume_Ratio': round(df.loc[j, 'volume_ratio'], 2),
                    'Point1_Date': df.loc[p1, 'Date'],
                    'Point1_Price': round(y1, 2),
                    'Point2_Date': df.loc[p2, 'Date'],
                    'Point2_Price': round(y2, 2)
                })
                break
    
    if not signals:
        return pd.DataFrame()
    result_df = pd.DataFrame(signals).drop_duplicates(subset='Date').reset_index(drop=True)
    return result_df


# ==================== 并行信号执行器（卖出） ====================
class SellSignalExecutor:
    """并行信号执行器"""
    
    def __init__(self, ticker: str, start_date: str, end_date: str, max_workers: int = 8):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.max_workers = max_workers
        self._signal_functions = self._get_signal_functions()
    
    @staticmethod
    def _get_signal_functions() -> List[Tuple[str, Callable]]:
        """获取所有卖出信号检测函数"""
        indicators = [
            ("头肩顶", query_head_shoulders_top),
            ("圆弧顶", query_rounding_top),
            ("双顶", query_double_top),
            ("三重顶", query_triple_top),
            ("菱形顶", query_diamond_top),
            ("MACD顶背离 + 均线死叉", query_macd_divergence_death_cross),
            ("MACD顶背离 + 成交量萎缩", query_macd_divergence_vol_shrink),
            ("MACD顶背离 + 均线死叉 + 成交量放大破位", query_macd_divergence_death_cross_volume),
            ("RSI顶背离 + 均线死叉", query_rsi_divergence_death_cross),
            ("RSI顶背离 + 成交量萎缩", query_rsi_divergence_vol_shrink),
            ("RSI顶背离 + 均线死叉 + 放量跌破支撑 / 看跌K线", query_rsi_divergence_death_cross_break),
            ("均线死叉", query_ma_death_cross),
            ("空头排列", query_ma_bearish_arrangement),
            ("趋势线跌破", query_trendline_break)
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


# ==================== 批量保存到数据库（卖出） ====================
@retry_on_locked(max_retries=5, delay=0.5, backoff=2.0)
def batch_save_sell_signals_to_db(ticker: str, stock_name: str, signals_df: pd.DataFrame) -> int:
    """批量保存卖出信号到数据库（带重试机制）"""
    if signals_df is None or signals_df.empty:
        return 0
    
    signals_df = sanitize_na_values(signals_df)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hk_sell_signal_details (
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                signal_type TEXT NOT NULL DEFAULT 'sell',
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
        
        cursor.execute("DELETE FROM hk_sell_signal_details WHERE stock_code = ?", (ticker,))
        
        insert_sql = """
            INSERT OR REPLACE INTO hk_sell_signal_details 
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
                details_dict = sanitize_na_values(details_dict)
                details_dict = convert_dates_in_dict(details_dict)
                details_json = json.dumps(details_dict, ensure_ascii=False, default=str)
            else:
                details_json = str(details_dict) if details_dict else ''
            
            batch_data.append((
                ticker, stock_name, 'sell', signal_date_str, signal_name, details_json,
                float(row.get('BaseScore', 0.0)) if row.get('BaseScore') is not None else 0.0,
                float(row.get('ResonanceScore', 0.0)) if row.get('ResonanceScore') is not None else 0.0,
                float(row.get('TrendScore', 0.0)) if row.get('TrendScore') is not None else 0.0,
                float(row.get('VolumeScore', 0.0)) if row.get('VolumeScore') is not None else 0.0,
                float(row.get('CompositeScore', 0.0)) if row.get('CompositeScore') is not None else 0.0,
                now_str
            ))
        
        if batch_data:
            batch_size = 500
            total_saved = 0
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i+batch_size]
                cursor.executemany(insert_sql, batch)
                conn.commit()
                total_saved += len(batch)
            
            logger.info(f"{ticker} 批量保存了 {total_saved} 条卖出信号到数据库 (新加坡时间: {now_str})")
            return total_saved
        
        conn.commit()
        return 0
        
    except Exception as e:
        logger.error(f"保存卖出信号到数据库失败: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise
    finally:
        if conn:
            return_db_connection(conn)


# ==================== PDF 摘要报告生成（卖出） ====================
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

def generate_sell_summary_pdf(ticker: str, start_date: str, end_date: str, 
                              last_3weeks_start, last_3weeks_end, 
                              signals_df: pd.DataFrame, output_path: str):
    """生成卖出信号摘要报告（PDF）"""
    ALLOWED_KEYS = {'Date', 'Close', 'Volume', 'EMA20', 'volume_ratio', 'Break_Price', 
                    'Neckline', 'Volume_Ratio', 'Left_Shoulder_Date', 'Right_Shoulder_Date',
                    'Head_Date', 'MACD_DIF', 'MACD_Histogram', 'RSI14', 'EMA5', 'EMA20',
                    'Trendline_Value', 'Point1_Date', 'Point2_Date', 'Vol_Shrink_Ratio'}

    def format_details(obj):
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

    story.append(Paragraph(f"{ticker} 卖出信号分析报告（摘要）", title_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(f"股票代码：{ticker}", normal_style))
    story.append(Paragraph(f"分析期间：{start_date} 至 {end_date}", normal_style))
    story.append(Paragraph(f"最后3周范围：{last_3weeks_start.strftime('%Y-%m-%d')} 至 {last_3weeks_end.strftime('%Y-%m-%d')}", normal_style))
    story.append(Spacer(1, 0.2*inch))

    if signals_df.empty:
        story.append(Paragraph("最近3周内没有检测到任何卖出信号。", heading_style))
        doc.build(story)
        return

    total_base = signals_df['BaseScore'].sum()
    story.append(Paragraph(f"基础评分总分：{total_base:.2f}", heading_style))
    story.append(Spacer(1, 0.1*inch))

    table_data = [["信号日期", "卖出信号", "基础分", "共振分", "趋势分", "量能分", "综合分", "详情"]]
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

    story.append(Paragraph("综合得分计算方法（卖点模型）", heading_style))
    method_text = """
    综合得分 = 卖点基础分 × 0.4 + 多信号共振 × 0.3 + 大周期趋势 × 0.2 + 成交量验证 × 0.1<br/>
    - 卖点基础分：根据形态类型的可靠性和完美程度预设。<br/>
    - 多信号共振：检测均线死叉、MACD死叉、KDJ死叉、放量下跌、跌破MA20，每项+2分，上限10。<br/>
    - 大周期趋势：依据周线和月线的空头排列程度评分，趋势越弱得分越高。<br/>
    - 成交量验证：用量比（5日均量比）评分，>1.5得10分，1.2-1.5得8分，1.0-1.2得6分，<1.0得3分。
    """
    story.append(Paragraph(method_text, normal_style))
    doc.build(story)


# ==================== 主处理函数 ====================
def process_one_stock_optimized(ticker, start_date, end_date, start_dt, end_dt, report_dir):
    """优化后的单股票处理函数"""
    try:
        start_time_sg = get_singapore_time()
        logger.info(f"[{ticker}] 开始处理 (新加坡时间: {start_time_sg.strftime('%Y-%m-%d %H:%M:%S')})")
        
        stock_name = get_stock_name(ticker)
        logger.info(f"处理股票: {ticker} ({stock_name})")
        
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
        
        executor = SellSignalExecutor(ticker, start_date, end_date, max_workers=8)
        signals_df, detailed_dfs = executor.execute_all()
        
        if not signals_df.empty:
            daily_data = load_data_with_cache(ticker, 'daily')
            
            signals_df['BaseScore'] = signals_df['Signal_Name'].apply(get_sell_base_score)
            signals_df['ResonanceScore'] = signals_df.apply(
                lambda row: compute_sell_resonance_score(row, daily_data), axis=1
            )
            signals_df['TrendScore'] = signals_df['Date'].apply(
                lambda d: compute_sell_trend_score(ticker, d)
            )
            signals_df['VolumeScore'] = signals_df.apply(
                lambda row: compute_sell_volume_score(row, daily_data), axis=1
            )
            signals_df['CompositeScore'] = (
                signals_df['BaseScore'] * 0.4 + 
                signals_df['ResonanceScore'] * 0.3 + 
                signals_df['TrendScore'] * 0.2 + 
                signals_df['VolumeScore'] * 0.1
            )
            
            saved_count = batch_save_sell_signals_to_db(ticker, stock_name, signals_df)
            logger.info(f"[{ticker}] 已保存 {saved_count} 条卖出信号到数据库")
            
            recent_signals = signals_df[
                (signals_df['Date'] >= last_3weeks_start) & 
                (signals_df['Date'] <= last_3weeks_end)
            ]
        else:
            recent_signals = pd.DataFrame()
            logger.info(f"[{ticker}] 未发现任何卖出信号")
        
        summary_path = os.path.join(report_dir, f"{ticker}_sell_signal_analysis_sum.pdf")
        generate_sell_summary_pdf(
            ticker, start_date, end_date,
            last_3weeks_start, last_3weeks_end,
            recent_signals, summary_path
        )
        
        end_time_sg = get_singapore_time()
        elapsed = (end_time_sg - start_time_sg).total_seconds()
        logger.info(f"[{ticker}] 处理完成，发现 {len(recent_signals)} 个近期卖出信号，用时 {elapsed:.2f} 秒 (新加坡时间: {end_time_sg.strftime('%Y-%m-%d %H:%M:%S')})")
        
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


# ==================== 主函数 ====================
def main():
    """主函数 - 参考 Daily_TA5_MergePDF.py 的日志配置方式"""
    global logger
    
    try:
        # ========== 主程序路径配置 ==========        
        # 构建配置文件路径：父目录下的config文件夹中的stock_data_analysis.par
        project_dir = find_project_root()
        config_path = os.path.join(project_dir, 'Config', 'stock_data_analysis.par')

        # ========== 加载配置 ==========
        # 使用load_config函数加载配置
        CONFIG = load_config(config_path, project_dir)
        print(f"配置文件加载成功: {config_path}")

        # 更新全局路径配置
        GlobalConfig.update_paths(CONFIG, project_dir)

        # ========== 初始化日志系统（参考 Daily_TA5_MergePDF.py） ==========
        # 在更新路径后初始化日志系统，使用 GlobalConfig.full_log_dir
        log_filepath = setup_logging(
            GlobalConfig.full_log_dir, 
            "Daily_TA6B_Sell_Signal_Analyzer_Optimized.log"
        )
        
        # 获取logger
        logger = logging.getLogger(__name__)
        
        # ========== 打印配置信息 ==========
        logger.info("=" * 60)
        logger.info("优化版卖出信号分析程序启动")
        logger.info("=" * 60)
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件位置: {config_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"报告目录: {GlobalConfig.full_report_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        logger.info(f"日志文件: {log_filepath}")
        
        # ===== 获取股票列表 =====
        # 优先从配置文件中的 stock_list_data 获取股票列表
        if 'stock_list_data' in CONFIG and CONFIG['stock_list_data']:
            stock_data = CONFIG['stock_list_data']
            if 'stocks' in stock_data:
                tickers = [stock['stock_code'] for stock in stock_data['stocks']]
                logger.info(f"从 stock_list.json 加载了 {len(tickers)} 只股票")
            else:
                tickers = CONFIG.get('tickers', [])
                logger.warning("stock_list.json 中没有 stocks 字段，使用备用列表")
        else:
            tickers = CONFIG.get('tickers', [])
            logger.info(f"从配置文件加载了 {len(tickers)} 只股票")
        
        # 如果 tickers 为空，尝试直接从 stock_list.json 加载
        if not tickers:
            stock_list_path = os.path.join(project_dir, 'Config', 'stock_list.json')
            if os.path.exists(stock_list_path):
                import json
                try:
                    with open(stock_list_path, 'r', encoding='utf-8') as f:
                        stock_data = json.load(f)
                    if 'stocks' in stock_data:
                        tickers = [stock['stock_code'] for stock in stock_data['stocks']]
                        logger.info(f"直接从 stock_list.json 加载了 {len(tickers)} 只股票")
                except Exception as e:
                    logger.error(f"加载 stock_list.json 失败: {e}")
        
        start_date, end_date = get_validated_dates(CONFIG, project_dir)
        
        if not tickers:
            logger.error("没有配置股票代码")
            return
        
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
        logger.info(f"✅ 所有股票卖出信号处理完成，总用时: {elapsed:.2f} 秒")
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