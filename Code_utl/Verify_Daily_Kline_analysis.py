#!/usr/bin/env python
# coding: utf-8

"""
Verify_Daily_Kline_analysis.py
数据验证程序 - 验证 hk_daily_kline_analysis 表的日资金流分析数据
功能:
  1. 显示表的基本信息（字段、记录数、日期范围等）
  2. 显示每只股票的数据统计
  3. 显示最新的5条记录（按日期升序）
  4. 检查数据完整性（空值、重复值等）
  5. 检查资金流数据的合理性
  6. 生成验证报告
  7. 保存验证结果到JSON文件
  8. 对比数据字典与数据库表结构的一致性
"""

import os
import sys
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
import warnings
import configparser
from tabulate import tabulate

warnings.filterwarnings('ignore')

# =====================================================
# 1. 路径设置
# =====================================================

def get_project_dir():
    """
    获取项目根目录
    脚本位于 $PROJECT_DIR/Code_utl/ 目录下
    """
    try:
        # 尝试从环境变量获取
        env_dir = os.environ.get('PROJECT_ROOT')
        if env_dir and Path(env_dir).exists():
            return Path(env_dir)

        # 从当前脚本路径推断项目根目录
        script_path = Path(__file__).resolve()

        # 向上一级到达项目根目录
        project_dir = script_path.parent

        # 验证是否真的是项目根目录（检查是否存在 Config 目录）
        if (project_dir / 'Config').exists():
            return project_dir

        # 如果找不到 Config，尝试其他方式
        if script_path.parent.name == 'Code_utl':
            return script_path.parent.parent

        # 尝试从当前工作目录向上查找
        cwd = Path(os.getcwd()).resolve()
        for parent in [cwd] + list(cwd.parents):
            if (parent / 'Config').exists() and (parent / 'Core').exists():
                return parent

        return cwd.parent if cwd.name == 'Code_utl' else cwd

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
# 2. 配置加载和路径初始化
# =====================================================

# 获取项目根目录
project_dir = get_project_dir()
print(f"[INFO] 项目目录: {project_dir}")

# 验证项目目录结构
if not (project_dir / 'Config').exists():
    print(f"[WARN] 项目目录中未找到 Config 目录: {project_dir}")
    parent_dir = project_dir.parent
    if (parent_dir / 'Config').exists():
        project_dir = parent_dir
        print(f"[INFO] 找到项目目录: {project_dir}")

# =====================================================
# 关键修改：添加必要的路径到 sys.path
# =====================================================

# 1. 添加项目根目录
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))
    print(f"[INFO] 已添加项目根目录到 sys.path: {project_dir}")

# 2. 添加 Core 目录（包含 Utl 子目录）
core_dir = project_dir / 'Core'
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))
    print(f"[INFO] 已添加 Core 目录到 sys.path: {core_dir}")

# 3. 直接添加 Utl 目录
utl_dir = project_dir / 'Core' / 'Utl'
if str(utl_dir) not in sys.path:
    sys.path.insert(0, str(utl_dir))
    print(f"[INFO] 已添加 Utl 目录到 sys.path: {utl_dir}")

# =====================================================
# 导入股票列表加载工具（使用修改后的路径）
# =====================================================

try:
    from stock_list_loader import load_stock_list, get_stock_name_map
    print("[INFO] 成功导入 stock_list_loader")
    
    # 从配置文件加载股票列表
    STOCK_LIST = load_stock_list(project_dir / 'Config')
    STOCK_MAP = {item['code']: item for item in STOCK_LIST}
    print(f"[INFO] 从配置文件加载了 {len(STOCK_LIST)} 只股票")
    
except ImportError as e:
    print(f"[ERROR] 无法导入 stock_list_loader: {e}")
    print(f"[ERROR] 请确保文件存在: {utl_dir / 'stock_list_loader.py'}")
    print("[ERROR] 程序退出")
    sys.exit(1)
    
except Exception as e:
    print(f"[ERROR] 加载股票列表失败: {e}")
    print("[ERROR] 请检查 Config/stock_list.json 文件是否存在且格式正确")
    print("[ERROR] 程序退出")
    sys.exit(1)

# 配置文件路径
config_path = project_dir / 'Config' / 'stock_data_analysis.par'
print(f"[INFO] 配置文件路径: {config_path}")

if not config_path.exists():
    alt_path = project_dir.parent / 'Config' / 'stock_data_analysis.par'
    if alt_path.exists():
        config_path = alt_path
        print(f"[INFO] 使用备用配置文件路径: {config_path}")
    else:
        print(f"[ERROR] 配置文件不存在: {config_path}")
        sys.exit(1)

# 加载配置
try:
    from Utl.stock_analysis_utl import load_config, GlobalConfig
    print("[INFO] 成功导入 Utl.stock_analysis_utl")
