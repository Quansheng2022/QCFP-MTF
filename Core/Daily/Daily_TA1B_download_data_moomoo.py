#!/usr/bin/env python
# coding: utf-8


"""
Daily_TA1B_download_data_moomoo.py
使用Moomoo API下载港股历史日k线交易数据。
支持换手率、涨跌幅、成交额、振幅、涨跌额等全部字段，并统一数值精度。
数据存储：hk_hist_daily_kline, SQLiteDB/HK_Stock.db
"""

import subprocess
import time
import os
import sys
import socket
import traceback
import sqlite3
import json
import configparser
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

import pandas as pd  # <-- 这一行很重要！
import moomoo as ft

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


setup_windows_encoding()

# ==================== 日志配置 ====================
def setup_logger(log_dir: Path, log_filename: str = "Daily_TA1B_download_data_moomoo.log") -> logging.Logger:
    """
    配置日志系统
    
    Args:
        log_dir: 日志目录
        log_filename: 日志文件名
        
    Returns:
        配置好的 Logger 对象
    """
    # 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_path = log_dir / log_filename
    
    # 创建 logger
    logger = logging.getLogger('Daily_TA1B_download_data_moomoo')
    logger.setLevel(logging.INFO)
    
    # 清除已有的处理器（避免重复）
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建文件处理器 - 使用 'w' 模式直接覆盖原有日志文件
    file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')  # 修改这里：添加 mode='w'
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到 logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# ==================== INI 配置加载 ====================
def load_ini_config(config_path: Path) -> configparser.ConfigParser:
    """
    加载 INI 格式的配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        ConfigParser 对象
    """
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    config = configparser.ConfigParser()
    config.read(str(config_path), encoding='utf-8')
    
    return config

def get_config_value(config: configparser.ConfigParser, section: str, key: str, default=None):
    """
    从 INI 配置中获取值
    
    Args:
        config: ConfigParser 对象
        section: 配置段
        key: 键名
        default: 默认值
        
    Returns:
        配置值
    """
    try:
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return default

# ==================== 数据格式化配置 ====================
# 定义各数值列的小数位数（与原有 akshare 输出保持一致）
DECIMAL_MAP = {
    'open': 2,
    'high': 2,
    'low': 2,
    'close': 2,
    'amount': 2,           # 成交额（万元？原格式为元，保留2位）
    'amplitude': 2,        # 振幅（百分比）
    'change_percent': 2,   # 涨跌幅（百分比）
    'change_amount': 2,    # 涨跌额（元）
    'turnover_rate': 2,    # 换手率（百分比数值，原格式如0.32表示0.32%）
    'previous_close': 2
}
VOLUME_COLS = ['volume']   # 成交量保持整数，不 round

def format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """对DataFrame中的数值列进行四舍五入，保持与原有格式一致"""
    df = df.copy()
    for col, decimals in DECIMAL_MAP.items():
        if col in df.columns:
            df[col] = df[col].round(decimals)
    # 成交量转为整数（去除小数）
    for col in VOLUME_COLS:
        if col in df.columns:
            df[col] = df[col].astype('Int64')  # 可空整数类型
    return df

