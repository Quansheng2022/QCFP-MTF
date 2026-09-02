#!/usr/bin/env python
# coding: utf-8

# HK_Macro_Dashboard.py
# 整合 v2 与 v3 的港股宏观风险监控，输出包含详细解释
# VHSI 恒指波幅指数直接从 SQLite 数据库读取
# 数据存储：所有数据存储在 SQLite 数据库中
# 存储精度：DXY,VIX,USDCNY 保留4位小数；港股指数及南向资金保留2位小数
# 指数获取：优先 yfinance，失败则通过 akshare 备用
# 日志抑制：完全屏蔽 yfinance HTTP 404 等错误输出（重定向 stdout/stderr）

import os
import sys
import time
import re
import logging
import warnings
import contextlib
import io
import html
import json
import sqlite3
import configparser
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import yfinance as yf
import akshare as ak
from fredapi import Fred
import requests
import pdfplumber
from io import BytesIO

# 抑制 pandas 的 SettingWithCopyWarning
warnings.filterwarnings('ignore', category=UserWarning)

# 抑制 yfinance 和 urllib3 的日志
logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

# ReportLab PDF 生成（保留，用于生成报告）
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️ reportlab 未安装，无法生成PDF报告。请安装: pip install reportlab")

# =====================================================
# 1. 统一路径设置（与 HK_Macro_History.py 保持一致）
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
        script_path = Path(__file__).resolve()
        
        # 向上两级到达项目根目录
        project_dir = script_path.parent.parent
        
        # 验证是否真的是项目根目录（检查是否存在 config 目录）
        if (project_dir / 'config').exists():
            return project_dir
        
        # 如果找不到 config，尝试其他方式
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
        return Path(__file__).resolve().parent.parent

def setup_windows_encoding():
    """解决Windows环境的中文编码问题"""
    if sys.platform == "win32":
        try:
            os.system("chcp 65001 > nul")
        except Exception as e:
            print(f"设置控制台代码页失败: {e}")

# =====================================================
# 2. 配置加载和路径初始化（与 HK_Macro_History.py 保持一致）
# =====================================================

# 获取项目根目录
project_dir = get_project_dir()
print(f"[INFO] 项目目录: {project_dir}")

# 验证项目目录结构
if not (project_dir / 'config').exists():
    print(f"[WARN] 项目目录中未找到 config 目录: {project_dir}")
    print(f"[WARN] 尝试在父目录中查找...")
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
        
        @classmethod
        def update_paths(cls, config, project_dir):
            """更新路径（与 HK_Macro_History.py 保持一致）"""
            cls.full_data_dir = config.get('full_data_dir')
            cls.full_report_dir = config.get('full_report_dir')
            cls.full_log_dir = config.get('full_log_dir')
            cls.full_temp_dir = config.get('full_temp_dir')
            cls.full_sqlite_dir = config.get('full_sqlite_dir')
            cls.db_name = config.get('db_name', 'HK_Stock.db')
            cls.full_db_path = config.get('full_db_path')
    
    def load_config(config_path, project_dir):
        """简化版配置加载（与 HK_Macro_History.py 保持一致）"""
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
        
        # 读取 FREDAPI 段
        if cp.has_section('FREDAPI'):
            config['FRED_API_KEY'] = cp.get('FREDAPI', 'FRED_API_KEY', fallback='')
        else:
            config['FRED_API_KEY'] = ''
        
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
        
        # 构建完整路径（与 HK_Macro_History.py 保持一致）
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

# 更新 GlobalConfig（与 HK_Macro_History.py 保持一致）
if hasattr(GlobalConfig, 'update_paths'):
    GlobalConfig.update_paths(CONFIG, project_dir)
else:
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
DATA_DIR = Path(GlobalConfig.full_data_dir)
SQLITE_DIR = Path(GlobalConfig.full_sqlite_dir)
DB_PATH = Path(GlobalConfig.full_db_path)

print(f"[INFO] 数据目录: {DATA_DIR}")
print(f"[INFO] SQLite 数据库目录: {SQLITE_DIR}")
print(f"[INFO] SQLite 数据库路径: {DB_PATH}")

# =====================================================
# 3. 加载数据字典
# =====================================================

def load_data_dictionary():
    """加载数据字典文件 hk_macro_data_dictionary.json"""
    dict_path = project_dir / "config" / "hk_macro_data_dictionary.json"
    if not dict_path.exists():
        print(f"⚠️ 数据字典文件不存在: {dict_path}")
        return None
    
    try:
        with open(dict_path, 'r', encoding='utf-8') as f:
            data_dict = json.load(f)
        print(f"✅ 加载数据字典成功: {dict_path}")
        return data_dict
    except Exception as e:
        print(f"❌ 加载数据字典失败: {e}")
        return None

DATA_DICT = load_data_dictionary()
if DATA_DICT:
    print(f"📋 数据字典加载成功，包含 {len(DATA_DICT)} 个表定义")

# =====================================================
# 4. 数据库操作辅助函数
# =====================================================

def get_db_connection():
    """获取数据库连接"""
    DB_DIR = Path(GlobalConfig.full_sqlite_dir)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.text_factory = str
    return conn

def save_to_sqlite(df, table_name, if_exists='replace'):
    """将 DataFrame 保存到 SQLite 数据库"""
    if df is None or df.empty:
        print(f"⚠️ 数据为空，跳过保存到 {table_name}")
        return
    
    conn = get_db_connection()
    try:
        for col in df.select_dtypes(include=['datetime64[ns]', 'datetime64']).columns:
            df[col] = df[col].dt.strftime('%Y-%m-%d')
        
        df.to_sql(table_name, conn, if_exists=if_exists, index=False)
        print(f"✅ 数据已保存到表: {table_name}, 共 {len(df)} 条记录")
    except Exception as e:
        print(f"❌ 保存到 {table_name} 失败: {e}")
        raise
    finally:
        conn.close()

