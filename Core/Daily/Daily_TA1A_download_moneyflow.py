#!/usr/bin/env python
# coding: utf-8

"""
Daily_TA1A_download_moneyflow.py
Step 1: Download moneyflow data + Capital Distribution data
"""

import subprocess
import time
import os
import sys
import socket
import traceback
import sqlite3
import logging
from datetime import datetime, date, time as tm, timedelta
from pathlib import Path
from typing import Optional, Set, Dict, List, Any, Tuple

import pandas as pd
import moomoo as ft

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
    )
except ImportError as e:
    print("=" * 60)
    print("❌ 严重错误：无法导入 utl.stock_analysis_utl 模块")
    print(f"   期望路径: {core_dir / 'utl' / 'stock_analysis_utl.py'}")
    print(f"   详细错误: {e}")
    print("=" * 60)
    sys.exit(1)

setup_windows_encoding()

# ==================== 日志配置 ====================
def setup_logger(log_dir: Path, log_filename: str = "Daily_TA1A_download_moneyflow.log") -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_filename
    
    logger = logging.getLogger('Daily_TA1A_download_moneyflow')
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        logger.handlers.clear()
    
    file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# ==================== SQLite 数据库管理 ====================
class SQLiteMoneyflowManager:
    REQUIRED_COLUMNS = {
        'capital_in_super': 'REAL',
        'capital_in_big': 'REAL',
        'capital_in_mid': 'REAL',
        'capital_in_small': 'REAL',
        'capital_out_super': 'REAL',
        'capital_out_big': 'REAL',
        'capital_out_mid': 'REAL',
        'capital_out_small': 'REAL'
    }
    
    def __init__(self, db_path: Path, logger: logging.Logger = None):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.logger = logger
        
    def log(self, msg: str, level: str = "info"):
        if self.logger:
            getattr(self.logger, level)(msg)
        else:
            print(msg)
        
    def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
            
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def get_table_columns(self, table_name: str) -> Set[str]:
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            rows = self.cursor.fetchall()
            return {row['name'] for row in rows}
        except Exception as e:
            self.log(f"获取表结构失败: {e}", "error")
            return set()
    
    def add_column_if_not_exists(self, table_name: str, column_name: str, column_type: str):
        try:
            existing_columns = self.get_table_columns(table_name)
            if column_name not in existing_columns:
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                self.cursor.execute(alter_sql)
                self.conn.commit()
                self.log(f"   ✅ 添加列: {column_name} ({column_type})")
                return True
            return False
        except Exception as e:
            self.log(f"   ❌ 添加列 {column_name} 失败: {e}", "error")
            return False
    
    def ensure_columns_exist(self, table_name: str) -> bool:
        try:
            self.log(f"🔧 检查表 {table_name} 的列结构...")
            existing_columns = self.get_table_columns(table_name)
            self.log(f"   现有列数: {len(existing_columns)}")
            
            added_count = 0
            for col_name, col_type in self.REQUIRED_COLUMNS.items():
                if col_name not in existing_columns:
                    if self.add_column_if_not_exists(table_name, col_name, col_type):
                        added_count += 1
            
            if added_count > 0:
                self.log(f"   ✅ 成功添加 {added_count} 个缺失的列")
            else:
                self.log(f"   ✅ 所有必需的列都已存在")
            
            final_columns = self.get_table_columns(table_name)
            all_exist = all(col in final_columns for col in self.REQUIRED_COLUMNS.keys())
            
            if not all_exist:
                missing = [col for col in self.REQUIRED_COLUMNS.keys() if col not in final_columns]
                self.log(f"   ⚠️ 仍有缺失的列: {missing}", "warning")
                return False
            return True
        except Exception as e:
            self.log(f"   ❌ 确保列存在失败: {e}", "error")
            return False
        
    def create_table(self):
        create_sql = """
        CREATE TABLE IF NOT EXISTS hk_hist_daily_moneyflow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            date TEXT NOT NULL,
            Price_ChgPct REAL,
            Capital_Trend REAL,
            Extra_Large REAL,
            Large REAL,
            Medium REAL,
            Small REAL,
            capital_in_super REAL,
            capital_in_big REAL,
            capital_in_mid REAL,
            capital_in_small REAL,
            capital_out_super REAL,
            capital_out_big REAL,
            capital_out_mid REAL,
            capital_out_small REAL
        )
        """
        self.cursor.execute(create_sql)
        self.conn.commit()
        
        index_sql = """
        CREATE INDEX IF NOT EXISTS idx_mf_stock_date 
        ON hk_hist_daily_moneyflow(stock_code, date)
        """
        self.cursor.execute(index_sql)
        self.conn.commit()
        
        self.log(f"数据表 hk_hist_daily_moneyflow 已就绪")
        self.ensure_columns_exist('hk_hist_daily_moneyflow')
    
    def get_last_date(self, stock_code: str) -> Optional[str]:
        sql = "SELECT MAX(date) as last_date FROM hk_hist_daily_moneyflow WHERE stock_code = ?"
        self.cursor.execute(sql, (stock_code,))
        row = self.cursor.fetchone()
        return row['last_date'] if row and row['last_date'] else None
    
    def get_first_date(self, stock_code: str) -> Optional[str]:
        """获取股票最早交易日"""
        sql = "SELECT MIN(date) as first_date FROM hk_hist_daily_moneyflow WHERE stock_code = ?"
        self.cursor.execute(sql, (stock_code,))
        row = self.cursor.fetchone()
        return row['first_date'] if row and row['first_date'] else None
    
    def get_date_count(self, stock_code: str) -> int:
        sql = "SELECT COUNT(*) as count FROM hk_hist_daily_moneyflow WHERE stock_code = ?"
        self.cursor.execute(sql, (stock_code,))
        row = self.cursor.fetchone()
        return row['count'] if row else 0
    
    def record_exists(self, stock_code: str, date: str) -> bool:
        sql = "SELECT COUNT(*) as count FROM hk_hist_daily_moneyflow WHERE stock_code = ? AND date = ?"
        self.cursor.execute(sql, (stock_code, date))
        row = self.cursor.fetchone()
        return row['count'] > 0 if row else False
        
    def insert_batch_data(self, stock_code: str, stock_name: str, 
                          data_list: List[Tuple[Dict, Dict]]) -> int:
        inserted_count = 0
        
        try:
            for flow_data, dist_data in data_list:
                date_str = flow_data['Date'].strftime('%Y-%m-%d')
                
                if self.record_exists(stock_code, date_str):
                    continue
                
                sql = """
                INSERT INTO hk_hist_daily_moneyflow (
                    stock_code, stock_name, date, Price_ChgPct, Capital_Trend,
                    Extra_Large, Large, Medium, Small,
                    capital_in_super, capital_in_big, capital_in_mid, capital_in_small,
                    capital_out_super, capital_out_big, capital_out_mid, capital_out_small
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                values = (
                    stock_code,
                    stock_name,
                    date_str,
                    flow_data.get('Price_ChgPct'),
                    flow_data.get('Capital_Trend'),
                    flow_data.get('Extra_Large'),
                    flow_data.get('Large'),
                    flow_data.get('Medium'),
                    flow_data.get('Small'),
                    dist_data.get('capital_in_super'),
                    dist_data.get('capital_in_big'),
                    dist_data.get('capital_in_mid'),
                    dist_data.get('capital_in_small'),
                    dist_data.get('capital_out_super'),
                    dist_data.get('capital_out_big'),
                    dist_data.get('capital_out_mid'),
                    dist_data.get('capital_out_small')
                )
                
                self.cursor.execute(sql, values)
                inserted_count += 1
            
            self.conn.commit()
        except sqlite3.Error as e:
            self.log(f"   批量插入数据库错误: {e}", "error")
            self.conn.rollback()
            inserted_count = 0
            
        return inserted_count
    
    def get_statistics(self) -> Dict[str, Any]:
        try:
            sql = """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT stock_code) as stock_count,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM hk_hist_daily_moneyflow
            """
            self.cursor.execute(sql)
            row = self.cursor.fetchone()
            if row:
                return {
                    'total_records': row['total_records'],
                    'stock_count': row['stock_count'],
                    'earliest_date': row['earliest_date'],
                    'latest_date': row['latest_date']
                }
            return {}
        except Exception as e:
            self.log(f"获取统计信息失败: {e}", "error")
            return {}

# ==================== OpenD 管理 ====================
def start_opend(futu_cfg):
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
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            ret, state = quote_ctx.get_global_state()
            if ret == 0:
                if (state.get('qot_logined') and
                        state.get('program_status_type') == 'READY'):
                    return True, state
        except Exception:
            pass
        time.sleep(1)
    return False, None

def silence_moomoo_console(enable=False):
    console_logger = logging.getLogger('FTConsoleLog')
    old_level = console_logger.level
    console_logger.setLevel(logging.INFO if enable else logging.CRITICAL)
    return old_level

# ==================== 资金流获取 ====================

FLOW_FIELD_MAP = {
    "Capital_Trend": "in_flow",
    "Extra_Large": "super_in_flow",
    "Large": "big_in_flow",
    "Medium": "mid_in_flow",
    "Small": "sml_in_flow",
}

try:
    PERIOD_TYPE_DAY = ft.PeriodType.DAY
except AttributeError:
    from moomoo.common.constant import PeriodType
    PERIOD_TYPE_DAY = PeriodType.DAY

MAX_DAYS_PER_QUERY = 365


def fetch_daily_capital_flow(ctx, symbol, start_date, end_date, logger=None, mode="auto") -> Tuple[pd.DataFrame, str]:
    """
    获取指定股票在 [start_date, end_date] 区间内的每日资金流数据。

    重要：
    - DAY 是“历史每日资金流”接口，适合本程序的数据库下载。
    - INTRADAY 只返回最新交易日的 5 分钟资金流，不能作为历史日期的回退方案。
      原程序在 DAY 失败后回退 INTRADAY，导致请求 2010 年等历史区间时，
      接口实际返回 2026-08-21 当日数据，最终每个批次都只留下 1 条最新记录。
    """
    if isinstance(start_date, date):
        start_d = start_date
    else:
        start_d = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()

    if isinstance(end_date, date):
        end_d = end_date
    else:
        end_d = datetime.strptime(str(end_date)[:10], "%Y-%m-%d").date()

    if start_d > end_d:
        return pd.DataFrame(), ""

    start_dash = start_d.strftime("%Y-%m-%d")
    end_dash = end_d.strftime("%Y-%m-%d")

    # 历史每日资金流必须使用 DAY。
    # 注意：Moomoo/Futu 的 INTRADAY 仅支持最新交易日，因此绝不能用于历史补数。
    if mode == "intraday":
        if logger:
            logger.warning(
                "   ⚠️ 已禁止 INTRADAY 用于历史每日资金流下载；"
                "INTRADAY 仅返回最新交易日，可能造成历史日期错位。"
            )
        return pd.DataFrame(), ""

    if logger:
        logger.info(f"   📊 尝试 DAY 周期获取每日资金流: {start_dash} 至 {end_dash}")

    try:
        ret, raw_df = ctx.get_capital_flow(
            symbol,
            period_type=PERIOD_TYPE_DAY,
            start=start_dash,
            end=end_dash,
        )
    except Exception as e:
        if logger:
            logger.warning(f"      ⚠️ DAY 周期调用异常: {e}")
        return pd.DataFrame(), ""

    if ret != 0 or raw_df is None or raw_df.empty:
        if logger:
            logger.info(f"      ⚠️ DAY 周期失败或为空: ret={ret}")
        return pd.DataFrame(), ""

    if logger:
        logger.info(f"      ✅ DAY 周期返回 {len(raw_df)} 行")

    try:
        result = process_capital_flow_data(raw_df, logger)
    except Exception as e:
        if logger:
            logger.warning(f"      ⚠️ DAY 数据处理失败: {e}")
        return pd.DataFrame(), ""

    # 强制校验 API 实际返回日期必须落在本批次请求范围内。
    # 这是防止“接口忽略历史日期参数而返回最新数据”的最后一道防线。
    if not result.empty:
        result_dates = pd.to_datetime(result["Date"]).dt.date
        valid_mask = (result_dates >= start_d) & (result_dates <= end_d)
        outside_count = int((~valid_mask).sum())

        if outside_count:
            if logger:
                logger.warning(
                    f"      ⚠️ API 返回 {outside_count} 条请求范围外记录，"
                    f"请求 {start_dash}~{end_dash}，实际 {result['Date'].min()}~{result['Date'].max()}"
                )
            result = result.loc[valid_mask].copy().reset_index(drop=True)

        if result.empty:
            if logger:
                logger.warning(
                    "      ⚠️ API 没有返回请求区间内的历史每日资金流；"
                    "该日期可能已超出 Moomoo/Futu 资金流接口可提供的历史范围。"
                )
            return pd.DataFrame(), ""

    return result, "DAY"

def process_capital_flow_data(raw_df, logger=None) -> pd.DataFrame:
    """
    处理资金流原始数据，按日聚合
    """
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()
    
    df = raw_df.copy()
    
    if 'capital_flow_item_time' not in df.columns:
        if logger:
            logger.warning("原始数据中没有 capital_flow_item_time 列")
        return pd.DataFrame()
    
    # 提取日期
    df["date_only"] = pd.to_datetime(df["capital_flow_item_time"]).dt.date
    
    # 按日期分组，取每天最后一条记录（当日累计值）
    df = df.sort_values("capital_flow_item_time")
    daily = df.groupby("date_only", as_index=False).last()

    result = pd.DataFrame({"Date": daily["date_only"]})
    for db_col, api_col in FLOW_FIELD_MAP.items():
        if api_col in daily.columns:
            result[db_col] = daily[api_col]
        else:
            result[db_col] = None

    result["Date"] = pd.to_datetime(result["Date"]).dt.strftime("%Y-%m-%d")
    result = result.sort_values("Date").reset_index(drop=True)
    
    if result.empty:
        raise RuntimeError("在该日期范围内没有可用的交易日数据")
    
    if logger:
        logger.info(f"      📊 聚合后: {len(result)} 个交易日")
    
    return result


def fetch_daily_capital_flow_batch(ctx, symbol, start_date, end_date, logger=None, mode="auto") -> pd.DataFrame:
    """
    分批获取指定股票在 [start_date, end_date] 内的每日资金流。

    每批最多 365 个自然日。只使用 DAY 历史接口。
    不再使用 INTRADAY 回退，因为 INTRADAY 仅返回最新交易日。
    """
    if start_date > end_date:
        if logger:
            logger.warning("起始日期 > 结束日期，无数据需要下载")
        return pd.DataFrame()

    delta_days = (end_date - start_date).days
    if logger:
        logger.info(f"   📅 总跨度: {delta_days + 1} 天")

    all_dfs = []
    current_start = start_date
    batch_num = 1

    while current_start <= end_date:
        current_end = min(
            current_start + timedelta(days=MAX_DAYS_PER_QUERY - 1),
            end_date
        )

        batch_days = (current_end - current_start).days + 1
        if logger:
            logger.info(
                f"   📦 批次 {batch_num}: {current_start} 至 {current_end} ({batch_days}天)"
            )

        try:
            df, used_mode = fetch_daily_capital_flow(
                ctx, symbol, current_start, current_end, logger, mode="day"
            )

            if not df.empty:
                # 再次限定日期范围，避免接口异常返回其他日期。
                dates = pd.to_datetime(df["Date"]).dt.date
                df = df.loc[(dates >= current_start) & (dates <= current_end)].copy()

                if not df.empty:
                    all_dfs.append(df)
                    if logger:
                        logger.info(
                            f"      ✅ 批次 {batch_num} 获取 {len(df)} 条记录 "
                            f"(日期 {df['Date'].min()}~{df['Date'].max()})"
                        )
                else:
                    if logger:
                        logger.info(f"      ⚠️ 批次 {batch_num} 没有区间内数据")
            else:
                if logger:
                    logger.info(
                        f"      ⚠️ 批次 {batch_num} 无数据"
                        f"（该区间可能超出资金流接口历史可用范围）"
                    )

        except Exception as e:
            if logger:
                logger.warning(f"      ⚠️ 批次 {batch_num} 失败: {e}")

        current_start = current_end + timedelta(days=1)
        batch_num += 1
        time.sleep(0.3)

    if not all_dfs:
        if logger:
            logger.warning("所有批次均未获取到有效数据")
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)
    combined["Date"] = pd.to_datetime(combined["Date"]).dt.strftime("%Y-%m-%d")
    combined = (
        combined.drop_duplicates(subset=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )

    if logger:
        logger.info(
            f"   ✅ 合并后共 {len(combined)} 条记录 "
            f"(来自 {len(all_dfs)} 个成功批次)"
        )

    return combined

def get_historical_moneyflow(ctx, symbol, start_date: str, end_date: str, 
                             logger=None) -> List[Dict]:
    """
    获取历史资金流数据
    """
    try:
        if logger:
            logger.info(f"   请求资金流数据: {start_date} 至 {end_date}")
        
        start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        daily_df = fetch_daily_capital_flow_batch(
            ctx, symbol, start_d, end_d, logger, mode="day"
        )
        
        if daily_df.empty:
            if logger:
                logger.warning(f"   未获取到资金流数据")
            return []
        
        result = []
        for _, row in daily_df.iterrows():
            record = {
                'Date': datetime.strptime(row['Date'], '%Y-%m-%d').date(),
                'Capital_Trend': row['Capital_Trend'],
                'Extra_Large': row['Extra_Large'],
                'Large': row['Large'],
                'Medium': row['Medium'],
                'Small': row['Small']
            }
            result.append(record)
        
        return result
        
    except Exception as e:
        if logger:
            logger.error(f"获取历史资金流数据失败 {symbol}: {e}")
            logger.error(traceback.format_exc())
        return []
        

def get_latest_capital_distribution(ctx, symbol, logger=None):
    """
    获取最新资金流分布原始数据
    """
    try:
        ret, dist_data = ctx.get_capital_distribution(symbol)
        if ret != 0 or dist_data.empty:
            if logger:
                logger.warning(f"   获取资金分布数据失败，错误码：{ret}")
            return None

        last = dist_data.iloc[-1]
        trade_date = pd.to_datetime(last['update_time']).date()

        return {
            'Date': trade_date,
            'capital_in_super': last['capital_in_super'],
            'capital_in_big': last['capital_in_big'],
            'capital_in_mid': last['capital_in_mid'],
            'capital_in_small': last['capital_in_small'],
            'capital_out_super': last['capital_out_super'],
            'capital_out_big': last['capital_out_big'],
            'capital_out_mid': last['capital_out_mid'],
            'capital_out_small': last['capital_out_small']
        }
    except Exception as e:
        if logger:
            logger.error(f"获取最新资金分布数据失败 {symbol}: {e}")
        return None

def merge_flow_and_distribution(flow_list: List[Dict], dist_data: Dict, logger=None) -> List[Tuple[Dict, Dict]]:
    """
    合并资金流和资金分布数据
    """
    result = []
    
    if not flow_list:
        return result
    
    sorted_flows = sorted(flow_list, key=lambda x: x['Date'])
    dist_date = dist_data.get('Date') if dist_data else None
    
    for flow in sorted_flows:
        flow_date = flow['Date']
        
        if dist_date and dist_date == flow_date:
            result.append((flow, dist_data))
        else:
            empty_dist = {
                'Date': flow_date,
                'capital_in_super': None,
                'capital_in_big': None,
                'capital_in_mid': None,
                'capital_in_small': None,
                'capital_out_super': None,
                'capital_out_big': None,
                'capital_out_mid': None,
                'capital_out_small': None
            }
            result.append((flow, empty_dist))
    
    return result

# ==================== 加载股票名称 ====================
def load_stock_names(project_dir: Path) -> Dict[str, str]:
    stock_names = {}
    stock_list_path = project_dir / "Config" / "stock_list.json"
    
    if stock_list_path.exists():
        try:
            import json
            with open(stock_list_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if isinstance(data, dict) and 'stocks' in data:
                    stocks_list = data['stocks']
                    if isinstance(stocks_list, list):
                        for item in stocks_list:
                            if isinstance(item, dict):
                                code = item.get('stock_code')
                                name = item.get('stock_name')
                                if code and name:
                                    stock_names[code] = name
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            code = item.get('code') or item.get('stock_code')
                            name = item.get('name') or item.get('stock_name')
                            if code and name:
                                stock_names[code] = name
                elif isinstance(data, dict):
                    for code, name in data.items():
                        if code and name:
                            stock_names[code] = name
        except Exception as e:
            print(f"⚠️ 加载股票名称文件失败: {e}")
    
    return stock_names

# ==================== 主函数 ====================
def main():
    config_path = project_dir / "config" / "stock_data_analysis.par"
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)

    try:
        config = load_config(str(config_path), str(project_dir))
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        sys.exit(1)

    log_dir = project_dir / "Log"
    logger = setup_logger(log_dir, "Daily_TA1A_download_moneyflow.log")
    logger.info("=" * 60)
    logger.info("开始执行 Daily_TA1A_download_moneyflow")
    logger.info("=" * 60)

    tickers = config.get('tickers', [])
    if not tickers:
        logger.error("配置文件中未找到股票列表 (tickers)")
        sys.exit(1)

    logger.info(f"待下载股票数量: {len(tickers)}")
    logger.info(f"股票列表: {', '.join(tickers)}")

    sqlite_dir = config.get('full_sqlite_dir', project_dir / "SQLiteDB")
    db_name = "HK_Stock.db"
    db_path = Path(sqlite_dir) / db_name
    logger.info(f"数据库路径: {db_path}")

    stock_names = load_stock_names(project_dir)

    futu_cfg = {
        'futu_account': config.get('futu_account', ''),
        'futu_pwd_md5': config.get('futu_pwd_md5', ''),
        'opend_exec_path': config.get('opend_exec_path', ''),
        'api_host': config.get('api_host', '127.0.0.1'),
        'api_port': int(config.get('api_port', 11111))
    }

    missing = [k for k in ['futu_account', 'opend_exec_path'] if not futu_cfg.get(k)]
    if missing:
        logger.error(f"配置缺少 Moomoo 必要字段: {missing}")
        sys.exit(1)

    # 计算日期范围
    now = datetime.now()
    today = now.date()
    
    if now.weekday() < 5 and now.time() < tm(16, 30):
        target_date = (today - timedelta(days=1))
        logger.info(f"⏰ 当前未到收盘，目标日期: {target_date}")
    else:
        target_date = today
        logger.info(f"⏰ 已收盘或周末，目标日期: {target_date}")
    
    # 从配置文件读取起始日期
    download_start_date = config.get('download_start_date', '2010-01-01')
    try:
        datetime.strptime(download_start_date, '%Y-%m-%d')
    except ValueError:
        logger.warning(f"⚠️ download_start_date 格式无效: {download_start_date}，使用 2010-01-01")
        download_start_date = '2010-01-01'
    
    download_end_date = target_date.strftime("%Y-%m-%d")
    logger.info(f"📅 起始日期: {download_start_date}")
    logger.info(f"📅 结束日期: {download_end_date}")

    # 启动 OpenD
    logger.info("🚀 启动 OpenD ...")
    opend_process = start_opend(futu_cfg)
    logger.info("⏳ 等待 OpenD 就绪 ...")
    if not wait_for_opend(futu_cfg['api_port'], timeout=120):
        logger.error("❌ OpenD 启动超时")
        opend_process.terminate()
        sys.exit(1)
    logger.info("✅ OpenD 已就绪")

    logger.info("⏳ 预热连接...")
    old_log_level = silence_moomoo_console(False)
    try:
        warm_ctx = ft.OpenQuoteContext(host=futu_cfg['api_host'], port=futu_cfg['api_port'])
        warm_ready, _ = wait_for_opend_ready(warm_ctx, timeout=120)
        warm_ctx.close()
        time.sleep(1)
        if not warm_ready:
            logger.warning("⚠️ OpenD 未进入 READY，仍尝试主连接...")
    finally:
        logging.getLogger('FTConsoleLog').setLevel(old_log_level)

    quote_ctx = None
    failed_stocks = []
    skipped_stocks = []
    success_stocks = []
    updated_stocks = []
    total_inserted = 0
    
    try:
        quote_ctx = ft.OpenQuoteContext(host=futu_cfg['api_host'], port=futu_cfg['api_port'])
        
        with SQLiteMoneyflowManager(db_path, logger) as db_manager:
            db_manager.create_table()
            
            for raw_ticker in tickers:
                symbol = f"HK.{raw_ticker}"
                stock_code = raw_ticker
                stock_name = stock_names.get(stock_code, '')
                
                logger.info(f"\n{'='*60}")
                logger.info(f"📊 处理股票: {symbol} ({stock_name})")
                logger.info(f"{'='*60}")
                
                try:
                    last_date = db_manager.get_last_date(stock_code)
                    existing_count = db_manager.get_date_count(stock_code)
                    
                    if last_date:
                        logger.info(f"   📊 现有数据: {existing_count} 条记录，最后日期: {last_date}")
                    else:
                        logger.info(f"   📊 无历史数据，将从 {download_start_date} 开始下载")
                    
                    if last_date:
                        last_date_obj = datetime.strptime(last_date, "%Y-%m-%d").date()
                        if last_date_obj >= target_date:
                            logger.info(f"   ⏭️ 已是最新，无需下载")
                            skipped_stocks.append(stock_code)
                            continue
                        
                        download_start_obj = last_date_obj + timedelta(days=1)
                        download_end_obj = target_date

                        # API 的 DAY 历史资金流存在有限历史窗口。
                        # 若数据库最后日期落后超过该窗口，不能假装已经补齐中间缺口。
                        api_earliest_date = target_date - timedelta(days=MAX_DAYS_PER_QUERY)
                        if download_start_obj < api_earliest_date:
                            logger.warning(
                                f"   ⚠️ 数据库最后日期 {last_date} 距今超过资金流接口可用历史窗口。"
                            )
                            logger.warning(
                                f"   ⚠️ 无法通过 get_capital_flow 补齐 "
                                f"{download_start_obj} 至 {api_earliest_date - timedelta(days=1)} 的缺口。"
                            )
                            logger.warning(
                                "   ⚠️ 本次仅下载接口当前可提供的历史窗口，"
                                "不会用 INTRADAY 数据冒充历史数据。"
                            )
                            download_start_obj = api_earliest_date

                        download_start = download_start_obj.strftime("%Y-%m-%d")
                        download_end = download_end_obj.strftime("%Y-%m-%d")
                        logger.info(f"   📥 下载增量/可用窗口数据: {download_start} 至 {download_end}")
                    else:
                        # 无历史数据时，严格使用配置文件中的 download_start_date。
                        # 注意：如果起始日期早于 Moomoo/Futu 资金流接口的历史可用范围，
                        # 对应批次会被 DAY 接口拒绝；程序会跳过这些批次，不再用
                        # INTRADAY 的“最新一天”数据冒充历史日期。
                        download_start = download_start_date
                        download_end = download_end_date
                        logger.info(f"   📥 下载完整历史数据: {download_start} 至 {download_end}")
                    
                    flow_list = get_historical_moneyflow(
                        quote_ctx, symbol, download_start, download_end, logger
                    )
                    
                    if not flow_list:
                        logger.warning(f"   ⚠️ [{stock_code}] 未获取到资金流数据")
                        failed_stocks.append(stock_code)
                        continue
                    
                    logger.info(f"   ✅ [{stock_code}] 获取到 {len(flow_list)} 条资金流记录")
                    
                    logger.info(f"   📊 获取最新资金分布数据...")
                    dist_data = get_latest_capital_distribution(quote_ctx, symbol, logger)
                    
                    if dist_data:
                        logger.info(f"   ✅ 获取到资金分布数据，日期: {dist_data['Date']}")
                    else:
                        logger.warning(f"   ⚠️ 未获取到资金分布数据")
                    
                    merged_data = merge_flow_and_distribution(flow_list, dist_data, logger)
                    
                    if not merged_data:
                        logger.warning(f"   ⚠️ [{stock_code}] 合并数据失败")
                        failed_stocks.append(stock_code)
                        continue
                    
                    inserted = db_manager.insert_batch_data(stock_code, stock_name, merged_data)
                    
                    if inserted > 0:
                        logger.info(f"   ✅ [{stock_code}] 成功插入 {inserted} 条记录")
                        total_inserted += inserted
                        success_stocks.append(stock_code)
                        
                        first_date = flow_list[0]['Date'].strftime('%Y-%m-%d')
                        last_date_str = flow_list[-1]['Date'].strftime('%Y-%m-%d')
                        if len(flow_list) == 1:
                            updated_stocks.append(f"{stock_code}({first_date})")
                        else:
                            updated_stocks.append(f"{stock_code}({first_date}~{last_date_str}, {inserted}条)")
                    else:
                        logger.warning(f"   ⚠️ [{stock_code}] 插入失败")
                        skipped_stocks.append(stock_code)
                    
                    current_count = db_manager.get_date_count(stock_code)
                    current_last = db_manager.get_last_date(stock_code)
                    current_first = db_manager.get_first_date(stock_code)
                    logger.info(f"   📊 [{stock_code}] 当前数据: {current_count} 条记录")
                    if current_first and current_last:
                        logger.info(f"      日期范围: {current_first} 至 {current_last}")
                    
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"   ❌ [{stock_code}] 处理失败: {e}")
                    logger.error(traceback.format_exc())
                    failed_stocks.append(stock_code)
                    continue
            
            logger.info("\n" + "=" * 60)
            logger.info("📊 执行结果统计:")
            logger.info(f"   ✅ 成功更新: {len(success_stocks)} 只股票")
            if updated_stocks:
                logger.info(f"      📝 更新详情:")
                for item in updated_stocks:
                    logger.info(f"          {item}")
            logger.info(f"   ⏭️ 跳过: {len(skipped_stocks)} 只股票")
            logger.info(f"   ❌ 失败: {len(failed_stocks)} 只股票")
            logger.info(f"   📊 总插入记录数: {total_inserted}")
            
            if failed_stocks:
                logger.info(f"   失败列表: {', '.join(failed_stocks)}")
            
            stats = db_manager.get_statistics()
            if stats:
                logger.info("\n📊 数据库统计:")
                logger.info(f"   总记录数: {stats.get('total_records', 0):,}")
                logger.info(f"   股票数量: {stats.get('stock_count', 0)}")
                logger.info(f"   日期范围: {stats.get('earliest_date', 'N/A')} 至 {stats.get('latest_date', 'N/A')}")
            
            logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 程序严重错误: {e}")
        logger.error(traceback.format_exc())
    finally:
        if quote_ctx:
            quote_ctx.close()
        opend_process.terminate()
        logger.info("🛑 OpenD 已关闭")
        logger.info("=" * 60)
        logger.info("程序执行完成")
        logger.info("=" * 60)

if __name__ == "__main__":
    main()