except ImportError as e:
    print(f"[WARN] 无法导入 Utl.stock_analysis_utl: {e}")
    print("[INFO] 使用本地简化配置加载")

    class GlobalConfig:
        full_data_dir = None
        full_report_dir = None
        full_log_dir = None
        full_temp_dir = None
        full_sqlite_dir = None
        full_db_path = None
        db_name = None

    def load_config(config_path, project_dir):
        """简化版配置加载"""
        config = {}
        cp = configparser.ConfigParser()
        cp.read(config_path, encoding='utf-8')

        if cp.has_section('FOLDERS'):
            for key in cp.options('FOLDERS'):
                value = cp.get('FOLDERS', key).strip().strip("'").strip('"')
                config[key] = value

        if cp.has_section('DATABASE'):
            config['db_name'] = cp.get('DATABASE', 'db_name', fallback='HK_Stock.db').strip()
        else:
            config['db_name'] = 'HK_Stock.db'

        data_rel = config.get('data_dir', 'Data')
        config['full_data_dir'] = os.path.join(str(project_dir), data_rel)

        report_rel = config.get('report_dir', 'Report')
        config['full_report_dir'] = os.path.join(str(project_dir), report_rel)

        log_rel = config.get('log_dir', 'Log')
        config['full_log_dir'] = os.path.join(str(project_dir), log_rel)

        temp_rel = config.get('temp_dir', 'Temp')
        config['full_temp_dir'] = os.path.join(str(project_dir), temp_rel)

        sqlite_rel = config.get('sqlite_dir', 'SQLiteDB')
        config['full_sqlite_dir'] = os.path.join(str(project_dir), sqlite_rel)

        db_name = config.get('db_name', 'HK_Stock.db')
        config['full_db_path'] = os.path.join(config['full_sqlite_dir'], db_name)

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
    GlobalConfig.update_paths(CONFIG, project_dir)
else:
    GlobalConfig.full_data_dir = CONFIG.get('full_data_dir')
    GlobalConfig.full_report_dir = CONFIG.get('full_report_dir')
    GlobalConfig.full_log_dir = CONFIG.get('full_log_dir')
    GlobalConfig.full_temp_dir = CONFIG.get('full_temp_dir')
    GlobalConfig.full_sqlite_dir = CONFIG.get('full_sqlite_dir')
    GlobalConfig.db_name = CONFIG.get('db_name', 'HK_Stock.db')
    GlobalConfig.full_db_path = CONFIG.get('full_db_path')

# 强制 UTF-8 输出
setup_windows_encoding()

# 使用 GlobalConfig 中的路径
DB_DIR = Path(GlobalConfig.full_sqlite_dir)
DB_PATH = Path(GlobalConfig.full_db_path)
REPORT_DIR = Path(GlobalConfig.full_report_dir)

print(f"[INFO] 数据库目录: {DB_DIR}")
print(f"[INFO] 数据库路径: {DB_PATH}")
print(f"[INFO] 报告目录: {REPORT_DIR}")

# 显示股票列表摘要
print(f"\n[INFO] 股票列表摘要:")
print(f"  总股票数: {len(STOCK_LIST)}")
if STOCK_LIST:
    print(f"  股票代码范围: {STOCK_LIST[0]['code']} ~ {STOCK_LIST[-1]['code']}")
    sectors = set(s.get('sector', 'N/A') for s in STOCK_LIST)
    print(f"  涉及行业: {', '.join(sectors)}")
print()

# =====================================================
# 3. 数据字典加载
# =====================================================

def load_data_dictionary():
    """加载数据字典 hk_daily_kline_analysis.json"""
    data_dict_path = project_dir / 'Config' / 'hk_daily_kline_analysis.json'
    
    if not data_dict_path.exists():
        print(f"[WARN] 数据字典文件不存在: {data_dict_path}")
        return None
    
    try:
        with open(data_dict_path, 'r', encoding='utf-8') as f:
            data_dict = json.load(f)
        print(f"[INFO] 成功加载数据字典: {data_dict_path}")
        return data_dict
    except Exception as e:
        print(f"[ERROR] 加载数据字典失败: {e}")
        return None

# =====================================================
# 4. 数据库连接和表结构检测
# =====================================================