def merge_to_sqlite(df_new, table_name, date_column='date'):
    """合并新数据到 SQLite 表"""
    if df_new is None or df_new.empty:
        print(f"⚠️ 新数据为空，跳过更新 {table_name}")
        return
    
    conn = get_db_connection()
    try:
        if date_column in df_new.columns:
            df_new[date_column] = pd.to_datetime(df_new[date_column]).dt.strftime('%Y-%m-%d')
        
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            df_old = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            
            if date_column in df_old.columns:
                df_old[date_column] = pd.to_datetime(df_old[date_column]).dt.strftime('%Y-%m-%d')
            
            combined = pd.concat([df_old, df_new], ignore_index=True)
            combined.drop_duplicates(subset=[date_column], keep='last', inplace=True)
            combined.sort_values(date_column, inplace=True)
            df_final = combined.reset_index(drop=True)
            
            df_final.to_sql(table_name, conn, if_exists='replace', index=False)
            print(f"✅ 表 {table_name} 已更新，共 {len(df_final)} 条记录")
        else:
            df_new.to_sql(table_name, conn, if_exists='replace', index=False)
            print(f"✅ 新表 {table_name} 已创建，共 {len(df_new)} 条记录")
    
    except Exception as e:
        print(f"❌ 更新表 {table_name} 失败: {e}")
        raise
    finally:
        conn.close()

