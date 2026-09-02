#!/usr/bin/env python
# coding: utf-8

"""
HK_Macro_History.py
获取并保存历史数据到 SQLite3 数据库：
   宏观指标（FRED + Yahoo）→ macro_data_hist 表
   港股指数（富途API）     → 每个指数单独表 + 合并收盘价表 hk_idx_hist
   南向资金每日明细         → southbound_flow_hist 表
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import yfinance as yf
import akshare as ak
import time
import warnings
import configparser
import sqlite3
import json
import logging

warnings.filterwarnings('ignore')

# =====================================================
# 1. 统一路径设置（修正：项目根目录为 TA_Workflow）
# =====================================================

def get_project_dir():
    """
    获取项目根目录 (TA_Workflow)
    脚本位于 TA_Workflow/Core/ 目录下
    """
    try:
        # 尝试从环境变量获取
        env_dir = os.environ.get('PROJECT_ROOT')
        if env_dir and Path(env_dir).exists():
            return Path(env_dir)

        # 从当前脚本路径推断项目根目录
        # 脚本路径: .../TA_Workflow/Core/HK_Macro_History.py
        # 项目根目录: .../TA_Workflow
        script_path = Path(__file__).resolve()
        
        # 向上两级到达项目根目录
        # Core 目录的父目录就是项目根目录
        project_dir = script_path.parent.parent
        
        # 验证是否真的是项目根目录（检查是否存在 config 目录）
        if (project_dir / 'config').exists():
            return project_dir
        
        # 如果找不到 config，尝试其他方式
        # 检查是否在 Core 目录中
        if script_path.parent.name == 'Core':
            return script_path.parent.parent
        
        # 尝试从当前工作目录向上查找
        cwd = Path(os.getcwd()).resolve()
        for parent in [cwd] + list(cwd.parents):
            if (parent / 'config').exists() and (parent / 'Core').exists():
                return parent
        
        # 最后返回当前目录的父目录
        return cwd.parent if cwd.name == 'Core' else cwd
        
    except Exception as e:
        print(f"获取项目目录错误: {str(e)}")
        # 备用方案：使用当前文件位置推断
        return Path(__file__).resolve().parent.parent

def fix_path_escapes(text):
    """
    自动修复Windows路径转义问题
    将单反斜杠替换为双反斜杠或正斜杠
    """
    import re
    # 使用正则表达式匹配Windows路径模式
    pattern = r'(?:[a-zA-Z]:\\)(?:[^\\\s]+\\)*[^\\\s]*'
    matches = re.findall(pattern, text)

    # 为每个匹配的路径创建修复版
    for match in matches:
        # 使用正斜杠版本（最安全）
        forward_slash_path = '"' + match.replace('\\', '/') + '"'
        text = text.replace(f"'{match}'", forward_slash_path)
        text = text.replace(f'"{match}"', forward_slash_path)

    # 额外全局替换未转义的单个反斜杠
    text = re.sub(r'(?<!\\)\$?!\$', r'\\\\', text)
    return text

def setup_windows_encoding():
    """解决Windows环境的中文编码问题"""
    if sys.platform == "win32":
        try:
            os.system("chcp 65001 > nul")
        except Exception as e:
            print(f"设置控制台代码页失败: {e}")

# =====================================================
# 2. 配置加载和路径初始化
# =====================================================

# 获取项目根目录
project_dir = get_project_dir()
print(f"[INFO] 项目目录: {project_dir}")

# 验证项目目录结构
if not (project_dir / 'config').exists():
    print(f"[WARN] 项目目录中未找到 config 目录: {project_dir}")
    print(f"[WARN] 尝试在父目录中查找...")
    # 尝试在父目录中查找
    parent_dir = project_dir.parent
    if (parent_dir / 'config').exists():
        project_dir = parent_dir
        print(f"[INFO] 找到项目目录: {project_dir}")

# 确保 Core 目录在 sys.path 中
core_dir = project_dir / 'Core'
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))
    print(f"[INFO] 已添加 Core 目录到 sys.path: {core_dir}")

# 也添加项目根目录到 sys.path
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

# 配置文件路径
config_path = project_dir / 'config' / 'stock_data_analysis.par'
print(f"[INFO] 配置文件路径: {config_path}")

# 验证配置文件存在
if not config_path.exists():
    alt_path = project_dir.parent / 'config' / 'stock_data_analysis.par'
    if alt_path.exists():
        config_path = alt_path
        print(f"[INFO] 使用备用配置文件路径: {config_path}")
    else:
        print(f"[ERROR] 配置文件不存在: {config_path}")
        print(f"[ERROR] 请确认项目目录结构: {project_dir}")
        sys.exit(1)

# 加载配置（优先使用 utl.stock_analysis_utl）
try:
    # 尝试从 utl 导入
    from utl.stock_analysis_utl import load_config, GlobalConfig
    print("[INFO] 成功导入 utl.stock_analysis_utl")
except ImportError as e:
    print(f"[WARN] 无法导入 utl.stock_analysis_utl: {e}")
    print("[INFO] 使用本地简化配置加载")
    
    # 本地简化版 GlobalConfig
    class GlobalConfig:
        full_data_dir = None
        full_report_dir = None
        full_log_dir = None
        full_temp_dir = None
        full_sqlite_dir = None
        full_db_path = None
        db_name = None
    
    def load_config(config_path, project_dir):
        """简化版配置加载（修复版：正确读取所有段落）"""
        config = {}
        cp = configparser.ConfigParser()
        cp.read(config_path, encoding='utf-8')
        
        # 读取 FOLDERS 段
        if cp.has_section('FOLDERS'):
            for key in cp.options('FOLDERS'):
                value = cp.get('FOLDERS', key).strip().strip("'").strip('"')
                config[key] = value
        
        # 读取 DATABASE 段
        if cp.has_section('DATABASE'):
            config['db_name'] = cp.get('DATABASE', 'db_name', fallback='HK_Stock.db').strip()
        else:
            config['db_name'] = 'HK_Stock.db'
        
        # ✅ 修复：正确读取 [FREDAPI] 段落
        if cp.has_section('FREDAPI'):
            config['FRED_API_KEY'] = cp.get('FREDAPI', 'FRED_API_KEY', fallback='').strip()
            print(f"[INFO] 已读取 FRED_API_KEY: {'已配置' if config['FRED_API_KEY'] else '未配置'}")
        else:
            config['FRED_API_KEY'] = ''
            print("[WARN] 配置文件中没有 [FREDAPI] 段落")
        
        # 读取 FUTU_MOOMOO 段（富途配置）
        if cp.has_section('FUTU_MOOMOO'):
            config['futu_account'] = cp.get('FUTU_MOOMOO', 'futu_account', fallback='')
            config['futu_pwd_md5'] = cp.get('FUTU_MOOMOO', 'futu_pwd_md5', fallback='')
            config['opend_exec_path'] = cp.get('FUTU_MOOMOO', 'opend_exec_path', fallback='')
            config['api_host'] = cp.get('FUTU_MOOMOO', 'api_host', fallback='127.0.0.1')
            port_str = cp.get('FUTU_MOOMOO', 'api_port', fallback='11111')
            try:
                config['api_port'] = int(port_str)
            except ValueError:
                config['api_port'] = 11111
        else:
            config['futu_account'] = ''
            config['futu_pwd_md5'] = ''
            config['opend_exec_path'] = ''
            config['api_host'] = '127.0.0.1'
            config['api_port'] = 11111
        
        # 构建完整路径
        data_rel = config.get('data_dir', 'data')
        config['full_data_dir'] = os.path.join(str(project_dir), data_rel)
        
        report_rel = config.get('report_dir', 'report')
        config['full_report_dir'] = os.path.join(str(project_dir), report_rel)
        
        log_rel = config.get('log_dir', 'log')
        config['full_log_dir'] = os.path.join(str(project_dir), log_rel)
        
        temp_rel = config.get('temp_dir', 'temp')
        config['full_temp_dir'] = os.path.join(str(project_dir), temp_rel)
        
        sqlite_rel = config.get('sqlite_dir', 'SQLiteDB')
        config['full_sqlite_dir'] = os.path.join(str(project_dir), sqlite_rel)
        
        db_name = config.get('db_name', 'HK_Stock.db')
        config['full_db_path'] = os.path.join(config['full_sqlite_dir'], db_name)
        
        # 确保目录存在
        for path_key in ['full_data_dir', 'full_report_dir', 'full_log_dir', 
                        'full_temp_dir', 'full_sqlite_dir']:
            path = config.get(path_key)
            if path and not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
        
        return config

# 加载配置
print("[INFO] 加载配置文件...")
CONFIG = load_config(str(config_path), str(project_dir))

# 更新 GlobalConfig
if hasattr(GlobalConfig, 'update_paths'):
    # 使用 stock_analysis_utl 的 update_paths 方法
    GlobalConfig.update_paths(CONFIG, project_dir)
else:
    # 手动设置 GlobalConfig
    GlobalConfig.full_data_dir = CONFIG.get('full_data_dir')
    GlobalConfig.full_report_dir = CONFIG.get('full_report_dir')
    GlobalConfig.full_log_dir = CONFIG.get('full_log_dir')
    GlobalConfig.full_temp_dir = CONFIG.get('full_temp_dir')
    GlobalConfig.full_sqlite_dir = CONFIG.get('full_sqlite_dir')
    GlobalConfig.db_name = CONFIG.get('db_name', 'HK_Stock.db')
    GlobalConfig.full_db_path = CONFIG.get('full_db_path')

# 强制 UTF-8 输出（控制台）
setup_windows_encoding()

# 使用 GlobalConfig 中的路径
DB_DIR = Path(GlobalConfig.full_sqlite_dir)
DB_PATH = Path(GlobalConfig.full_db_path)
print(f"[INFO] 数据库目录: {DB_DIR}")
print(f"[INFO] 数据库路径: {DB_PATH}")

# ---------- 加载数据字典 ----------
DATA_DICT_PATH = project_dir / "config" / "hk_macro_data_dictionary.json"
data_dictionary = {}
if DATA_DICT_PATH.exists():
    try:
        with open(DATA_DICT_PATH, 'r', encoding='utf-8') as f:
            data_dictionary = json.load(f)
        print(f"[INFO] 数据字典已加载: {DATA_DICT_PATH}")
        print(f"[INFO] 数据字典内容: {list(data_dictionary.keys()) if data_dictionary else '空'}")
    except Exception as e:
        print(f"[WARN] 加载数据字典失败: {e}")
else:
    print(f"[WARN] 数据字典文件不存在: {DATA_DICT_PATH}")

# ---------- 富途 (moomoo) 依赖 ----------
try:
    import moomoo as ft
    MOOMOO_AVAILABLE = True
    print("[INFO] moomoo 已加载，将使用富途API获取港股指数。")
except ImportError:
    MOOMOO_AVAILABLE = False
    print("[WARN] moomoo 未安装，请执行：pip install moomoo")

# ---------- FRED API ----------
try:
    from fredapi import Fred
    FRED_AVAILABLE = True
    print("[INFO] fredapi 已加载，宏观数据（除 DXY 外）将使用 FRED API。")
except ImportError:
    FRED_AVAILABLE = False
    print("[WARN] fredapi 未安装，请执行：pip install fredapi")

# =====================================================
# 3. 数据库操作辅助函数
# =====================================================

def get_db_connection():
    """获取数据库连接"""
    # 确保数据库目录存在（使用 GlobalConfig）
    DB_DIR = Path(GlobalConfig.full_sqlite_dir)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.text_factory = str  # 确保文本以字符串形式返回
    return conn

def save_to_sqlite(df, table_name, if_exists='replace'):
    """
    将 DataFrame 保存到 SQLite 数据库
    :param df: 要保存的 DataFrame
    :param table_name: 表名
    :param if_exists: 'replace' 覆盖, 'append' 追加, 'fail' 失败
    """
    if df is None or df.empty:
        print(f"⚠️ 数据为空，跳过保存到 {table_name}")
        return
    
    conn = get_db_connection()
    try:
        # 确保日期列转换为字符串格式
        for col in df.select_dtypes(include=['datetime64[ns]', 'datetime64']).columns:
            df[col] = df[col].dt.strftime('%Y-%m-%d')
        
        # 保存到数据库
        df.to_sql(table_name, conn, if_exists=if_exists, index=False)
        print(f"✅ 数据已保存到表: {table_name}, 共 {len(df)} 条记录")
    except Exception as e:
        print(f"❌ 保存到 {table_name} 失败: {e}")
        raise
    finally:
        conn.close()

def merge_to_sqlite(df_new, table_name, date_column='date'):
    """
    合并新数据到 SQLite 表（如果表存在则更新，否则创建）
    :param df_new: 新数据 DataFrame
    :param table_name: 表名
    :param date_column: 日期列名
    """
    if df_new is None or df_new.empty:
        print(f"⚠️ 新数据为空，跳过更新 {table_name}")
        return
    
    conn = get_db_connection()
    try:
        # 确保日期列格式统一
        if date_column in df_new.columns:
            df_new[date_column] = pd.to_datetime(df_new[date_column]).dt.strftime('%Y-%m-%d')
        
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # 读取旧数据
            df_old = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            
            # 确保日期列格式一致
            if date_column in df_old.columns:
                df_old[date_column] = pd.to_datetime(df_old[date_column]).dt.strftime('%Y-%m-%d')
            
            # 合并：新数据覆盖旧数据（按日期去重，保留最新）
            combined = pd.concat([df_old, df_new], ignore_index=True)
            combined.drop_duplicates(subset=[date_column], keep='last', inplace=True)
            combined.sort_values(date_column, inplace=True)
            df_final = combined.reset_index(drop=True)
            
            # 替换旧表
            df_final.to_sql(table_name, conn, if_exists='replace', index=False)
            print(f"✅ 表 {table_name} 已更新，共 {len(df_final)} 条记录")
        else:
            # 创建新表
            df_new.to_sql(table_name, conn, if_exists='replace', index=False)
            print(f"✅ 新表 {table_name} 已创建，共 {len(df_new)} 条记录")
    
    except Exception as e:
        print(f"❌ 更新表 {table_name} 失败: {e}")
        raise
    finally:
        conn.close()

def read_from_sqlite(table_name, date_column='date', start_date=None, end_date=None):
    """
    从 SQLite 读取数据
    :param table_name: 表名
    :param date_column: 日期列名
    :param start_date: 开始日期
    :param end_date: 结束日期
    :return: DataFrame
    """
    conn = get_db_connection()
    try:
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone() is None:
            print(f"⚠️ 表 {table_name} 不存在")
            return pd.DataFrame()
        
        # 构建查询
        query = f"SELECT * FROM {table_name}"
        if start_date and end_date:
            query += f" WHERE {date_column} BETWEEN '{start_date}' AND '{end_date}'"
        elif start_date:
            query += f" WHERE {date_column} >= '{start_date}'"
        elif end_date:
            query += f" WHERE {date_column} <= '{end_date}'"
        
        query += f" ORDER BY {date_column}"
        
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"❌ 读取表 {table_name} 失败: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# =====================================================
# 4. 辅助函数
# =====================================================

def get_historical_data(symbol, start_date, end_date):
    """Yahoo Finance 历史收盘价（用于 DXY）"""
    try:
        df = yf.download(symbol, start=start_date, end=end_date, progress=False, auto_adjust=True)
        if df is None or df.empty:
            return pd.Series()
        return df["Close"].dropna()
    except Exception as e:
        print(f"[ERROR] {symbol} 获取失败: {e}")
        return pd.Series()

def get_fred_api_key():
    """
    从全局配置（CONFIG）读取 FRED_API_KEY。
    优先从配置中读取，其次环境变量。
    """
    # 尝试从 CONFIG 中读取
    key = CONFIG.get('FRED_API_KEY')
    if key and key.strip():
        return key.strip()
    # 后备：尝试环境变量
    env_key = os.getenv("FRED_API_KEY")
    if env_key:
        return env_key.strip()
    raise RuntimeError(
        "无法获取 FRED_API_KEY，请确保在 config/stock_data_analysis.par 中设置 FRED_API_KEY，"
        "或设置环境变量 FRED_API_KEY。"
    )

# =====================================================
# 5. 南向资金历史净流入（用于合并到 hk_idx_hist）
# =====================================================
def get_southbound_flow_history():
    """
    获取南向资金历史日度净流入（亿元）
    返回 DataFrame: columns=['date', 'SouthboundFlow']
    """
    try:
        df = ak.stock_hsgt_hist_em(symbol="南向资金")
        if df is None or df.empty:
            return pd.DataFrame()

        date_col = [c for c in df.columns if '日期' in c or 'date' in c.lower()]
        buy_col  = [c for c in df.columns if '买入' in c and ('成交额' in c or '金额' in c)]
        sell_col = [c for c in df.columns if '卖出' in c and ('成交额' in c or '金额' in c)]

        if not date_col or not buy_col or not sell_col:
            print("[ERROR] 无法识别买入/卖出/日期列")
            return pd.DataFrame()

        df_out = df[[date_col[0], buy_col[0], sell_col[0]]].copy()
        df_out.columns = ['date', 'buy', 'sell']
        df_out['SouthboundFlow'] = df_out['buy'] - df_out['sell']
        df_out['date'] = pd.to_datetime(df_out['date']).dt.date
        return df_out[['date', 'SouthboundFlow']]
    except Exception as e:
        print(f"[ERROR] 南向资金历史获取失败: {e}")
        return pd.DataFrame()

# =====================================================
# 6. 宏观数据保存到 SQLite
# =====================================================
def save_macro_data(start_date, end_date):
    print(f"[DEBUG] 准备保存宏观历史数据到数据库表: macro_data_hist")
    
    # DXY
    print("  -> 获取 DXY (DX-Y.NYB) 数据...")
    dxy = get_historical_data("DX-Y.NYB", start_date, end_date)
    if dxy.empty:
        print("     ⚠️ DXY 获取失败")
    else:
        print(f"     成功，共 {len(dxy)} 条")

    if not FRED_AVAILABLE:
        print("[ERROR] fredapi 未安装，其他宏观数据将为空。")
        df_all = pd.DataFrame(index=pd.date_range(start=start_date, end=end_date, freq='D'))
        df_all.index = df_all.index.date
        df_all["DXY"] = dxy
        for col in ["US2Y", "US10Y", "US30Y", "VIX", "USDCNY"]:
            df_all[col] = np.nan
    else:
        # ---------- 使用配置文件中的 API Key ----------
        api_key = get_fred_api_key()
        fred = Fred(api_key=api_key)
        series_map = {
            "US2Y": "DGS2",
            "US10Y": "DGS10",
            "US30Y": "DGS30",
            "VIX": "VIXCLS",
            "USDCNY": "DEXCHUS",
        }
        df_all = pd.DataFrame(index=pd.date_range(start=start_date, end=end_date, freq='D'))
        df_all.index = df_all.index.date
        df_all["DXY"] = dxy

        for name, sid in series_map.items():
            print(f"  -> 获取 {name} ({sid}) 数据...")
            try:
                series = fred.get_series(sid, observation_start=start_date, observation_end=end_date)
                if series is not None and not series.empty:
                    df_all[name] = series
                    print(f"     成功，共 {len(series)} 条")
                else:
                    print(f"     ⚠️ 无数据")
                    df_all[name] = np.nan
            except Exception as e:
                print(f"     ❌ 失败: {e}")
                df_all[name] = np.nan

    df_all = df_all.reset_index().rename(columns={'index': 'date'})

    # 标准列顺序
    standard_cols = [
        "date", "DXY", "US2Y", "US10Y", "US30Y", "VIX", "USDCNY",
        "FEDFUNDS", "SOFR", "UNRATE", "CORE_CPI_YOY"
    ]
    for col in standard_cols:
        if col not in df_all.columns:
            df_all[col] = np.nan
    df_all = df_all[standard_cols]
    df_all.sort_values("date", inplace=True)
    df_all.reset_index(drop=True, inplace=True)
    
    # 数值列四舍五入
    numeric_cols = df_all.select_dtypes(include=[np.number]).columns
    df_all[numeric_cols] = df_all[numeric_cols].round(4)
    
    # 保存到 SQLite（合并更新）
    merge_to_sqlite(df_all, "macro_data_hist", date_column='date')
    
    # 显示最新数据
    latest_date = df_all['date'].max()
    print(f"     📊 最新日期: {latest_date}，共 {len(df_all)} 条记录")

# =====================================================
# 7. 南向资金每日明细保存到 SQLite
# =====================================================
def save_southbound_flow_daily():
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            df = ak.stock_hsgt_hist_em(symbol="南向资金")
            if df is None or df.empty:
                print("⚠️ 南向资金数据为空")
                return

            col_map = {}
            date_col = [c for c in df.columns if '日期' in c or 'date' in c.lower()]
            if date_col:
                col_map['date'] = date_col[0]
            buy_col = [c for c in df.columns if '买入' in c and ('成交额' in c or '金额' in c)]
            if buy_col:
                col_map['buy_amount'] = buy_col[0]
            sell_col = [c for c in df.columns if '卖出' in c and ('成交额' in c or '金额' in c)]
            if sell_col:
                col_map['sell_amount'] = sell_col[0]

            required = ['date', 'buy_amount', 'sell_amount']
            if any(k not in col_map for k in required):
                print(f"⚠️ 未找到所需列，跳过保存")
                return

            df_save = df[list(col_map.values())].copy()
            df_save.columns = ['date', 'buy_amount', 'sell_amount']
            df_save['net_inflow'] = df_save['buy_amount'] - df_save['sell_amount']
            for col in ['buy_amount', 'sell_amount', 'net_inflow']:
                df_save[col] = df_save[col].round(2)
            df_save = df_save.sort_values('date').reset_index(drop=True)
            
            # 保存到 SQLite（全量替换）
            save_to_sqlite(df_save, "southbound_flow_hist", if_exists='replace')
            print(f"✅ 南向资金每日明细已保存到数据库 (共 {len(df_save)} 条)")
            return
        except Exception as e:
            print(f"❌ 第 {attempt} 次尝试失败: {e}")
            time.sleep(5)
    print("❌ 所有重试均失败")

# =====================================================
# 8. 港股指数获取（富途API）
# =====================================================

def load_par_config(config_path):
    """读取富途配置段（保持原有逻辑）"""
    config = {}
    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            if key == 'tickers':
                config[key] = [v.strip() for v in value.split(',') if v.strip()]
            else:
                config[key] = value
    return config

def start_opend(opend_path, account, port):
    import subprocess
    # OpenD 10.10 起废弃 login_pwd_md5 参数，改用“记住密码”免密自动登录：
    # 需先手动登录一次并勾选“记住密码”，才能用 -login_by_remember=1 自动登录。
    cmd = [
        opend_path,
        f"-login_account={account}",
        "-login_by_remember=1",
        f"-api_port={port}",
        "-lang=chs"
    ]
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.Popen(cmd, startupinfo=si)
    else:
        return subprocess.Popen(cmd)

def wait_for_opend(port, timeout=120):
    import socket
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

def get_index_kline(ctx, code, start_date, end_date, ktype=ft.KLType.K_DAY):
    """
    分页获取历史K线，返回完整DataFrame
    ⚠️ 重要：下载数据时将 time_key 列重命名为 date
    """
    all_data = []
    page_key = None
    max_attempts = 100
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        ret, data, next_page_key = ctx.request_history_kline(
            code=code,
            start=start_date,
            end=end_date,
            ktype=ktype,
            max_count=1000,
            page_req_key=page_key
        )
        if ret != ft.RET_OK:
            raise Exception(f"请求失败: {data}")

        if data.empty:
            break

        all_data.append(data)
        if not next_page_key:
            break
        page_key = next_page_key
        time.sleep(0.2)

    if not all_data:
        return pd.DataFrame()

    df_all = pd.concat(all_data, ignore_index=True)
    df_all = df_all.sort_values('time_key').reset_index(drop=True)
    
    # ⚠️ 关键修改：将 time_key 列重命名为 date
    if 'time_key' in df_all.columns:
        df_all = df_all.rename(columns={'time_key': 'date'})
        df_all['date'] = pd.to_datetime(df_all['date']).dt.strftime('%Y-%m-%d')
    else:
        print(f"   ⚠️ 警告: 数据中没有 time_key 列，请检查数据格式")
    
    return df_all

def save_to_sqlite_index(df, table_name):
    """
    保存指数K线数据到 SQLite 数据库
    :param df: 包含 K 线数据的 DataFrame (date列已改为'date')
    :param table_name: 表名 (如 hk_idx_hsi)
    """
    if df is None or df.empty:
        print(f"   ⚠️ 数据为空，跳过保存到 {table_name}")
        return
    
    # 确保日期列格式（现在列名是 'date'）
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    else:
        print(f"   ⚠️ 警告: 数据中没有 date 列，无法保存到 {table_name}")
        return
    
    # 保存到 SQLite（合并更新），使用 'date' 作为日期列
    merge_to_sqlite(df, table_name, date_column='date')

# ---------- 指数映射表 ----------
INDEX_MAPPING = [
    ("HK.800000", "HSI",    "hk_idx_hsi",     True),   # 恒生指数
    ("HK.800100", "HSCEI",  "hk_idx_hscei",   True),   # 恒生国企指数
    ("HK.800700", "HSTECH", "hk_idx_hstech",  True),   # 恒生科技指数
    ("HK.800152", "HSNF",   "hk_idx_hnf",     True),   # 恒生金融分类指数
    ("HK.800153", "HSNP",   "hk_idx_hnp",     True),   # 恒生地产分类指数
    ("HK.800154", "HSNC",   "hk_idx_hnc",     True),   # 恒生工商分类指数
    ("HK.800155", "HSNU",   "hk_idx_hnu",     True),   # 恒生公用事业分类指数
    ("HK.800187", "HSBIO",  "hk_idx_hsbio",   True),   # 恒生生物科技指数
    ("HK.800125", "VHSI",   "hk_idx_vhsi",    True),   # 恒指波幅指数
]

def get_hk_index_data_from_futu(start_date, end_date):
    """
    使用富途API获取港股指数数据：
       - 为每个指数保存完整的K线数据到单独的 SQLite 表（使用 date 列）
       - 返回合并的收盘价DataFrame（只包含 merge_flag=True 的指数）
    """
    if not MOOMOO_AVAILABLE:
        print("[WARN] moomoo 不可用，跳过富途指数获取。")
        return pd.DataFrame()

    # 富途配置文件路径（使用统一 project_dir）
    config_path = project_dir / "config" / "stock_data_analysis.par"
    if not config_path.exists():
        print(f"[ERROR] 配置文件不存在: {config_path}")
        return pd.DataFrame()

    config = load_par_config(config_path)
    required = ['futu_account', 'opend_exec_path']
    if any(k not in config or not config[k] for k in required):
        print("[ERROR] 富途配置缺失必要字段，跳过指数获取。")
        return pd.DataFrame()

    api_host = config.get('api_host', '127.0.0.1')
    api_port = int(config.get('api_port', 11111))
    account = config['futu_account']
    opend_path = config['opend_exec_path']

    # 启动 OpenD
    print("🚀 启动 OpenD ...")
    opend_process = start_opend(opend_path, account, api_port)
    print("⏳ 等待 OpenD 就绪 ...")
    if not wait_for_opend(api_port):
        print("❌ OpenD 启动超时，跳过指数获取。")
        opend_process.terminate()
        return pd.DataFrame()
    print("✅ OpenD 已就绪")

    # 端口监听不代表 API 已就绪：OpenD 启动后还需完成登录/初始化（约几秒~几十秒）。
    # 用一次预热连接等 OpenD 真正 READY 后再关闭，主连接就能第一次成功。
    # 预热期间库内部的首连被拒/重连/关闭属正常现象，临时静音 moomoo 控制台日志。
    print("⏳ 预热连接：等待 OpenD 登录完成并进入 READY ...")
    old_log_level = silence_moomoo_console(False)
    try:
        warm_ctx = ft.OpenQuoteContext(host=api_host, port=api_port)
        warm_ready, _ = wait_for_opend_ready(warm_ctx, timeout=120)
        warm_ctx.close()
        time.sleep(1)
        if not warm_ready:
            print("⚠️ OpenD 未在预期时间内进入 READY，仍尝试主连接 ...")
    finally:
        logging.getLogger('FTConsoleLog').setLevel(old_log_level)

    ctx = ft.OpenQuoteContext(host=api_host, port=api_port)

    start_str = start_date.strftime("%Y-%m-%d") if isinstance(start_date, (datetime, pd.Timestamp)) else str(start_date)
    end_str = end_date.strftime("%Y-%m-%d") if isinstance(end_date, (datetime, pd.Timestamp)) else str(end_date)

    close_dict = {}
    try:
        for code, col_name, table_name, merge_flag in INDEX_MAPPING:
            print(f"📊 获取 {code} ({col_name}) ...")
            try:
                # 这里返回的 DataFrame 中 time_key 已经被重命名为 date
                df_full = get_index_kline(ctx, code, start_str, end_str)
                if df_full.empty:
                    print(f"   ⚠️ 无数据，跳过")
                    continue

                # 保存完整的 K 线数据到 SQLite（列名已经是 'date'）
                save_to_sqlite_index(df_full, table_name)

                if merge_flag:
                    # 使用 'date' 列构建合并数据
                    if 'date' in df_full.columns and 'close' in df_full.columns:
                        close_df = df_full[['date', 'close']].copy()
                        close_df.rename(columns={'close': col_name}, inplace=True)
                        close_df['date'] = pd.to_datetime(close_df['date']).dt.date
                        close_dict[col_name] = close_df
                        print(f"   ✅ 获取 {len(df_full)} 条记录，已加入合并列表")
                    else:
                        print(f"   ⚠️ 数据缺少 date 或 close 列，无法合并")
                else:
                    print(f"   ✅ 获取 {len(df_full)} 条记录（仅保存单独表）")
            except Exception as e:
                print(f"   ❌ 失败: {e}")
            time.sleep(0.5)

        if not close_dict:
            print("⚠️ 未获取到任何需要合并的指数数据")
            return pd.DataFrame()

        merged = None
        for col_name, df in close_dict.items():
            if merged is None:
                merged = df
            else:
                merged = pd.merge(merged, df, on='date', how='outer')
        merged = merged.sort_values('date').reset_index(drop=True)
        return merged

    except Exception as e:
        print(f"[ERROR] 富途获取指数失败: {e}")
        return pd.DataFrame()
    finally:
        ctx.close()
        opend_process.terminate()
        print("🛑 OpenD 已关闭")

# =====================================================
# 9. 保存港股历史数据到 SQLite（合并收盘价 + 南向资金）
# =====================================================
def save_hk_index(start_date, end_date):
    """
    获取港股指数收盘价（由 get_hk_index_data_from_futu 内部保存单独表）
    并合并南向资金净流入，最终生成 hk_idx_hist 表
    新数据会覆盖旧数据（按日期去重，保留最新）
    """
    print(f"\n[DEBUG] 准备保存港股合并数据到数据库表: hk_idx_hist")

    df_idx = get_hk_index_data_from_futu(start_date, end_date)
    if df_idx.empty:
        print("[WARN] 无法获取港股指数，将只保留南向资金。")
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        df_idx = pd.DataFrame({'date': date_range.date})
        index_cols = ["HSI", "HSCEI", "HSTECH", "HSNF", "HSNP", "HSNC", "HSNU", "HSBIO", "VHSI"]
        for col in index_cols:
            df_idx[col] = np.nan
    else:
        df_idx['date'] = pd.to_datetime(df_idx['date']).dt.date

    df_south = get_southbound_flow_history()
    if not df_south.empty:
        df_south['date'] = pd.to_datetime(df_south['date']).dt.date
        df_idx = pd.merge(df_idx, df_south, on='date', how='left')
    else:
        df_idx['SouthboundFlow'] = np.nan

    desired_columns = ["date", "HSI", "HSCEI", "HSTECH", "HSNF", "HSNP", "HSNC", "HSNU", "HSBIO", "VHSI", "SouthboundFlow"]
    for col in desired_columns:
        if col not in df_idx.columns:
            df_idx[col] = np.nan
    df_idx = df_idx[desired_columns]

    # 移除完全为空的行（date 列必须有值）
    non_date_cols = [c for c in desired_columns if c != 'date']
    df_idx = df_idx.dropna(subset=non_date_cols, how='all')

    # 数值列四舍五入
    numeric_cols = df_idx.select_dtypes(include=[np.number]).columns
    df_idx[numeric_cols] = df_idx[numeric_cols].round(2)

    # 保存到 SQLite（合并更新）
    merge_to_sqlite(df_idx, "hk_idx_hist", date_column='date')
    
    # 显示最新数据
    latest_date = df_idx['date'].max()
    print(f"     📊 最新日期: {latest_date}，共 {len(df_idx)} 条记录")

# =====================================================
# 10. 风险检查（从 SQLite 读取宏观数据）
# =====================================================
def risk_check():
    """从数据库读取宏观数据进行风险检查"""
    df = read_from_sqlite("macro_data_hist", date_column='date')
    if df.empty:
        print("[WARN] macro_data_hist 表为空或不存在")
        return
    
    try:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        latest = df.iloc[-1]
        alerts = []
        if latest["DXY"] > 108:
            alerts.append("DXY > 108 高风险")
        elif latest["DXY"] > 105:
            alerts.append("DXY > 105 承压")
        if latest["US10Y"] > 5.0:
            alerts.append("10Y > 5% 风险资产受压")
        if latest["US30Y"] > 5.2:
            alerts.append("30Y > 5.2 长债风险")
        if latest["VIX"] > 35:
            alerts.append("VIX > 35 恐慌")
        elif latest["VIX"] > 25:
            alerts.append("VIX > 25 风险下降")

        print("\n====================")
        print("风险预警（基于最新数据）")
        print("====================")
        if alerts:
            for a in alerts:
                print("⚠", a)
        else:
            print("无风险信号")
    except Exception as e:
        print(f"[ERROR] 风险检查失败: {e}")

# =====================================================
# 11. 主函数
# =====================================================
def main():
    today = datetime.today().date()
    print("\n====================")
    print("获取历史数据并更新到 SQLite 数据库")
    print("====================\n")

    # ------------------- 直接从配置文件读取 [HK_MACRO_DATA] 段落 -------------------
    import configparser
    config_file = project_dir / "config" / "stock_data_analysis.par"
    if not config_file.exists():
        print(f"[ERROR] 配置文件不存在: {config_file}")
        sys.exit(1)
    cp = configparser.ConfigParser()
    cp.read(config_file, encoding='utf-8')
    if not cp.has_section('HK_MACRO_DATA'):
        print("[ERROR] 配置文件中缺少 [HK_MACRO_DATA] 段落")
        sys.exit(1)
    section = cp['HK_MACRO_DATA']
    days_str = section.get('macro_data_download_days', '').strip()
    start_date_str = section.get('macro_data_download_start_date', '').strip()

    # 解析下载天数
    days_valid = False
    days = None
    if days_str and days_str.lower() != 'nan':
        try:
            days = int(days_str)
            if 0 < days < 100:
                days_valid = True
            else:
                print(f"[ERROR] macro_data_download_days 必须为 1~100 之间的整数，当前值: {days_str}")
        except ValueError:
            print(f"[ERROR] macro_data_download_days 不是合法整数: {days_str}")

    # 解析起始日期
    start_valid_old = False
    parsed_start = None
    if start_date_str and start_date_str.lower() != 'nan':
        try:
            parsed_start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            ten_years_ago = today - timedelta(days=365*10)
            if parsed_start < ten_years_ago:   # 早于10年前
                start_valid_old = True
            else:
                print(f"[WARN] macro_data_download_start_date = {start_date_str} 并非超过10年前的日期，将被忽略（除非 days 无效）")
        except ValueError:
            print(f"[WARN] macro_data_download_start_date 日期格式无效: {start_date_str}，将被忽略")

    # ------- 确定下载起止日期（优先使用 days） -------
    if days_valid:
        start_date = today - timedelta(days=days)
        end_date = today
        print(f"📅 根据 macro_data_download_days = {days}，下载最近 {days} 天的数据")
        print(f"   时间范围: {start_date} 至 {end_date}")
    elif start_valid_old:
        start_date = parsed_start
        end_date = today
        print(f"📅 根据 macro_data_download_start_date = {start_date_str}（超过10年前），下载自该日期以来的数据")
        print(f"   时间范围: {start_date} 至 {end_date}")
    else:
        print("[ERROR] 配置参数无效：")
        print("   - macro_data_download_days 不是 1~29 的整数（或为 Nan），且")
        print("   - macro_data_download_start_date 不是超过10年前的有效日期（或为 Nan）")
        print("   请至少正确设置其中一个参数。")
        sys.exit(1)

    # ------------------- 执行下载 -------------------
    print(f"\n数据库路径: {DB_PATH.resolve()}")
    print(f"项目根目录: {project_dir}")
    save_macro_data(start_date, end_date)
    save_hk_index(start_date, end_date)          # 内部会保存单独指数表 + 合并表
    save_southbound_flow_daily()                 # 南向资金明细（全量更新）
    risk_check()

    print("\n✅ 全部完成")

if __name__ == "__main__":
    main()