def get_db_connection():
    """获取数据库连接"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.text_factory = str
    return conn

def get_table_columns(conn, table_name):
    """获取表的列名列表"""
    query = f"PRAGMA table_info({table_name});"
    df = pd.read_sql_query(query, conn)
    return df['name'].tolist()

def get_available_columns(conn, table_name, required_columns):
    """检查哪些列存在于表中"""
    existing_columns = set(get_table_columns(conn, table_name))
    available = {}
    for col in required_columns:
        available[col] = col in existing_columns
    return available

# =====================================================
# 5. 数据验证函数（动态列检测）
# =====================================================

def get_table_info(conn, table_name):
    """获取表的列信息"""
    query = f"PRAGMA table_info({table_name});"
    df = pd.read_sql_query(query, conn)
    return df

def get_table_count(conn, table_name):
    """获取表的记录数"""
    query = f"SELECT COUNT(*) as count FROM {table_name};"
    df = pd.read_sql_query(query, conn)
    return df['count'].iloc[0]

def get_stock_statistics(conn, table_name, available_cols):
    """获取每只股票的统计数据（动态根据可用列调整）"""
    # 基础字段
    select_parts = [
        "stock_code",
        "stock_name",
        "COUNT(*) as record_count",
        "MIN(date) as first_date",
        "MAX(date) as last_date",
        "COUNT(DISTINCT date) as trading_days"
    ]
    
    # 根据可用列添加额外统计
    if available_cols.get('close', False) or available_cols.get('close_price', False):
        close_col = 'close_price' if available_cols.get('close_price', False) else 'close'
        select_parts.append(f"AVG({close_col}) as avg_close")
    
    if available_cols.get('amount', False):
        select_parts.append(f"AVG(amount) as avg_amount")
        select_parts.append(f"SUM(amount) as total_amount")
    
    if available_cols.get('main_net_inflow', False):
        select_parts.append(f"AVG(main_net_inflow) as avg_main_net_inflow")
    
    if available_cols.get('retail_net_inflow', False):
        select_parts.append(f"AVG(retail_net_inflow) as avg_retail_net_inflow")
    
    if available_cols.get('net_inflow', False):
        select_parts.append(f"AVG(net_inflow) as avg_net_inflow")
    
    if available_cols.get('turnover_rate', False):
        select_parts.append(f"AVG(turnover_rate) as avg_turnover_rate")
    
    query = f"""
        SELECT {', '.join(select_parts)}
        FROM {table_name}
        GROUP BY stock_code, stock_name
        ORDER BY stock_code
    """
    
    df = pd.read_sql_query(query, conn)
    return df

def get_table_sample(conn, table_name, limit=5):
    """获取表的最新记录（按日期升序）"""
    try:
        # 获取最新的 N 条记录（按日期降序取最新，然后升序显示）
        query = f"""
            SELECT * FROM {table_name} 
            ORDER BY date DESC 
            LIMIT {limit}
        """
        df = pd.read_sql_query(query, conn)
        
        # 按日期升序排列
        if not df.empty and 'date' in df.columns:
            df = df.sort_values('date', ascending=True)
        
        return df
    except Exception as e:
        print(f"  ⚠️ 获取样本数据失败: {e}")
        return pd.DataFrame()

def check_null_values(conn, table_name):
    """检查空值"""
    try:
        columns = get_table_info(conn, table_name)['name'].tolist()
        null_counts = {}

        for col in columns:
            if col != 'id':  # 跳过 id 列
                query = f"""
                    SELECT COUNT(*) as null_count 
                    FROM {table_name} 
                    WHERE {col} IS NULL OR {col} = ''
                """
                df = pd.read_sql_query(query, conn)
                null_counts[col] = df['null_count'].iloc[0]

        return null_counts
    except Exception as e:
        print(f"  ⚠️ 空值检查失败: {e}")
        return {}

def check_duplicates(conn, table_name):
    """检查重复记录（按股票代码和日期）"""
    try:
        query = f"""
            SELECT stock_code, date, COUNT(*) as count 
            FROM {table_name} 
            GROUP BY stock_code, date 
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"  ⚠️ 重复检查失败: {e}")
        return pd.DataFrame()