def read_from_sqlite(table_name, date_column='date', start_date=None, end_date=None, order_by=None, limit=None):
    """从 SQLite 读取数据"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone() is None:
            print(f"⚠️ 表 {table_name} 不存在")
            return pd.DataFrame()
        
        query = f"SELECT * FROM {table_name}"
        where_clauses = []
        
        if start_date and end_date:
            where_clauses.append(f"{date_column} BETWEEN '{start_date}' AND '{end_date}'")
        elif start_date:
            where_clauses.append(f"{date_column} >= '{start_date}'")
        elif end_date:
            where_clauses.append(f"{date_column} <= '{end_date}'")
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        if order_by:
            query += f" ORDER BY {order_by}"
        else:
            query += f" ORDER BY {date_column}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"❌ 读取表 {table_name} 失败: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# =====================================================
# 5. FRED API KEY 获取
# =====================================================

def get_fred_api_key():
    """从全局配置读取 FRED_API_KEY"""
    key = CONFIG.get('FRED_API_KEY')
    if key and key.strip():
        return key.strip()
    env_key = os.getenv("FRED_API_KEY")
    if env_key:
        return env_key.strip()
    print("[WARN] 无法获取 FRED_API_KEY")
    return None

# =====================================================
# 6. 数据获取函数
# =====================================================

def get_latest_price(symbol):
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = yf.download(symbol, period="10d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return np.nan
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            arr = close.values.flatten()
        elif isinstance(close, pd.Series):
            arr = close.dropna().values
        else:
            return float(close)
        arr = arr[~pd.isna(arr)]
        return float(arr[-1]) if len(arr) > 0 else np.nan
    except Exception:
        return np.nan

def get_hk_index_from_akshare(name_cn):
    try:
        df = ak.stock_hk_index_spot_em()
        if df is None or df.empty:
            return np.nan
        row = df[df['名称'] == name_cn]
        if not row.empty:
            return float(row['最新价'].iloc[0])
        return np.nan
    except Exception as e:
        print(f"  ⚠️ akshare 获取 {name_cn} 失败: {e}")
        return np.nan

def get_price_with_fallback(symbol, ak_name=None):
    val = get_latest_price(symbol)
    if pd.isna(val) and ak_name:
        val = get_hk_index_from_akshare(ak_name)
    return val

def get_fred(series):
    try:
        api_key = get_fred_api_key()
        if not api_key:
            return np.nan
        fred = Fred(api_key=api_key)
        s = fred.get_series(series).dropna()
        return float(s.to_numpy()[-1]) if len(s) > 0 else np.nan
    except Exception as e:
        print(f"  ❌ FRED {series} 错误: {e}")
        return np.nan

def get_southbound_flow():
    try:
        df = ak.stock_hsgt_hist_em(symbol="南向资金")
        if df is None or df.empty:
            return "无有效南向资金数据"
        today = datetime.now().strftime("%Y-%m-%d")
        today_data = df[df["日期"] == today]
        if not today_data.empty:
            row = today_data.iloc[0]
        else:
            row = df.iloc[-1]
        date_str = row["日期"]
        reported = row.get("当日资金流入", np.nan)
        if pd.notna(reported):
            val = float(reported)
        else:
            if "买入成交额" in df.columns and "卖出成交额" in df.columns:
                val = float(row["买入成交额"] - row["卖出成交额"])
            else:
                return "无有效南向资金数据"
        return f"{date_str}    {val:.2f} 亿元"
    except Exception as e:
        return "无有效南向资金数据"

def get_core_cpi_yoy():
    try:
        api_key = get_fred_api_key()
        if not api_key:
            return np.nan
        fred = Fred(api_key=api_key)
        s = fred.get_series("CPILFESL").dropna()
        if len(s) < 13:
            return np.nan
        latest = float(s.iloc[-1])
        last_year = float(s.iloc[-13])
        return round((latest / last_year - 1) * 100, 2)
    except Exception as e:
        print(f"  ❌ 核心CPI计算失败: {e}")
        return np.nan

def save_macro_data():
    """采集并保存宏观数据到 SQLite"""
    print("\n📊 开始采集宏观数据...")
    row = {
        "date": datetime.today().strftime("%Y-%m-%d"),
        "DXY": get_latest_price("DX-Y.NYB"),
        "US2Y": get_fred("DGS2"),
        "US10Y": get_fred("DGS10"),
        "US30Y": get_fred("DGS30"),
        "FEDFUNDS": get_fred("FEDFUNDS"),
        "SOFR": get_fred("SOFR"),
        "UNRATE": get_fred("UNRATE"),
        "CORE_CPI_YOY": get_core_cpi_yoy(),
        "VIX": get_latest_price("^VIX"),
        "USDCNY": get_latest_price("CNY=X")
    }
    for col in ("DXY", "VIX", "USDCNY"):
        if not pd.isna(row[col]):
            row[col] = round(row[col], 4)
    
    df_new = pd.DataFrame([row])
    save_to_sqlite(df_new, "macro_data", if_exists='append')

def save_hk_index():
    """采集并保存港股指数数据到 SQLite"""
    print("\n📈 开始采集港股指数数据...")
    sf_str = get_southbound_flow()
    south_val = np.nan
    if "亿元" in sf_str and "无" not in sf_str:
        try:
            match = re.search(r'([-+]?\d+\.\d+)', sf_str)
            if match:
                south_val = float(match.group(1))
            else:
                parts = sf_str.split()
                if len(parts) >= 3:
                    south_val = float(parts[-2])
        except Exception as e:
            print(f"  ⚠️ 解析南向资金数值失败: {e}")
    else:
        print(f"  ℹ️ 南向资金无有效数据: {sf_str}")
    print(f"  🧪 解析得到南向资金净流入: {south_val} 亿元")
    row = {
        "date": datetime.today().strftime("%Y-%m-%d"),
        "HSI": get_price_with_fallback("^HSI", "恒生指数"),
        "HSCEI": get_price_with_fallback("^HSCE", "恒生中国企业指数"),
        "HSTECH": get_price_with_fallback("^HSTECH", "恒生科技指数"),
        "SouthboundFlow": south_val,
        "HSNF": get_price_with_fallback("^HSNF", "恒生金融分类指数"),
        "HSNP": get_price_with_fallback("^HSNP", "恒生地产分类指数"),
        "HSHBIO": get_price_with_fallback("^HSBIO", "恒生生物科技指数")
    }
    for col in ("HSI", "HSCEI", "HSTECH", "HSNF", "HSNP", "HSHBIO", "SouthboundFlow"):
        if not pd.isna(row[col]):
            row[col] = round(row[col], 2)
    
    df_new = pd.DataFrame([row])
    save_to_sqlite(df_new, "hk_idx", if_exists='append')

# =====================================================
# 7. 历史数据处理（从 SQLite 加载）
# =====================================================

def load_and_clean_hist_data():
    """
    从 SQLite 加载并清洗港股历史数据
    """
    df = read_from_sqlite("hk_idx_hist", order_by='date ASC')
    
    if df.empty:
        raise FileNotFoundError(f"历史数据不存在（SQLite 中无数据）")
    
    df['date'] = pd.to_datetime(df['date']).dt.date
    df.sort_values('date', inplace=True)

    # 必要列（用于趋势计算）
    required_cols = ['HSI', 'HSCEI', 'HSTECH', 'SouthboundFlow']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"数据缺少必要列：{missing}")

    # 清洗必要列
    df_clean = df.dropna(subset=required_cols, how='any')
    for col in required_cols:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    df_clean = df_clean.dropna(subset=required_cols)

    return df_clean

def compute_trend_from_hist(df, col, ma1, ma2):
    if len(df) < ma2:
        return 0, f"样本不足，需 {ma2} 天"
    series = df[col]
    cur = series.iloc[-1]
    ma2_val = series.rolling(ma2).mean().iloc[-1]
    ma1_val = series.rolling(ma1).mean().iloc[-1]
    if cur < ma2_val:
        return 2, f"跌破 MA{ma2}"
    if cur < ma1_val:
        return 1, f"跌破 MA{ma1}"
    return 0, "趋势良好"

def compute_southbound_risk_from_hist(df):
    if len(df) < 10:
        return 0, "数据不足（少于10日）"
    if df['SouthboundFlow'].tail(10).isna().any():
        return 0, "近10日存在缺失"
    sum10 = df['SouthboundFlow'].tail(10).sum()
    sum5 = df['SouthboundFlow'].tail(5).sum()
    if sum10 < -300:
        return 2, "10日净流出>300亿"
    if sum5 < -100:
        return 1, "5日净流出>100亿"
    return 0, "正常"

def compute_us2y_trend(df, ma_short=20, ma_long=60):
    series = df['US2Y'].dropna()
    if len(series) < ma_long:
        return 0, f"数据不足（至少{ma_long}个有效值）", np.nan, np.nan, np.nan
    cur = series.iloc[-1]
    ma_short_val = series.rolling(ma_short).mean().iloc[-1]
    ma_long_val = series.rolling(ma_long).mean().iloc[-1]
    if cur > ma_short_val and ma_short_val > ma_long_val:
        risk = 2
        desc = f"上行趋势（MA{ma_short} > MA{ma_long}，收益率走高）"
    elif cur > ma_long_val:
        risk = 1
        desc = f"位于长均线上方，中性偏强"
    else:
        risk = 0
        desc = f"下行趋势（跌破MA{ma_long}，收益率走低/宽松预期）"
    return risk, desc, cur, ma_short_val, ma_long_val

def compute_dxy_trend(df, ma_short=20, ma_long=60):
    series = df['DXY'].dropna()
    if len(series) < ma_long:
        return 0, f"数据不足（至少{ma_long}个有效值）", np.nan, np.nan, np.nan
    cur = series.iloc[-1]
    ma_short_val = series.rolling(ma_short).mean().iloc[-1]
    ma_long_val = series.rolling(ma_long).mean().iloc[-1]
    if cur > ma_short_val and ma_short_val > ma_long_val:
        risk = 2
        desc = f"上行趋势（MA{ma_short} > MA{ma_long}，美元走强）"
    elif cur > ma_long_val:
        risk = 1
        desc = f"位于长均线上方，中性偏强"
    else:
        risk = 0
        desc = f"下行趋势（跌破MA{ma_long}，美元走弱）"
    return risk, desc, cur, ma_short_val, ma_long_val

def get_latest_valid(df, col):
    """从 DataFrame 中提取指定列的最新非空值及其日期"""
    sub = df[['date', col]].dropna(subset=[col])
    if sub.empty:
        return np.nan, None
    row = sub.iloc[-1]
    return row[col], row['date']

# =====================================================
# 8. PDF 报告生成
# =====================================================

def generate_pdf_report(captured_text, pdf_path):
    if not REPORTLAB_AVAILABLE:
        print("⚠️ reportlab 未安装，跳过PDF生成。")
        return

    lines = captured_text.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if "【当前指标状态】" in line:
            start_idx = i
            break
    if start_idx is None:
        report_lines = lines
    else:
        report_lines = lines[start_idx:]

    color_map = {
        "🟢": "green",
        "🟡": "gold",
        "🟠": "orange",
        "🔴": "red",
        "⚪": "gray",
    }

    font_paths = [
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    font_registered = False
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('ChineseFont', fp))
                font_registered = True
                break
            except:
                pass
    if not font_registered:
        print("⚠️ 未找到中文字体，PDF中文可能显示为乱码。")
        font_name = 'Helvetica'
    else:
        font_name = 'ChineseFont'

    styles = getSampleStyleSheet()
    main_title_style = ParagraphStyle('MainTitleStyle', parent=styles['Heading1'],
                                      fontName=font_name, fontSize=20, spaceAfter=4,
                                      alignment=1)
    date_style = ParagraphStyle('DateStyle', parent=styles['Normal'],
                                fontName=font_name, fontSize=10, spaceAfter=12,
                                alignment=1)
    sub_title_style = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'],
                                     fontName=font_name, fontSize=14, spaceAfter=8)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'],
                                fontName=font_name, fontSize=10, spaceAfter=4)

    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                            leftMargin=10*mm, rightMargin=10*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    story = []
    story.append(Paragraph("港股宏观概要", main_title_style))
    today_date = datetime.now().strftime("%Y-%m-%d")
    story.append(Paragraph(today_date, date_style))
    story.append(Spacer(1, 6*mm))

    for line in report_lines:
        if line.strip() == "":
            story.append(Spacer(1, 6*mm))
            continue
        escaped = html.escape(line)
        for emoji, color in color_map.items():
            if emoji in escaped:
                escaped = escaped.replace(emoji, f'<font color="{color}">●</font>')
        if '【' in line and '】' in line:
            story.append(Paragraph(escaped, sub_title_style))
        else:
            story.append(Paragraph(escaped, body_style))

    doc.build(story)
    print(f"📄 PDF报告已保存至: {pdf_path}")

# =====================================================
# 8.5 纯文本报告生成
# =====================================================

def save_text_report(captured_text, report_path):
    """
    保存纯文本报告到指定路径
    :param captured_text: 捕获的文本内容
    :param report_path: 报告保存路径
    """
    try:
        # 确保目录存在
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 提取报告核心内容（从【当前指标状态】开始）
        lines = captured_text.splitlines()
        start_idx = None
        for i, line in enumerate(lines):
            if "【当前指标状态】" in line:
                start_idx = i
                break
        
        # 添加报告头部
        header = f"""
{'='*70}
港股宏观风险监控报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*70}