# ==================== SQLite 数据库管理 ====================
class SQLiteManager:
    """SQLite数据库管理类"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """连接数据库"""
        # 确保数据库目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
            
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def create_table(self):
        """创建数据表（根据字段结构）"""
        create_sql = """
        CREATE TABLE IF NOT EXISTS hk_hist_daily_kline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            amplitude REAL,
            change_percent REAL,
            change_amount REAL,
            turnover_rate REAL,
            previous_close REAL
        );
        """
        self.cursor.execute(create_sql)
        self.conn.commit()
        
        # 创建索引以提高查询效率
        index_sqls = [
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_hk_hist_daily_kline ON hk_hist_daily_kline(stock_code, date)",
        ]
        for sql in index_sqls:
            self.cursor.execute(sql)
        self.conn.commit()
        
    def get_existing_dates(self, stock_code: str) -> Set[str]:
        """获取股票已存在的日期集合"""
        sql = "SELECT date FROM hk_hist_daily_kline WHERE stock_code = ?"
        self.cursor.execute(sql, (stock_code,))
        rows = self.cursor.fetchall()
        return {row['date'] for row in rows}
    
    def get_last_date(self, stock_code: str) -> Optional[str]:
        """获取股票最后交易日"""
        sql = "SELECT MAX(date) as last_date FROM hk_hist_daily_kline WHERE stock_code = ?"
        self.cursor.execute(sql, (stock_code,))
        row = self.cursor.fetchone()
        return row['last_date'] if row and row['last_date'] else None
    
    def get_last_close(self, stock_code: str, date: str) -> Optional[float]:
        """获取指定日期之前的最后收盘价"""
        sql = """
        SELECT close FROM hk_hist_daily_kline 
        WHERE stock_code = ? AND date < ? 
        ORDER BY date DESC LIMIT 1
        """
        self.cursor.execute(sql, (stock_code, date))
        row = self.cursor.fetchone()
        return row['close'] if row else None
    
    def insert_data(self, stock_code: str, df: pd.DataFrame, stock_name: str = "") -> int:
        """
        插入数据（使用INSERT OR REPLACE避免重复）
        返回插入的记录数
        """
        if df.empty:
            return 0
        
        # 准备数据
        records = []
        for _, row in df.iterrows():
            # 确保日期格式为 YYYY-MM-DD
            date_str = row['Date']
            if isinstance(date_str, pd.Timestamp):
                date_str = date_str.strftime('%Y-%m-%d')
            elif isinstance(date_str, datetime):
                date_str = date_str.strftime('%Y-%m-%d')
            else:
                # 尝试转换字符串格式
                try:
                    date_str = pd.to_datetime(date_str).strftime('%Y-%m-%d')
                except:
                    date_str = str(date_str)
            
            record = (
                stock_code,
                stock_name,
                date_str,
                float(row['open']) if pd.notna(row['open']) else None,
                float(row['high']) if pd.notna(row['high']) else None,
                float(row['low']) if pd.notna(row['low']) else None,
                float(row['close']) if pd.notna(row['close']) else None,
                float(row['volume']) if pd.notna(row['volume']) else None,
                float(row['amount']) if pd.notna(row['amount']) else None,
                float(row['amplitude']) if pd.notna(row['amplitude']) else None,
                float(row['change_percent']) if pd.notna(row['change_percent']) else None,
                float(row['change_amount']) if pd.notna(row['change_amount']) else None,
                float(row['turnover_rate']) if pd.notna(row['turnover_rate']) else None,
                float(row['previous_close']) if pd.notna(row['previous_close']) else None
            )
            records.append(record)
        
        # 使用 INSERT OR REPLACE 避免重复
        sql = """
        INSERT OR REPLACE INTO hk_hist_daily_kline (
            stock_code, stock_name, date, open, high, low, close,
            volume, amount, amplitude, change_percent, change_amount,
            turnover_rate, previous_close
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            self.cursor.executemany(sql, records)
            self.conn.commit()
            return len(records)
        except sqlite3.Error as e:
            print(f"   数据库插入错误: {e}")
            self.conn.rollback()
            raise
    
    def get_stock_data(self, stock_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """查询股票数据"""
        sql = "SELECT * FROM hk_hist_daily_kline WHERE stock_code = ?"
        params = [stock_code]
        
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
            
        sql += " ORDER BY date"
        
        df = pd.read_sql_query(sql, self.conn, params=params)
        return df
    
    def get_all_stocks(self) -> List[str]:
        """获取所有股票代码列表"""
        sql = "SELECT DISTINCT stock_code FROM hk_hist_daily_kline ORDER BY stock_code"
        df = pd.read_sql_query(sql, self.conn)
        return df['stock_code'].tolist() if not df.empty else []
    
    def get_table_info(self) -> Dict[str, Any]:
        """获取表信息"""
        sql = "SELECT COUNT(*) as count FROM hk_hist_daily_kline"
        self.cursor.execute(sql)
        total = self.cursor.fetchone()['count']
        
        sql = "SELECT COUNT(DISTINCT stock_code) as stock_count FROM hk_hist_daily_kline"
        self.cursor.execute(sql)
        stock_count = self.cursor.fetchone()['stock_count']
        
        return {
            'total_records': total,
            'stock_count': stock_count
        }

# ==================== OpenD 管理 ====================
def start_opend(futu_cfg):
    # OpenD 10.10 起废弃 login_account/login_pwd/login_pwd_md5 配置参数，
    # 启动后默认进入交互式登录。只有之前登录时勾选过“记住密码”，
    # 才能用 -login_account=<账号> -login_by_remember=1 免密自动登录。
    cmd = [
        futu_cfg['opend_exec_path'],
        f"-login_account={futu_cfg['futu_account']}",
        "-login_by_remember=1",
        f"-api_port={futu_cfg['api_port']}",
        "-lang=chs"
    ]
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.Popen(cmd, startupinfo=si)
    else:
        return subprocess.Popen(cmd)

def wait_for_opend(port, timeout=120):
    for _ in range(timeout):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            return True
        time.sleep(1)
    return False

def wait_for_opend_ready(quote_ctx, timeout=120):
    """轮询 OpenD 全局状态，直到行情已登录且程序进入 READY。"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            ret, state = quote_ctx.get_global_state()
            if ret == 0:
                if (state.get('qot_logined') and
                        state.get('program_status_type') == 'READY'):
                    return True, state
        except Exception:
            # OpenD 启动初期连接会被拒绝或关闭，属正常现象，继续等待
            pass
        time.sleep(1)
    return False, None

def silence_moomoo_console(enable=False):
    """开关 moomoo 库的控制台日志（文件日志不受影响）。

    仅移除 stdout handler 无法完全静音（stderr 路径仍会输出），
    因此直接调整 FTConsoleLog 的日志级别，返回原 level 供恢复。
    """
    console_logger = logging.getLogger('FTConsoleLog')
    old_level = console_logger.level
    console_logger.setLevel(logging.INFO if enable else logging.CRITICAL)
    return old_level

# ==================== 数据获取核心函数 ====================
def get_history_kline_with_retry(ctx, symbol, start_date: str, end_date: str,
                                  ktype=ft.KLType.K_DAY, autype=ft.AuType.QFQ,
                                  max_retries=3, retry_delay=2, logger=None) -> pd.DataFrame:
    """
    获取完整的历史K线数据，包含换手率、涨跌幅、成交额等，并转换为统一格式。
    """
    start = start_date.replace('-', '')
    end = end_date.replace('-', '')
    start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
    end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:8]}"

    all_data = []
    page_req_key = None
    max_count = 1000

    for attempt in range(max_retries):
        try:
            while True:
                ret, data, page_req_key = ctx.request_history_kline(
                    symbol,
                    start=start_fmt,
                    end=end_fmt,
                    ktype=ktype,
                    autype=autype,
                    max_count=max_count,
                    page_req_key=page_req_key
                )
                if ret != ft.RET_OK:
                    raise Exception(f"请求失败，错误码：{ret}，消息：{data}")
                if data.empty:
                    break
                all_data.append(data)
                if page_req_key is None:
                    break
                time.sleep(0.5)
            break
        except Exception as e:
            msg = f"获取数据失败 (尝试 {attempt+1}/{max_retries}): {e}"
            if logger:
                logger.warning(msg)
            else:
                print(f"   {msg}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                raise Exception(f"重试 {max_retries} 次后仍失败: {e}")

    if not all_data:
        return pd.DataFrame()

    df = pd.concat(all_data, ignore_index=True)
    df['time_key'] = pd.to_datetime(df['time_key'])
    df.sort_values('time_key', inplace=True)

    # 列映射 - 全部改为小写
    rename_map = {
        'time_key': 'Date',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume',
        'turnover': 'amount',
        'turnover_rate': 'turnover_rate_raw',   # 原始小数（如0.02）
        'change_rate': 'change_percent_raw',    # 原始涨跌幅（如2.5）
        'last_close': 'last_close'
    }
    df.rename(columns=rename_map, inplace=True)

    # 处理换手率：将原始小数转换为百分比数值（乘以100）
    if 'turnover_rate_raw' in df.columns:
        df['turnover_rate'] = df['turnover_rate_raw'] * 100
    else:
        df['turnover_rate'] = None

    # 处理涨跌幅：直接使用（若为百分比数值则保持不变）
    if 'change_percent_raw' in df.columns:
        df['change_percent'] = df['change_percent_raw']
    else:
        df['change_percent'] = None

    # 计算涨跌额
    if 'last_close' in df.columns:
        df['change_amount'] = df['close'] - df['last_close']
    else:
        # 若没有昨收价，使用前一日收盘
        df['change_amount'] = df['close'] - df['close'].shift(1)

    # 计算振幅（百分比）
    if 'last_close' in df.columns and df['last_close'].notna().any():
        df['amplitude'] = (df['high'] - df['low']) / df['last_close'] * 100
    else:
        prev_close = df['close'].shift(1)
        df['amplitude'] = (df['high'] - df['low']) / prev_close * 100

    # 整理最终列（按原有顺序）- 全部改为小写
    final_columns = [
        'Date', 'open', 'high', 'low', 'close', 'volume', 'amount',
        'amplitude', 'change_percent', 'change_amount', 'turnover_rate'
    ]
    for col in final_columns:
        if col not in df.columns:
            df[col] = None

    df = df[final_columns]
    return df

def get_stock_data_moomoo(ticker: str, start_date: str, end_date: str,
                          quote_ctx, max_retries=3, logger=None) -> pd.DataFrame:
    """单个股票数据获取包装函数"""
    symbol = f"HK.{ticker}"
    df = get_history_kline_with_retry(
        quote_ctx, symbol, start_date, end_date,
        ktype=ft.KLType.K_DAY, autype=ft.AuType.QFQ,
        max_retries=max_retries,
        logger=logger
    )
    if df.empty:
        raise ValueError(f"未获取到 {symbol} 在 {start_date}~{end_date} 的数据")
    return df

# ==================== 增量更新与保存（SQLite版本） ====================
def update_stock_data_moomoo(ticker_list, start_date, end_date, db_manager: SQLiteManager,
                             quote_ctx, max_retries=3, stock_names: Dict[str, str] = None,
                             logger=None):
    """
    更新股票数据到SQLite数据库，支持增量下载，并自动格式化数值精度。
    
    Args:
        ticker_list: 股票代码列表
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
        db_manager: SQLite数据库管理器
        quote_ctx: Moomoo报价上下文
        max_retries: 最大重试次数
        stock_names: 股票名称映射 {code: name}
        logger: 日志记录器
    """
    failed_tickers = []
    final_col_order = [
        'Date', 'open', 'high', 'low', 'close', 'volume', 'amount',
        'amplitude', 'change_percent', 'change_amount', 'turnover_rate', 'previous_close'
    ]
    
    stock_names = stock_names or {}

    for ticker in ticker_list:
        try:
            # 获取数据库中该股票的最后日期
            last_date = db_manager.get_last_date(ticker)
            
            # 确定是否需要下载
            if last_date is None:
                need_start = start_date
                msg = f"{ticker} 无历史数据，全量下载 {start_date} ~ {end_date}"
                if logger:
                    logger.info(msg)
                else:
                    print(f"  📊 {msg}")
            else:
                # 最后日期加1天作为开始日期
                last_date_obj = datetime.strptime(last_date, '%Y-%m-%d')
                need_start = (last_date_obj + timedelta(days=1)).strftime("%Y%m%d")
                
                if need_start > end_date:
                    msg = f"{ticker} 数据已是最新 (最后日期: {last_date})"
                    if logger:
                        logger.info(msg)
                    else:
                        print(f"  ✅ {msg}")
                    continue
                msg = f"{ticker} 增量更新：从 {need_start} 到 {end_date} (最后日期: {last_date})"
                if logger:
                    logger.info(msg)
                else:
                    print(f"  📈 {msg}")

            # 下载数据
            try:
                df_new = get_stock_data_moomoo(ticker, need_start, end_date, quote_ctx, max_retries, logger)
            except ValueError as e:
                # 如果没有获取到数据，记录日志并继续
                msg = f"{ticker} 从 {need_start} 后无最新数据"
                if logger:
                    logger.warning(msg)
                else:
                    print(f"  ⚠️ {msg}")
                failed_tickers.append(ticker)
                continue

            if df_new.empty:
                msg = f"{ticker} 从 {need_start} 后无最新数据"
                if logger:
                    logger.warning(msg)
                else:
                    print(f"  ⚠️ {msg}")
                failed_tickers.append(ticker)
                continue

            # 添加 previous_close 列
            if last_date is not None:
                # 获取数据库中最后一条记录的收盘价作为前一日收盘价
                last_close_old = db_manager.get_last_close(ticker, need_start)
                if last_close_old is not None:
                    df_new['previous_close'] = df_new['close'].shift(1)
                    df_new.loc[df_new.index[0], 'previous_close'] = last_close_old
                else:
                    df_new['previous_close'] = df_new['close'].shift(1)
            else:
                df_new['previous_close'] = df_new['close'].shift(1)

            # 确保列顺序
            df_new = df_new[final_col_order]

            # 应用数值格式化（四舍五入）
            df_new = format_dataframe(df_new)
            
            # 日期格式转换（确保为YYYY-MM-DD格式）
            df_new['Date'] = pd.to_datetime(df_new['Date']).dt.strftime('%Y-%m-%d')

            # 获取股票名称
            stock_name = stock_names.get(ticker, '')

            # 插入数据库
            inserted_count = db_manager.insert_data(ticker, df_new, stock_name)
            msg = f"{ticker} 成功插入 {inserted_count} 条数据到数据库"
            if logger:
                logger.info(msg)
            else:
                print(f"  ✅ {msg}")

        except Exception as e:
            error_msg = f"处理 {ticker} 失败: {e}"
            if logger:
                logger.error(error_msg)
                logger.error(traceback.format_exc())
            else:
                print(f"  ❌ {error_msg}")
                traceback.print_exc()
            failed_tickers.append(ticker)

    return failed_tickers

def load_stock_names_from_json(json_path: Path) -> Dict[str, str]:
    """
    专门从 stock_list.json 加载股票名称
    
    Args:
        json_path: stock_list.json 文件路径
        
    Returns:
        股票名称映射字典 {code: name}
    """
    stock_names = {}
    
    if not json_path.exists():
        print(f"⚠️ 文件不存在: {json_path}")
        return stock_names
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 处理您的 JSON 格式 - 使用 stock_code 和 stock_name
        if isinstance(data, dict) and 'stocks' in data:
            for stock in data['stocks']:
                code = stock.get('stock_code')  # 修改为 stock_code
                name = stock.get('stock_name')  # 修改为 stock_name
                if code and name:
                    stock_names[code] = name
        else:
            print(f"⚠️ JSON 格式不符合预期: 缺少 'stocks' 键")
            
        print(f"✅ 成功加载 {len(stock_names)} 个股票名称")
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析错误: {e}")
    except Exception as e:
        print(f"❌ 加载股票名称失败: {e}")
        
    return stock_names
    
# ==================== 解析股票列表 ====================
def parse_tickers(tickers_str: str) -> List[str]:
    """
    解析股票列表字符串，支持逗号分隔
    
    Args:
        tickers_str: 股票列表字符串，如 "00788,00371,02202"
        
    Returns:
        股票代码列表
    """
    if not tickers_str:
        return []
    
    # 按逗号分割，去除空白，过滤空字符串
    tickers = [t.strip() for t in tickers_str.split(',') if t.strip()]
    return tickers

# ==================== 主函数 ====================
def main():
    # 配置文件路径
    config_path = project_dir / "config" / "stock_data_analysis.par"
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)

    # 加载 INI 配置
    try:
        config = load_ini_config(config_path)
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        sys.exit(1)

    # 获取日志目录
    log_dir_str = get_config_value(config, 'FOLDERS', 'log_dir', 'Log')
    log_dir = project_dir / log_dir_str
    
    # 设置日志
    logger = setup_logger(log_dir, "Daily_TA1B_download_data_moomoo.log")
    logger.info("=" * 60)
    logger.info("开始执行 Daily_TA1B_download_data_moomoo")
    logger.info("=" * 60)

    # 获取股票列表
    tickers_str = get_config_value(config, 'TICKERS', 'tickers', '')
    tickers = parse_tickers(tickers_str)
    
    if not tickers:
        logger.error("配置文件中未找到股票列表 (TICKERS -> tickers)")
        logger.error("请检查配置文件格式，确保包含 [TICKERS] 段和 tickers 键")
        sys.exit(1)

    logger.info(f"待下载股票数量: {len(tickers)}")
    logger.info(f"股票列表: {', '.join(tickers)}")

    # 获取数据库配置
    db_name = get_config_value(config, 'DATABASE', 'db_name', 'HK_Stock.db')
    sqlite_dir = get_config_value(config, 'FOLDERS', 'sqlite_dir', 'SQLiteDB')
    
    # 在主函数中加载股票名称
    stock_list_path = project_dir / "Config" / "stock_list.json"
    stock_names = load_stock_names_from_json(stock_list_path)
    
    # 数据库路径
    db_path = project_dir / sqlite_dir / db_name
    logger.info(f"数据库路径: {db_path}")

    # 获取 Moomoo 配置
    moomoo_cfg = {
        'futu_account': get_config_value(config, 'FUTU_MOOMOO', 'futu_account', ''),
        'futu_pwd_md5': get_config_value(config, 'FUTU_MOOMOO', 'futu_pwd_md5', ''),
        'opend_exec_path': get_config_value(config, 'FUTU_MOOMOO', 'opend_exec_path', ''),
        'api_host': get_config_value(config, 'FUTU_MOOMOO', 'api_host', '127.0.0.1'),
        'api_port': int(get_config_value(config, 'FUTU_MOOMOO', 'api_port', 11111))
    }

    missing = [k for k in ['futu_account', 'opend_exec_path'] if not moomoo_cfg.get(k)]
    if missing:
        logger.error(f"配置缺少 Moomoo 必要字段: {missing}")
        logger.error("请在配置文件 [FUTU_MOOMOO] 段中添加以下字段:")
        logger.error("   - futu_account: 富途账号")
        logger.error("   - futu_account: 富途账号")
        logger.error("   - opend_exec_path: OpenD 可执行文件路径")
        logger.error("   - opend_exec_path: OpenD 可执行文件路径")
        sys.exit(1)

    # ==================== 关键修改：数据下载日期配置 ====================
    # 1. 从 [DATA_DOWNLOAD] 段读取数据下载起始日期（专门用于数据下载）
    download_start_str = get_config_value(config, 'DATA_DOWNLOAD', 'download_start_date', '2010-01-01')
    try:
        download_start_obj = datetime.strptime(download_start_str, '%Y-%m-%d')
        download_start_date = download_start_obj.strftime('%Y%m%d')  # 格式化为 YYYYMMDD
        logger.info(f"数据下载起始日期（从 [DATA_DOWNLOAD] 读取）: {download_start_str}")
    except ValueError:
        download_start_date = '20100101'
        logger.warning(f"数据下载起始日期格式错误: {download_start_str}，使用默认值: 20100101")

    # 2. 从 [ANALYSIS_PERIOD] 段读取分析周期（仅用于分析，不影响数据下载）
    analysis_start_str = get_config_value(config, 'ANALYSIS_PERIOD', 'start_date', '2010-01-01')
    analysis_end_str = get_config_value(config, 'ANALYSIS_PERIOD', 'end_date', '')
    logger.info(f"分析周期配置: {analysis_start_str} ~ {analysis_end_str} (仅用于分析，不影响数据下载)")

    # 3. 计算数据下载结束日期
    now = datetime.now()
    if analysis_end_str:  # 如果配置了结束日期，使用配置值
        try:
            end_date_obj = datetime.strptime(analysis_end_str, '%Y-%m-%d')
            end_date = end_date_obj.strftime('%Y%m%d')
            logger.info(f"数据下载结束日期（从 [ANALYSIS_PERIOD] 读取）: {analysis_end_str}")
        except ValueError:
            end_date = now.strftime('%Y%m%d')
            logger.warning(f"数据下载结束日期格式错误: {analysis_end_str}，使用当前日期: {end_date}")
    else:
        # 如果没有指定结束日期，根据当前时间计算
        cutoff_time = datetime.now().replace(hour=16, minute=15).time()
        if now.weekday() < 5 and now.time() < cutoff_time:
            end_date = (now - timedelta(days=1)).strftime('%Y%m%d')
            logger.info(f"交易日内未收盘，下载数据至昨天: {end_date}")
        else:
            end_date = now.strftime('%Y%m%d')
            logger.info(f"已收盘或周末，下载数据至今天: {end_date}")

    logger.info(f"=" * 60)
    logger.info(f"数据下载范围: {download_start_date} ~ {end_date}")
    logger.info(f"数据下载起始日期来源: [DATA_DOWNLOAD] download_start_date = {download_start_str}")
    logger.info(f"=" * 60)

    # 启动 OpenD
    logger.info("启动 OpenD ...")
    opend_process = start_opend(moomoo_cfg)
    logger.info("等待 OpenD 就绪 ...")
    if not wait_for_opend(moomoo_cfg['api_port'], timeout=120):
        logger.error("OpenD 启动超时")
        opend_process.terminate()
        sys.exit(1)
    logger.info("OpenD 已就绪")

    # 端口监听不代表 API 已就绪：OpenD 启动后还需完成登录/初始化（约几秒~几十秒）。
    # 用一次预热连接等 OpenD 真正 READY 后再关闭，主连接就能第一次成功。
    # 预热期间库内部的首连被拒/重连/关闭属正常现象，临时静音 moomoo 控制台日志。
    logger.info("⏳ 预热连接：等待 OpenD 登录完成并进入 READY ...")
    old_log_level = silence_moomoo_console(False)
    try:
        warm_ctx = ft.OpenQuoteContext(host=moomoo_cfg['api_host'], port=moomoo_cfg['api_port'])
        warm_ready, _ = wait_for_opend_ready(warm_ctx, timeout=120)
        warm_ctx.close()
        time.sleep(1)
        if not warm_ready:
            logger.warning("⚠️ OpenD 未在预期时间内进入 READY，仍尝试主连接 ...")
    finally:
        logging.getLogger('FTConsoleLog').setLevel(old_log_level)

    quote_ctx = None
    try:
        quote_ctx = ft.OpenQuoteContext(host=moomoo_cfg['api_host'], port=moomoo_cfg['api_port'])
        
        # 使用SQLite数据库
        with SQLiteManager(db_path) as db_manager:
            # 创建表
            db_manager.create_table()
            logger.info("数据库表创建成功")
            
            logger.info(f"开始下载港股历史数据... (股票数量: {len(tickers)})")
            # ====== 关键修改：使用 download_start_date 而不是 analysis_start_date ======
            failed = update_stock_data_moomoo(
                tickers, download_start_date, end_date, db_manager, 
                quote_ctx, max_retries=3, stock_names=stock_names,
                logger=logger
            )

            if failed:
                logger.warning(f"以下股票下载失败: {failed}")
            else:
                logger.info("所有股票数据下载完成！")
            
            # 显示统计信息
            logger.info("数据库统计信息:")
            table_info = db_manager.get_table_info()
            logger.info(f"   总记录数: {table_info['total_records']:,}")
            logger.info(f"   股票数量: {table_info['stock_count']}")
            
            # 显示各股票的数据量
            logger.info("各股票数据量:")
            for ticker in tickers:
                if ticker not in failed:
                    df = db_manager.get_stock_data(ticker)
                    if not df.empty:
                        name = stock_names.get(ticker, '')
                        name_str = f" ({name})" if name else ""
                        logger.info(f"   {ticker}{name_str}: {len(df):,} 条记录 "
                                   f"({df['date'].min()} ~ {df['date'].max()})")

    except Exception as e:
        logger.error(f"程序异常: {e}")
        logger.error(traceback.format_exc())
    finally:
        if quote_ctx:
            quote_ctx.close()
        opend_process.terminate()
        logger.info("OpenD 已关闭")
        logger.info("=" * 60)
        logger.info("程序执行完成")
        logger.info("=" * 60)

if __name__ == "__main__":
    main()