def check_cash_flow_reasonability(conn, table_name, available_cols):
    """检查资金流数据的合理性（动态根据可用列调整）"""
    try:
        # 构建条件
        conditions = []
        select_parts = [
            "stock_code",
            "date"
        ]
        
        # 添加可用列到SELECT
        for col in ['close', 'close_price', 'amount', 'main_net_inflow', 
                   'retail_net_inflow', 'net_inflow', 'turnover_rate']:
            if available_cols.get(col, False):
                select_parts.append(col)
        
        # 构建WHERE条件
        if available_cols.get('main_net_inflow', False) and available_cols.get('retail_net_inflow', False) and available_cols.get('net_inflow', False):
            conditions.append("main_net_inflow + retail_net_inflow != net_inflow")
        
        if available_cols.get('main_net_inflow', False) and available_cols.get('amount', False):
            conditions.append("ABS(main_net_inflow) > amount")
        
        if available_cols.get('retail_net_inflow', False) and available_cols.get('amount', False):
            conditions.append("ABS(retail_net_inflow) > amount")
        
        if available_cols.get('net_inflow', False) and available_cols.get('amount', False):
            conditions.append("ABS(net_inflow) > amount")
        
        if available_cols.get('turnover_rate', False):
            conditions.append("turnover_rate < 0 OR turnover_rate > 100")
        
        # 价格检查
        if available_cols.get('close', False):
            conditions.append("close <= 0")
        if available_cols.get('close_price', False):
            conditions.append("close_price <= 0")
        
        if available_cols.get('amount', False):
            conditions.append("amount < 0")
        
        if not conditions:
            # 如果没有可检查的条件，返回空DataFrame
            return pd.DataFrame()
        
        query = f"""
            SELECT 
                {', '.join(select_parts)},
                CASE 
                    {' WHEN ' + ' WHEN '.join([f"{cond} THEN '{desc}'" for cond, desc in [
                        ("main_net_inflow + retail_net_inflow != net_inflow", "Net inflow mismatch"),
                        ("ABS(main_net_inflow) > amount", "Main inflow exceeds amount"),
                        ("ABS(retail_net_inflow) > amount", "Retail inflow exceeds amount"),
                        ("ABS(net_inflow) > amount", "Net inflow exceeds amount"),
                        ("turnover_rate < 0 OR turnover_rate > 100", "Turnover rate out of range"),
                        ("close <= 0", "Invalid close price"),
                        ("close_price <= 0", "Invalid close price"),
                        ("amount < 0", "Negative amount")
                    ] if eval(cond.split()[0]) in [c.split()[0] if ' ' in c else c for c in select_parts] or True])}
                    ELSE NULL
                END as error_type
            FROM {table_name}
            WHERE {' OR '.join(conditions)}
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"  ⚠️ 资金流合理性检查失败: {e}")
        return pd.DataFrame()

def check_missing_stocks(conn, table_name):
    """检查是否有缺失的股票"""
    query = f"SELECT DISTINCT stock_code FROM {table_name}"
    df = pd.read_sql_query(query, conn)
    existing_codes = set(df['stock_code'].astype(str).tolist())
    
    # 使用从配置文件加载的股票列表
    expected_codes = set(STOCK_MAP.keys())
    missing_codes = expected_codes - existing_codes
    
    # 额外检查：数据库中是否有不在配置文件中的股票
    extra_codes = existing_codes - expected_codes
    
    return missing_codes, extra_codes

def compare_with_data_dictionary(conn, table_name, data_dict):
    """对比数据库表结构与数据字典的一致性"""
    if data_dict is None:
        return None
    
    # 获取表结构
    table_info = get_table_info(conn, table_name)
    db_columns = set(table_info['name'].tolist())
    
    # 获取数据字典中的字段 - 支持多种数据结构
    dict_fields = set()
    
    # 方法1: 从 table_schema.columns 获取
    if 'table_schema' in data_dict and 'columns' in data_dict['table_schema']:
        for field in data_dict['table_schema']['columns']:
            if 'name' in field:
                dict_fields.add(field['name'])
    
    # 方法2: 从 data_dictionary.column_definitions 获取
    elif 'data_dictionary' in data_dict and 'column_definitions' in data_dict['data_dictionary']:
        for field in data_dict['data_dictionary']['column_definitions']:
            if 'name' in field:
                dict_fields.add(field['name'])
    
    # 方法3: 从 fields 获取（旧格式）
    elif 'fields' in data_dict:
        for field in data_dict['fields']:
            if 'name' in field:
                dict_fields.add(field['name'])
    
    # 方法4: 从 table_schema 直接获取字段名列表
    elif 'table_schema' in data_dict and 'fields' in data_dict['table_schema']:
        for field in data_dict['table_schema']['fields']:
            if 'name' in field:
                dict_fields.add(field['name'])
    
    # 检查字段差异
    missing_in_db = dict_fields - db_columns
    extra_in_db = db_columns - dict_fields
    
    comparison_result = {
        'missing_in_db': sorted(missing_in_db),
        'extra_in_db': sorted(extra_in_db),
        'missing_in_dict': sorted(db_columns - dict_fields) if dict_fields else [],
        'db_columns': sorted(db_columns),
        'dict_fields': sorted(dict_fields),
        'is_consistent': len(missing_in_db) == 0 and len(extra_in_db) == 0
    }
    
    return comparison_result
    
def get_cash_flow_summary(conn, table_name, available_cols):
    """获取资金流汇总统计（动态根据可用列调整）"""
    select_parts = ["COUNT(*) as total_records"]
    
    if available_cols.get('amount', False):
        select_parts.append("SUM(amount) as total_amount")
    
    if available_cols.get('main_net_inflow', False):
        select_parts.append("SUM(main_net_inflow) as total_main_net_inflow")
        select_parts.append("AVG(main_net_inflow) as avg_main_net_inflow")
    
    if available_cols.get('retail_net_inflow', False):
        select_parts.append("SUM(retail_net_inflow) as total_retail_net_inflow")
        select_parts.append("AVG(retail_net_inflow) as avg_retail_net_inflow")
    
    if available_cols.get('net_inflow', False):
        select_parts.append("SUM(net_inflow) as total_net_inflow")
        select_parts.append("AVG(net_inflow) as avg_net_inflow")
    
    query = f"""
        SELECT {', '.join(select_parts)}
        FROM {table_name}
    """
    df = pd.read_sql_query(query, conn)
    return df

# =====================================================
# 6. 显示函数
# =====================================================

def display_header(text, char='='):
    """显示标题"""
    print()
    print(char * 80)
    print(f" {text}")
    print(char * 80)

def display_table_summary(conn, table_name, available_cols):
    """显示表的摘要信息"""
    print("\n" + "=" * 80)
    print(f" 📊 表名: {table_name}")
    print("=" * 80)

    # 基本信息
    count = get_table_count(conn, table_name)
    print(f"  总记录数: {count:,}")

    # 列信息
    col_info = get_table_info(conn, table_name)
    print(f"  字段数: {len(col_info)}")

    # 显示字段信息
    print("\n  字段列表:")
    field_data = []
    for _, row in col_info.iterrows():
        field_data.append([
            row['name'],
            row['type'],
            'NOT NULL' if row['notnull'] else 'NULL',
            'PK' if row['pk'] else ''
        ])

    print(tabulate(field_data,
                   headers=['字段名', '类型', '非空', '主键'],
                   tablefmt='grid',
                   stralign='left'))

    # 股票统计
    stock_stats = get_stock_statistics(conn, table_name, available_cols)
    if not stock_stats.empty:
        print(f"\n  📈 股票统计:")
        print(f"    股票数量: {len(stock_stats)} 只")
        print(f"    总交易天数: {stock_stats['trading_days'].sum():,}")
        print(f"    平均每只股票记录数: {stock_stats['record_count'].mean():.1f}")

    # 日期范围
    if not stock_stats.empty:
        min_date = stock_stats['first_date'].min()
        max_date = stock_stats['last_date'].max()
        print(f"\n  📅 全局日期范围:")
        print(f"    最早日期: {min_date}")
        print(f"    最晚日期: {max_date}")
        
        # 资金流汇总
        cash_flow_summary = get_cash_flow_summary(conn, table_name, available_cols)
        if not cash_flow_summary.empty:
            print(f"\n  💰 资金流汇总:")
            if 'total_amount' in cash_flow_summary.columns:
                print(f"    总成交额: {cash_flow_summary['total_amount'].iloc[0]:,.0f}")
            if 'total_main_net_inflow' in cash_flow_summary.columns:
                print(f"    总主力净流入: {cash_flow_summary['total_main_net_inflow'].iloc[0]:,.0f}")
            if 'total_retail_net_inflow' in cash_flow_summary.columns:
                print(f"    总散户净流入: {cash_flow_summary['total_retail_net_inflow'].iloc[0]:,.0f}")
            if 'total_net_inflow' in cash_flow_summary.columns:
                print(f"    总净流入: {cash_flow_summary['total_net_inflow'].iloc[0]:,.0f}")
            if 'avg_main_net_inflow' in cash_flow_summary.columns:
                print(f"    平均主力净流入: {cash_flow_summary['avg_main_net_inflow'].iloc[0]:,.2f}")
            if 'avg_retail_net_inflow' in cash_flow_summary.columns:
                print(f"    平均散户净流入: {cash_flow_summary['avg_retail_net_inflow'].iloc[0]:,.2f}")

def display_stock_statistics(conn, table_name, available_cols):
    """显示每只股票的统计信息"""
    print("\n" + "-" * 80)
    print(" 📈 每只股票资金流统计")
    print("-" * 80)

    stock_stats = get_stock_statistics(conn, table_name, available_cols)

    if stock_stats.empty:
        print("  ⚠️ 无数据")
        return

    # 构建表头
    headers = ['状态', '代码', '名称', '记录数', '开始日期', '结束日期']
    
    # 根据可用列添加表头
    if 'avg_close' in stock_stats.columns:
        headers.append('均价')
    if 'avg_amount' in stock_stats.columns:
        headers.append('平均成交额')
    if 'avg_main_net_inflow' in stock_stats.columns:
        headers.append('平均主力净流入')
    if 'avg_retail_net_inflow' in stock_stats.columns:
        headers.append('平均散户净流入')
    if 'avg_net_inflow' in stock_stats.columns:
        headers.append('平均净流入')
    if 'avg_turnover_rate' in stock_stats.columns:
        headers.append('平均换手率')

    # 格式化显示
    display_data = []
    for _, row in stock_stats.iterrows():
        # 检查是否在配置文件中
        in_config = "✓" if row['stock_code'] in STOCK_MAP else "⚠️"
        row_data = [
            in_config,
            row['stock_code'],
            row['stock_name'],
            f"{row['record_count']:,}",
            row['first_date'],
            row['last_date']
        ]
        
        # 根据可用列添加数据
        if 'avg_close' in stock_stats.columns:
            row_data.append(f"{row['avg_close']:.2f}")
        if 'avg_amount' in stock_stats.columns:
            row_data.append(f"{row['avg_amount']:,.0f}")
        if 'avg_main_net_inflow' in stock_stats.columns:
            row_data.append(f"{row['avg_main_net_inflow']:,.0f}")
        if 'avg_retail_net_inflow' in stock_stats.columns:
            row_data.append(f"{row['avg_retail_net_inflow']:,.0f}")
        if 'avg_net_inflow' in stock_stats.columns:
            row_data.append(f"{row['avg_net_inflow']:,.0f}")
        if 'avg_turnover_rate' in stock_stats.columns:
            row_data.append(f"{row['avg_turnover_rate']:.2f}%")
        
        display_data.append(row_data)

    print(tabulate(display_data,
                   headers=headers,
                   tablefmt='grid',
                   stralign='left'))

def display_sample_data(conn, table_name, limit=10):
    """显示样本数据"""
    print("\n" + "-" * 80)
    print(f" 📋 最新 {limit} 条记录 (按日期升序)")
    print("-" * 80)

    df = get_table_sample(conn, table_name, limit)

    if df.empty:
        print("  ⚠️ 无数据")
        return

    # 获取所有列，选择前15个列
    all_columns = df.columns.tolist()
    
    # 优先显示关键列，然后补全到15列
    priority_cols = ['stock_code', 'stock_name', 'date']
    other_cols = [col for col in all_columns if col not in priority_cols]
    
    # 组合：优先列 + 其他列（最多补到15列）
    display_cols = priority_cols + other_cols[:15 - len(priority_cols)]
    
    # 如果列数少于15，全部显示
    if len(display_cols) < 15 and len(all_columns) < 15:
        display_cols = all_columns
    elif len(display_cols) > 15:
        display_cols = display_cols[:15]
    
    df_display = df[display_cols].copy()

    # 格式化数值
    for col in df_display.columns:
        if col in ['close', 'close_price', 'amount', 'main_net_inflow', 
                   'retail_net_inflow', 'net_inflow', 'volume', 'turnover']:
            df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else '')
        elif col == 'turnover_rate':
            df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else '')
        elif col in ['Open', 'High', 'Low', 'Close']:
            df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else '')
        elif col in ['change', 'pct_change']:
            df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else '')

    print(tabulate(df_display,
                   headers='keys',
                   tablefmt='grid',
                   stralign='right',
                   showindex=False))

def display_quality_checks(conn, table_name, available_cols):
    """显示数据质量检查结果"""
    print("\n" + "-" * 80)
    print(" 🔍 数据质量检查")
    print("-" * 80)

    total_records = get_table_count(conn, table_name)

    # 1. 空值检查
    null_counts = check_null_values(conn, table_name)
    if null_counts:
        total_nulls = sum(null_counts.values())
        print(f"\n  1. 空值检查:")
        print(f"     总空值数: {total_nulls:,}")

        if total_nulls > 0:
            # 显示有空值的字段
            null_fields = {k: v for k, v in null_counts.items() if v > 0}
            if null_fields:
                null_data = []
                for col, count in sorted(null_fields.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_records * 100) if total_records > 0 else 0
                    null_data.append([col, f"{count:,}", f"{percentage:.1f}%"])
                print("     空值字段:")
                print(tabulate(null_data,
                               headers=['字段名', '空值数', '空值率'],
                               tablefmt='simple',
                               stralign='left'))
        else:
            print("     ✅ 无空值")

    # 2. 重复检查
    duplicates = check_duplicates(conn, table_name)
    print(f"\n  2. 重复记录检查:")
    if duplicates.empty:
        print("     ✅ 无重复记录")
    else:
        print(f"     ⚠️ 发现 {len(duplicates)} 组重复记录")
        dup_data = []
        for _, row in duplicates.head(5).iterrows():
            dup_data.append([row['stock_code'], row['date'], row['count']])
        if dup_data:
            print("     重复记录示例 (前5组):")
            print(tabulate(dup_data,
                           headers=['股票代码', '日期', '重复次数'],
                           tablefmt='simple',
                           stralign='left'))

    # 3. 资金流合理性检查
    cash_flow_errors = check_cash_flow_reasonability(conn, table_name, available_cols)
    print(f"\n  3. 资金流合理性检查:")
    if cash_flow_errors.empty:
        print("     ✅ 所有资金流数据合理")
    else:
        print(f"     ⚠️ 发现 {len(cash_flow_errors)} 条资金流逻辑错误")
        error_data = []
        for _, row in cash_flow_errors.head(5).iterrows():
            # 安全地获取列值
            stock_code = row.get('stock_code', 'N/A')
            date_val = row.get('date', 'N/A')
            error_type = row.get('error_type', 'Unknown')
            
            # 构建显示数据
            error_row = [stock_code, date_val]
            
            # 添加数值列
            for col in ['close', 'close_price', 'amount', 'main_net_inflow', 
                       'retail_net_inflow', 'net_inflow']:
                if col in row.index:
                    val = row.get(col, 0)
                    if pd.notna(val):
                        error_row.append(f"{val:,.2f}" if val != 0 else "0.00")
                    else:
                        error_row.append("N/A")
            
            error_row.append(error_type)
            error_data.append(error_row)
        
        if error_data:
            # 构建表头
            headers = ['股票代码', '日期']
            for col in ['close', 'close_price', 'amount', 'main_net_inflow', 
                       'retail_net_inflow', 'net_inflow']:
                if col in cash_flow_errors.columns:
                    headers.append(col)
            headers.append('错误类型')
            
            print("     错误记录示例 (前5条):")
            print(tabulate(error_data,
                           headers=headers,
                           tablefmt='simple',
                           stralign='left'))

    # 4. 缺失股票检查
    missing_stocks, extra_stocks = check_missing_stocks(conn, table_name)
    print(f"\n  4. 缺失股票检查:")
    if missing_stocks:
        print(f"     ⚠️ 缺失 {len(missing_stocks)} 只股票（在配置文件中但不在数据库中）:")
        for code in sorted(missing_stocks):
            stock_info = STOCK_MAP.get(code, {})
            name = stock_info.get('name', '未知')
            sector = stock_info.get('sector', 'N/A')
            print(f"       - {code} {name} ({sector})")
    else:
        print("     ✅ 所有配置的股票都有数据")
    
    # 5. 额外股票检查（数据库中有的但配置文件中没有）
    if extra_stocks:
        print(f"\n  5. 额外股票检查:")
        print(f"     ⚠️ 发现 {len(extra_stocks)} 只额外股票（在数据库中但不在配置文件中）:")
        for code in sorted(extra_stocks):
            # 从数据库获取名称
            query = f"SELECT stock_name FROM {table_name} WHERE stock_code='{code}' LIMIT 1"
            df = pd.read_sql_query(query, conn)
            name = df['stock_name'].iloc[0] if not df.empty else '未知'
            print(f"       - {code} {name}")
    else:
        print("\n  5. 额外股票检查: ✅ 无额外股票")

def display_data_dictionary_comparison(comparison_result):
    """显示数据字典对比结果"""
    if comparison_result is None:
        return
    
    print("\n" + "-" * 80)
    print(" 📋 数据字典与数据库表结构对比")
    print("-" * 80)
    
    if comparison_result['is_consistent']:
        print("  ✅ 数据库表结构与数据字典完全一致")
        print(f"     共 {len(comparison_result['db_columns'])} 个字段")
    else:
        print("  ⚠️ 数据库表结构与数据字典存在差异:")
        
        if comparison_result['missing_in_db']:
            print(f"\n     缺失字段 (在数据字典中但数据库中不存在):")
            for field in comparison_result['missing_in_db']:
                print(f"       - {field}")
        
        if comparison_result['extra_in_db']:
            print(f"\n     额外字段 (在数据库中但数据字典中不存在):")
            for field in comparison_result['extra_in_db']:
                print(f"       - {field}")
        
        if comparison_result['missing_in_dict']:
            print(f"\n     数据库字段但数据字典无定义:")
            for field in comparison_result['missing_in_dict']:
                print(f"       - {field}")

# =====================================================
# 7. 生成验证报告
# =====================================================

def generate_report(conn, table_name, data_dict=None, available_cols=None):
    """生成验证报告"""
    REPORT_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"Verify_Daily_Kline_analysis_{timestamp}.txt"
    report_path = REPORT_DIR / report_filename
    json_report_path = REPORT_DIR / f"Verify_Daily_Kline_analysis_{timestamp}.json"

    # 收集验证数据
    validation_data = {
        'metadata': {
            'table_name': table_name,
            'generated_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'database_path': str(DB_PATH),
            'project_dir': str(project_dir),
            'data_dictionary_loaded': data_dict is not None
        },
        'basic_info': {},
        'stock_statistics': [],
        'sample_data': [],
        'cash_flow_summary': {},
        'quality_checks': {
            'null_values': {},
            'duplicates': [],
            'cash_flow_errors': [],
            'missing_stocks': [],
            'extra_stocks': []
        }
    }

    # 基本信息
    total_records = get_table_count(conn, table_name)
    validation_data['basic_info']['total_records'] = total_records
    validation_data['basic_info']['columns'] = get_table_info(conn, table_name).to_dict('records')

    # 股票统计
    stock_stats = get_stock_statistics(conn, table_name, available_cols)
    validation_data['stock_statistics'] = stock_stats.to_dict('records')

    # 样本数据 - 获取10条
    sample_df = get_table_sample(conn, table_name, limit=10)
    validation_data['sample_data'] = sample_df.to_dict('records')

    # 资金流汇总
    cash_flow_summary = get_cash_flow_summary(conn, table_name, available_cols)
    validation_data['cash_flow_summary'] = cash_flow_summary.to_dict('records')[0] if not cash_flow_summary.empty else {}

    # 质量检查
    null_counts = check_null_values(conn, table_name)
    validation_data['quality_checks']['null_values'] = null_counts

    duplicates = check_duplicates(conn, table_name)
    validation_data['quality_checks']['duplicates'] = duplicates.to_dict('records')

    cash_flow_errors = check_cash_flow_reasonability(conn, table_name, available_cols)
    validation_data['quality_checks']['cash_flow_errors'] = cash_flow_errors.to_dict('records')

    missing_stocks, extra_stocks = check_missing_stocks(conn, table_name)
    validation_data['quality_checks']['missing_stocks'] = list(missing_stocks)
    validation_data['quality_checks']['extra_stocks'] = list(extra_stocks)

    # 数据字典对比
    if data_dict:
        comparison = compare_with_data_dictionary(conn, table_name, data_dict)
        validation_data['data_dictionary_comparison'] = comparison

    # 保存JSON报告
    with open(json_report_path, 'w', encoding='utf-8') as f:
        json.dump(validation_data, f, ensure_ascii=False, indent=2, default=str)

    # 生成文本报告
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("日资金流数据验证报告\n")
        f.write("=" * 80 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"数据库路径: {DB_PATH}\n")
        f.write(f"项目目录: {project_dir}\n")
        f.write("=" * 80 + "\n\n")

        # 基本信息
        f.write("-" * 80 + "\n")
        f.write("基本信息\n")
        f.write("-" * 80 + "\n")
        f.write(f"表名: {table_name}\n")
        f.write(f"总记录数: {total_records:,}\n")
        f.write(f"股票数量: {len(stock_stats)}\n")
        
        # 资金流汇总
        if not cash_flow_summary.empty:
            f.write("\n资金流汇总:\n")
            if 'total_amount' in cash_flow_summary.columns:
                f.write(f"  总成交额: {cash_flow_summary['total_amount'].iloc[0]:,.0f}\n")
            if 'total_main_net_inflow' in cash_flow_summary.columns:
                f.write(f"  总主力净流入: {cash_flow_summary['total_main_net_inflow'].iloc[0]:,.0f}\n")
            if 'total_retail_net_inflow' in cash_flow_summary.columns:
                f.write(f"  总散户净流入: {cash_flow_summary['total_retail_net_inflow'].iloc[0]:,.0f}\n")
            if 'total_net_inflow' in cash_flow_summary.columns:
                f.write(f"  总净流入: {cash_flow_summary['total_net_inflow'].iloc[0]:,.0f}\n")
        f.write("\n")

        # 股票统计
        f.write("-" * 80 + "\n")
        f.write("每只股票资金流统计\n")
        f.write("-" * 80 + "\n")
        for _, row in stock_stats.iterrows():
            in_config = "✓" if row['stock_code'] in STOCK_MAP else "⚠️"
            f.write(f"  {in_config} {row['stock_code']} {row['stock_name']}: ")
            f.write(f"{row['record_count']:,} 条记录, ")
            f.write(f"{row['first_date']} ~ {row['last_date']}, ")
            if 'avg_close' in row:
                f.write(f"均价: {row['avg_close']:.2f}, ")
            if 'avg_main_net_inflow' in row:
                f.write(f"平均主力净流入: {row['avg_main_net_inflow']:,.0f}")
            f.write("\n")
        f.write("\n")

        # 质量检查
        f.write("-" * 80 + "\n")
        f.write("数据质量检查\n")
        f.write("-" * 80 + "\n")

        # 空值
        total_nulls = sum(null_counts.values())
        f.write(f"1. 空值检查: 总空值数 {total_nulls:,}\n")
        if total_nulls > 0:
            for col, count in sorted(null_counts.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    percentage = (count / total_records * 100) if total_records > 0 else 0
                    f.write(f"     {col}: {count:,} ({percentage:.1f}%)\n")
        f.write("\n")

        # 重复
        f.write(f"2. 重复记录检查: {len(duplicates)} 组重复\n")
        if not duplicates.empty:
            for _, row in duplicates.head(10).iterrows():
                f.write(f"     {row['stock_code']} {row['date']}: {row['count']} 次\n")
        f.write("\n")

        # 资金流错误
        f.write(f"3. 资金流合理性检查: {len(cash_flow_errors)} 条错误\n")
        if not cash_flow_errors.empty:
            for _, row in cash_flow_errors.head(10).iterrows():
                stock_code = row.get('stock_code', 'N/A')
                date_val = row.get('date', 'N/A')
                error_type = row.get('error_type', 'Unknown')
                f.write(f"     {stock_code} {date_val}: {error_type}\n")
        f.write("\n")

        # 缺失股票
        f.write(f"4. 缺失股票检查: {len(missing_stocks)} 只缺失\n")
        for code in sorted(missing_stocks):
            stock_info = STOCK_MAP.get(code, {})
            name = stock_info.get('name', '未知')
            sector = stock_info.get('sector', 'N/A')
            f.write(f"     {code} {name} ({sector})\n")
        f.write("\n")

        # 额外股票
        f.write(f"5. 额外股票检查: {len(extra_stocks)} 只额外\n")
        for code in sorted(extra_stocks):
            query = f"SELECT stock_name FROM {table_name} WHERE stock_code='{code}' LIMIT 1"
            df = pd.read_sql_query(query, conn)
            name = df['stock_name'].iloc[0] if not df.empty else '未知'
            f.write(f"     {code} {name}\n")
        f.write("\n")

        # 数据字典对比
        if data_dict:
            comparison = compare_with_data_dictionary(conn, table_name, data_dict)
            f.write("-" * 80 + "\n")
            f.write("数据字典与数据库表结构对比\n")
            f.write("-" * 80 + "\n")
            if comparison['is_consistent']:
                f.write("  ✅ 完全一致\n")
            else:
                f.write("  ⚠️ 存在差异:\n")
                if comparison['missing_in_db']:
                    f.write("    缺失字段 (数据字典中有但数据库中没有):\n")
                    for field in comparison['missing_in_db']:
                        f.write(f"      - {field}\n")
                if comparison['extra_in_db']:
                    f.write("    额外字段 (数据库中有但数据字典中没有):\n")
                    for field in comparison['extra_in_db']:
                        f.write(f"      - {field}\n")
            f.write("\n")

        # 样本数据 - 显示最新10条，前15列
        f.write("-" * 80 + "\n")
        f.write("样本数据 (最新10条，前15列)\n")
        f.write("-" * 80 + "\n")
        if not sample_df.empty:
            # 选择前15列
            display_cols = sample_df.columns[:15].tolist()
            # 格式化数值
            df_display = sample_df[display_cols].copy()
            for col in df_display.columns:
                if col in ['close', 'close_price', 'amount', 'main_net_inflow', 
                          'retail_net_inflow', 'net_inflow', 'volume', 'turnover']:
                    df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else '')
                elif col == 'turnover_rate':
                    df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else '')
                elif col in ['Open', 'High', 'Low', 'Close']:
                    df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else '')
            f.write(df_display.to_string(index=False))
        else:
            f.write("  无样本数据\n")
        f.write("\n\n")

        f.write("=" * 80 + "\n")
        f.write("报告结束\n")
        f.write("=" * 80 + "\n")

    return report_path, json_report_path

# =====================================================
# 8. 主函数
# =====================================================

def main():
    print("\n" + "=" * 80)
    print("日资金流数据验证工具")
    print("=" * 80)
    print(f"项目目录: {project_dir}")
    print(f"数据库路径: {DB_PATH}")
    print(f"配置文件股票数: {len(STOCK_LIST)}")
    print("=" * 80)

    # 检查数据库是否存在
    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("请先运行导入程序导入数据")
        sys.exit(1)

    TABLE_NAME = 'hk_daily_kline_analysis'
    
    # 加载数据字典
    print("\n加载数据字典...")
    data_dict = load_data_dictionary()

    # 获取数据库连接
    conn = get_db_connection()

    try:
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}'")
        if not cursor.fetchone():
            print(f"❌ 表 {TABLE_NAME} 不存在")
            print("请先运行导入程序导入数据")
            return

        # 检测可用列
        print("\n检测表结构...")
        all_columns = get_table_columns(conn, TABLE_NAME)
        print(f"  表中包含的列: {', '.join(all_columns)}")
        
        # 定义需要检测的列
        required_cols = [
            'close', 'close_price', 'amount', 'main_net_inflow',
            'retail_net_inflow', 'net_inflow', 'turnover_rate'
        ]
        available_cols = {col: col in all_columns for col in required_cols}
        
        print("\n  可用列状态:")
        for col, available in available_cols.items():
            status = "✅" if available else "❌"
            print(f"    {status} {col}")

        # 显示表摘要
        display_table_summary(conn, TABLE_NAME, available_cols)

        # 显示股票统计
        display_stock_statistics(conn, TABLE_NAME, available_cols)

        # 显示样本数据 - 显示10条，前15列
        display_sample_data(conn, TABLE_NAME, limit=10)

        # 显示数据质量检查
        display_quality_checks(conn, TABLE_NAME, available_cols)

        # 显示数据字典对比
        if data_dict:
            comparison = compare_with_data_dictionary(conn, TABLE_NAME, data_dict)
            display_data_dictionary_comparison(comparison)

        # 生成报告
        print("\n" + "-" * 80)
        print("生成验证报告...")
        print("-" * 80)

        txt_report, json_report = generate_report(conn, TABLE_NAME, data_dict, available_cols)
        print(f"✅ 文本报告已生成: {txt_report}")
        print(f"✅ JSON报告已生成: {json_report}")

        # 汇总统计
        print("\n" + "=" * 80)
        print("验证完成!")
        print("=" * 80)

    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    main()