"""
        
        if start_idx is None:
            report_content = header + captured_text
        else:
            report_content = header + "\n".join(lines[start_idx:])
        
        # 写入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"📄 文本报告已保存至: {report_path}")
        return True
    except Exception as e:
        print(f"⚠️ 保存文本报告失败: {e}")
        return False

# =====================================================
# 9. 风险检查主函数
# =====================================================

def risk_check():
    # 重定向 stdout 以捕获所有打印内容（用于 PDF）
    original_stdout = sys.stdout
    buffer = io.StringIO()
    class Tee:
        def __init__(self, *files):
            self.files = files
        def write(self, obj):
            for f in self.files:
                f.write(obj)
        def flush(self):
            for f in self.files:
                f.flush()
    sys.stdout = Tee(original_stdout, buffer)
    try:
        # ========== 1. 从 SQLite 加载宏观数据 ==========
        macro_df = read_from_sqlite("macro_data", order_by='date ASC')
        
        if macro_df.empty:
            print("⚠️ SQLite 中无宏观数据，正在采集...")
            save_macro_data()
            macro_df = read_from_sqlite("macro_data", order_by='date ASC')
            if macro_df.empty:
                print("❌ 无宏观数据可用，请检查网络或数据库")
                return
        
        print(f"✅ 从 SQLite 加载宏观数据，共 {len(macro_df)} 行")
        macro_df['date'] = pd.to_datetime(macro_df['date'])
        macro_df.sort_values('date', inplace=True)

        # ---- 获取每个指标的最新有效值及日期 ----
        macro_latest = {}
        for col in ['DXY', 'US2Y', 'US10Y', 'US30Y', 'USDCNY', 'VIX', 'FEDFUNDS', 'SOFR', 'UNRATE', 'CORE_CPI_YOY']:
            val, dt = get_latest_valid(macro_df, col)
            macro_latest[col] = {'value': val, 'date': dt}

        # ========== 实时获取 FRED 关键指标 ==========
        print("\n📡 实时获取 FRED 关键指标...")
        real_time_cols = {
            'FEDFUNDS': ('FEDFUNDS', get_fred),
            'SOFR': ('SOFR', get_fred),
            'UNRATE': ('UNRATE', get_fred),
            'CORE_CPI_YOY': ('CORE_CPI_YOY', get_core_cpi_yoy)
        }
        for key, (col, func) in real_time_cols.items():
            try:
                if col == 'CORE_CPI_YOY':
                    val = func()
                else:
                    val = func(col)
                if not pd.isna(val):
                    macro_latest[key] = {'value': val, 'date': datetime.now().date()}
                    print(f"  ✅ {key} = {val:.2f} (实时)")
                else:
                    print(f"  ⚠️ {key} 实时获取失败，保留数据库值")
            except Exception as e:
                print(f"  ❌ 获取 {key} 异常: {e}")

        # ========== 2. 从 SQLite 加载港股历史数据 ==========
        try:
            hist_df = load_and_clean_hist_data()
            print(f"✅ 从 SQLite 加载历史数据成功，共 {len(hist_df)} 条有效记录")
        except FileNotFoundError:
            print(f"❌ 历史数据不存在，将跳过南向资金和指数趋势分析。")
            hist_df = pd.DataFrame()
        except Exception as e:
            print(f"❌ 加载历史数据失败: {e}")
            hist_df = pd.DataFrame()

        if hist_df.empty:
            print("⚠️ 历史数据为空（可能因清洗后无有效数据），将跳过南向资金和指数趋势分析。")
            sf_risk = 0
            sf_msg = "无数据"
            sf_latest = np.nan
            sf_date = "N/A"
            hsi_risk = 0
            hsi_msg = "无数据"
            hstech_risk = 0
            hstech_msg = "无数据"
            hscei_risk = 0
            hscei_msg = "无数据"
            has_hist = False
        else:
            has_hist = True
            latest_hist = hist_df.iloc[-1]
            sf_date = latest_hist['date']
            sf_risk, sf_msg = compute_southbound_risk_from_hist(hist_df)
            sf_latest = latest_hist["SouthboundFlow"]
            hsi_risk, hsi_msg = compute_trend_from_hist(hist_df, 'HSI', 60, 120)
            hstech_risk, hstech_msg = compute_trend_from_hist(hist_df, 'HSTECH', 60, 120)
            hscei_risk, hscei_msg = compute_trend_from_hist(hist_df, 'HSCEI', 120, 250)

        # ========== 3. 从历史数据获取 VHSI ==========
        vhsi_val = np.nan
        vhsi_date = None
        if has_hist and 'VHSI' in hist_df.columns:
            vhsi_series = hist_df['VHSI'].dropna()
            if not vhsi_series.empty:
                vhsi_val = vhsi_series.iloc[-1]
                vhsi_date = hist_df.loc[vhsi_series.index[-1], 'date']
                print(f"  ✅ 从历史数据获取 VHSI = {vhsi_val:.2f} (日期: {vhsi_date})")
            else:
                print("  ⚠️ 历史数据中 VHSI 列全为空")
        else:
            print("  ⚠️ 历史数据中无 VHSI 列或历史数据为空")

        # ========== 4. 阈值参考表 ==========
        print("\n" + "=" * 70)
        print("【指标阈值参考表】")
        print(f"{'指标':<10} {'低风险':<14} {'中风险':<16} {'高风险':<16} {'极高风险'}")
        print("-" * 70)
        print(f"{'DXY':<10} {'<103':<14} {'103 ~ 106':<16} {'>106':<16} {'-'}")
        print(f"{'US2Y':<10} {'<3.8%':<14} {'3.8% ~ 4.2%':<16} {'>4.2%':<16} {'-'}")
        print(f"{'US10Y':<10} {'<4.6%':<14} {'4.6% ~ 5.0%':<16} {'>5.0%':<16} {'-'}")
        print(f"{'US30Y':<10} {'<4.8%':<14} {'4.8% ~ 5.0%':<16} {'5.0% ~ 5.5%':<16} {'>5.5%'}")
        print(f"{'USDCNY':<10} {'<7.25':<14} {'7.25 ~ 7.40':<16} {'>7.40':<16} {'-'}")
        print(f"{'VIX':<10} {'≤25':<14} {'25 ~ 35':<16} {'35 ~ 50':<16} {'>50'}")
        print(f"{'VHSI':<10} {'<20':<14} {'20 ~ 30':<16} {'30 ~ 40':<16} {'>40'}")
        print(f"{'南向资金':<10} {'-':<14} {'5日净流出>100亿':<16} {'10日净流出>300亿':<16} {'-'}")
        print(f"{'HSI趋势':<10} {'-':<14} {'跌破MA60':<16} {'跌破MA120':<16} {'-'}")
        print(f"{'HSTECH趋势':<10} {'-':<14} {'跌破MA60':<16} {'跌破MA120':<16} {'-'}")
        print(f"{'HSCEI趋势':<10} {'-':<14} {'跌破MA120':<16} {'跌破MA250':<16} {'-'}")
        print("=" * 70)

        # ========== 5. 当前指标状态 ==========
        print("\n【当前指标状态】")

        def get_ma_details(df, col):
            series = df[col].dropna()
            if len(series) < 20:
                return None, None, None, None, None, "数据不足（少于20天）"
            cur = series.iloc[-1]
            ma20 = series.rolling(20).mean().iloc[-1]
            ma60 = series.rolling(60).mean().iloc[-1] if len(series) >= 60 else np.nan
            ma120 = series.rolling(120).mean().iloc[-1] if len(series) >= 120 else np.nan
            ma250 = series.rolling(250).mean().iloc[-1] if len(series) >= 250 else np.nan
            return cur, ma20, ma60, ma120, ma250, None

        # 5a. 港股指数趋势
        if has_hist:
            hsi_light = "🟡" if hsi_risk == 1 else "🟠" if hsi_risk == 2 else "🟢"
            hstech_light = "🟡" if hstech_risk == 1 else "🟠" if hstech_risk == 2 else "🟢"
            hscei_light = "🟡" if hscei_risk == 1 else "🟠" if hscei_risk == 2 else "🟢"

            # HSI
            hsi_cur, hsi_ma20, hsi_ma60, hsi_ma120, hsi_ma250, hsi_err = get_ma_details(hist_df, 'HSI')
            if hsi_err:
                print(f"HSI Trend  : {hsi_light} {hsi_msg} ({hsi_err})")
            else:
                ma_parts = []
                if not pd.isna(hsi_ma20): ma_parts.append(f"MA20={hsi_ma20:.2f}")
                if not pd.isna(hsi_ma60): ma_parts.append(f"MA60={hsi_ma60:.2f}")
                if not pd.isna(hsi_ma120): ma_parts.append(f"MA120={hsi_ma120:.2f}")
                if not pd.isna(hsi_ma250): ma_parts.append(f"MA250={hsi_ma250:.2f}")
                ma_str = ", ".join(ma_parts) if ma_parts else ""
                print(f"HSI Trend  : {hsi_light} {hsi_msg}  (当前={hsi_cur:.2f}, {ma_str})")

            # HSTECH
            hstech_cur, hstech_ma20, hstech_ma60, hstech_ma120, hstech_ma250, hstech_err = get_ma_details(hist_df, 'HSTECH')
            if hstech_err:
                print(f"HSTECH Trend: {hstech_light} {hstech_msg} ({hstech_err})")
            else:
                ma_parts = []
                if not pd.isna(hstech_ma20): ma_parts.append(f"MA20={hstech_ma20:.2f}")
                if not pd.isna(hstech_ma60): ma_parts.append(f"MA60={hstech_ma60:.2f}")
                if not pd.isna(hstech_ma120): ma_parts.append(f"MA120={hstech_ma120:.2f}")
                if not pd.isna(hstech_ma250): ma_parts.append(f"MA250={hstech_ma250:.2f}")
                ma_str = ", ".join(ma_parts) if ma_parts else ""
                print(f"HSTECH Trend: {hstech_light} {hstech_msg}  (当前={hstech_cur:.2f}, {ma_str})")

            # HSCEI
            hscei_cur, hscei_ma20, hscei_ma60, hscei_ma120, hscei_ma250, hscei_err = get_ma_details(hist_df, 'HSCEI')
            if hscei_err:
                print(f"HSCEI Trend : {hscei_light} {hscei_msg} ({hscei_err})")
            else:
                ma_parts = []
                if not pd.isna(hscei_ma20): ma_parts.append(f"MA20={hscei_ma20:.2f}")
                if not pd.isna(hscei_ma60): ma_parts.append(f"MA60={hscei_ma60:.2f}")
                if not pd.isna(hscei_ma120): ma_parts.append(f"MA120={hscei_ma120:.2f}")
                if not pd.isna(hscei_ma250): ma_parts.append(f"MA250={hscei_ma250:.2f}")
                ma_str = ", ".join(ma_parts) if ma_parts else ""
                print(f"HSCEI Trend : {hscei_light} {hscei_msg}  (当前={hscei_cur:.2f}, {ma_str})")
        else:
            print("HSI Trend  : 无数据")
            print("HSTECH Trend: 无数据")
            print("HSCEI Trend : 无数据")

        # 5b. US2Y 和 DXY 趋势
        us2y_risk, us2y_desc, cur_us2y, ma20_us2y, ma60_us2y = compute_us2y_trend(macro_df)
        us2y_light = ["🟢", "🟡", "🔴"][us2y_risk]
        if not pd.isna(cur_us2y):
            us2y_date = macro_latest['US2Y']['date']
            date_str = us2y_date.strftime('%Y-%m-%d') if us2y_date else "N/A"
            print(f"US2Y Trend : {us2y_light} {us2y_desc}  (当前={cur_us2y:.2f}%, MA20={ma20_us2y:.2f}%, MA60={ma60_us2y:.2f}%, 最新日期={date_str})")
        else:
            print("US2Y Trend : 数据不足")

        dxy_risk, dxy_desc, cur_dxy, ma20_dxy, ma60_dxy = compute_dxy_trend(macro_df)
        dxy_light = ["🟢", "🟡", "🔴"][dxy_risk]
        if not pd.isna(cur_dxy):
            dxy_date = macro_latest['DXY']['date']
            date_str = dxy_date.strftime('%Y-%m-%d') if dxy_date else "N/A"
            print(f"DXY Trend  : {dxy_light} {dxy_desc}  (当前={cur_dxy:.2f}, MA20={ma20_dxy:.2f}, MA60={ma60_dxy:.2f}, 最新日期={date_str})")
        else:
            print("DXY Trend  : 数据不足")

        # 5c. 南向资金
        if has_hist:
            sf_light = ["🟢", "🟡", "🟠"][min(sf_risk, 2)] if sf_risk in [0,1,2] else "⚪"
            print(f"\nSouthbound : {sf_latest:6.2f}亿元 (日期: {sf_date}) {sf_light} {sf_msg}")
        else:
            print("\nSouthbound : 无历史数据")

        # 5d. 其他指标（使用最新有效值）
        indicators = {
            "US10Y": {"col": "US10Y", "yellow": 4.6, "red": 5.0, "extreme": None,
                      "desc": ["正常", "中风险", "高风险", None], "range": ["<4.6", "4.6~5.0", ">5.0", None]},
            "US30Y": {"col": "US30Y", "yellow": 4.8, "red": 5.0, "extreme": 5.5,
                      "desc": ["正常", "中风险", "高风险", "极高风险"], "range": ["<4.8", "4.8~5.0", "5.0~5.5", ">5.5"]},
            "USDCNY": {"col": "USDCNY", "yellow": 7.25, "red": 7.40, "extreme": None,
                       "desc": ["正常", "中风险", "高风险", None], "range": ["<7.25", "7.25~7.40", ">7.40", None]},
            "VIX": {"col": "VIX", "yellow": 25, "red": 35, "extreme": 50,
                    "desc": ["正常", "中风险", "高风险", "极高风险"], "range": ["≤25", "25~35", "35~50", ">50"]},
        }

        for name, cfg in indicators.items():
            col = cfg["col"]
            val = macro_latest[col]['value']
            dt = macro_latest[col]['date']
            if pd.isna(val):
                risk, desc, rng = 0, "数据缺失", ""
                light = "⚪"
                val_str = "N/A"
                date_str = ""
            else:
                if cfg["extreme"] is not None and val > cfg["extreme"]:
                    risk, desc, rng = 3, cfg["desc"][3], cfg["range"][3]
                elif val > cfg["red"]:
                    risk, desc, rng = 2, cfg["desc"][2], cfg["range"][2]
                elif val > cfg["yellow"]:
                    risk, desc, rng = 1, cfg["desc"][1], cfg["range"][1]
                else:
                    risk, desc, rng = 0, cfg["desc"][0], cfg["range"][0]
                light = ["🟢", "🟡", "🟠", "🔴"][min(risk, 3)]
                val_str = f"{val:.2f}"
                date_str = f"(日期: {dt.strftime('%Y-%m-%d')})" if dt else ""
            print(f"{name:<10} {val_str:>6} {light} {desc} {date_str} ({rng})")

        # ---- VHSI 展示（从历史数据获取） ----
        if pd.isna(vhsi_val):
            print(f"VHSI       N/A ⚪ 数据缺失")
        else:
            if vhsi_val > 40:
                risk, desc = 3, "极高风险"
                light = "🔴"
            elif vhsi_val > 30:
                risk, desc = 2, "高风险"
                light = "🟠"
            elif vhsi_val > 20:
                risk, desc = 1, "中风险"
                light = "🟡"
            else:
                risk, desc = 0, "正常"
                light = "🟢"
            date_display = f"(日期: {vhsi_date})" if vhsi_date else "(无日期)"
            print(f"VHSI       {vhsi_val:6.2f} {light} {desc} {date_display}")

        # ========== 6. 综合风险评分 ==========
        print("\n【综合风险评分】")
        liquidity = 0
        dxy_val = macro_latest["DXY"]['value']
        us10y_val = macro_latest["US10Y"]['value']
        us30y_val = macro_latest["US30Y"]['value']
        usdcny_val = macro_latest["USDCNY"]['value']

        if not pd.isna(dxy_val):
            liquidity += 2 if dxy_val > 106 else 1 if dxy_val > 103 else 0
        if not pd.isna(us10y_val):
            liquidity += 2 if us10y_val > 5.0 else 1 if us10y_val > 4.6 else 0
        if not pd.isna(us30y_val):
            liquidity += 2 if us30y_val > 5.0 else 1 if us30y_val > 4.8 else 0
        if not pd.isna(usdcny_val):
            liquidity += 2 if usdcny_val > 7.4 else 1 if usdcny_val > 7.25 else 0
        print(f"Liquidity Score : {liquidity}/8")

        market = 0
        vix_val = macro_latest["VIX"]['value']
        if not pd.isna(vix_val):
            market += 2 if vix_val > 35 else 1 if vix_val > 25 else 0
        if not pd.isna(vhsi_val):
            market += 2 if vhsi_val > 40 else 1 if vhsi_val > 30 else 0
        if has_hist:
            market += sf_risk
            market += hsi_risk
            market += hstech_risk
            market += hscei_risk
        print(f"Market Score    : {market}/10")

        cycle = 0
        us2y_val = macro_latest["US2Y"]['value']
        core_cpi_val = macro_latest["CORE_CPI_YOY"]['value']
        if not pd.isna(us2y_val) and us2y_val > 4.2:
            cycle += 2
        if not pd.isna(core_cpi_val):
            if core_cpi_val > 3.0:
                cycle += 2
            elif core_cpi_val > 2.5:
                cycle += 1
        spread = us10y_val - us2y_val if not pd.isna(us10y_val) and not pd.isna(us2y_val) else np.nan
        if not pd.isna(spread):
            if spread < -0.5:
                cycle += 2
            elif spread < 0:
                cycle += 1
        print(f"Cycle Score     : {cycle}/4")

        total = liquidity + market + cycle
        print(f"Total Score     : {total}/22")

        if total >= 14:
            signal, advice = "🔴 红灯", "建议仓位 0-10%"
        elif total >= 10:
            signal, advice = "🟠 橙灯", "建议仓位 10-30%"
        elif total >= 6:
            signal, advice = "🟡 黄灯", "建议仓位 30-50%"
        else:
            signal, advice = "🟢 绿灯", "建议仓位 50-70%"
        print(f"Signal          : {signal} (阈值区间: ≥14, 10~13, 6~9, 0~5)")
        print(f"仓位建议        : {advice}")

        # ========== 7. FED WATCH 及曲线分析 ==========
        print("\n【FED WATCH 宏观解读】")
        def fed_view(us2y):
            if pd.isna(us2y):
                return "数据缺失"
            if us2y > 4.2:
                return "市场定价进一步加息"
            if us2y < 3.8:
                return "市场定价降息预期"
            return "市场定价高利率长期维持"

        def fed_policy_view(us2y, fedfunds):
            if pd.isna(us2y) or pd.isna(fedfunds):
                return "数据不足"
            gap = us2y - fedfunds
            if gap > 0.5:
                return "市场预期未来加息"
            if gap < -0.5:
                return "市场预期未来降息"
            return "市场预期维持利率"

        def curve_analysis(us2y, us10y):
            if pd.isna(us2y) or pd.isna(us10y):
                return np.nan, "数据不足"
            spr = us10y - us2y
            if spr > 0.8:
                msg = "曲线走陡：经济韧性或通胀回升"
            elif spr > 0:
                msg = "正常曲线"
            elif spr > -0.5:
                msg = "倒挂：增长放缓"
            else:
                msg = "深度倒挂：衰退风险"
            return spr, msg

        def curve_trend():
            if len(macro_df) < 20:
                return "样本不足"
            now = macro_df["US10Y"].iloc[-1] - macro_df["US2Y"].iloc[-1]
            old = macro_df["US10Y"].iloc[-20] - macro_df["US2Y"].iloc[-20]
            diff = now - old
            if diff > 0.3:
                return "利差扩大（曲线走陡）"
            if diff < -0.3:
                return "利差收窄（曲线走平）"
            return "基本稳定"

        us2y_val = macro_latest["US2Y"]['value']
        us10y_val = macro_latest["US10Y"]['value']
        us30y_val = macro_latest["US30Y"]['value']
        fedfunds_val = macro_latest["FEDFUNDS"]['value']
        sofr_val = macro_latest["SOFR"]['value']
        unrate_val = macro_latest["UNRATE"]['value']
        core_cpi_val = macro_latest["CORE_CPI_YOY"]['value']

        print(f"US2Y       : {us2y_val:.2f}% (日期: {macro_latest['US2Y']['date'].strftime('%Y-%m-%d')})" if not pd.isna(us2y_val) else "US2Y       : N/A")
        print(f"US10Y      : {us10y_val:.2f}% (日期: {macro_latest['US10Y']['date'].strftime('%Y-%m-%d')})" if not pd.isna(us10y_val) else "US10Y      : N/A")
        print(f"US30Y      : {us30y_val:.2f}% (日期: {macro_latest['US30Y']['date'].strftime('%Y-%m-%d')})" if not pd.isna(us30y_val) else "US30Y      : N/A")
        print(f"FEDFUNDS   : {fedfunds_val:.2f}% (日期: {macro_latest['FEDFUNDS']['date'].strftime('%Y-%m-%d')})" if not pd.isna(fedfunds_val) else "FEDFUNDS   : N/A")
        print(f"SOFR       : {sofr_val:.2f}% (日期: {macro_latest['SOFR']['date'].strftime('%Y-%m-%d')})" if not pd.isna(sofr_val) else "SOFR       : N/A")
        print(f"失业率      : {unrate_val:.2f}% (日期: {macro_latest['UNRATE']['date'].strftime('%Y-%m-%d')})" if not pd.isna(unrate_val) else "失业率      : N/A")
        print(f"核心CPI同比  : {core_cpi_val:.2f}% (日期: {macro_latest['CORE_CPI_YOY']['date'].strftime('%Y-%m-%d')})" if not pd.isna(core_cpi_val) else "核心CPI同比  : N/A")
        print(f"政策预期    : {fed_view(us2y_val)}")
        print(f"利率展望    : {fed_policy_view(us2y_val, fedfunds_val)}")
        spread, msg = curve_analysis(us2y_val, us10y_val)
        if not pd.isna(spread):
            print(f"2s10s利差  : {spread:.2f}%")
        else:
            print("2s10s利差  : N/A")
        print(f"收益率曲线  : {msg}")
        print(f"曲线趋势    : {curve_trend()}")

    finally:
        sys.stdout = original_stdout
        captured_text = buffer.getvalue()
        
        # ========== 保存文本报告 ==========
        try:
            txt_path = Path(GlobalConfig.full_report_dir) / "HK_Macro_Dashboard.txt"
            save_text_report(captured_text, txt_path)
        except Exception as e:
            print(f"⚠️ 保存文本报告失败: {e}")
        
        # ========== 生成 PDF 报告 ==========
        try:
            pdf_path = Path(GlobalConfig.full_report_dir) / "HK_Macro_Dashboard.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            generate_pdf_report(captured_text, pdf_path)
        except Exception as e:
            print(f"⚠️ 生成PDF报告失败: {e}")

# =====================================================
# 10. 主程序
# =====================================================

def main():
    start = time.time()
    print("🚀 港股宏观风险监控（使用 SQLite 数据库）启动...")
    
    print(f"📁 数据目录: {DATA_DIR}")
    print(f"🗄️ SQLite数据库目录: {SQLITE_DIR}")
    print(f"🗄️ SQLite数据库文件: {DB_PATH}")

    try:
        risk_check()
    except Exception as e:
        print(f"❌ 运行异常: {e}")
        import traceback
        traceback.print_exc()
    elapsed = time.time() - start
    print(f"\n⏱️ 总耗时: {elapsed:.2f} 秒")
    print("✅ 监控完成")

if __name__ == "__main__":
    main()