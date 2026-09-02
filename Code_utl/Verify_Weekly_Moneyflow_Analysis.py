#!/usr/bin/env python
# coding: utf-8

"""
Verify_Weekly_Moneyflow_Analysis.py
数据验证程序 - 验证 hk_weekly_moneyflow_analysis 表的周资金流数据
功能:
  1. 显示表的基本信息（字段、记录数、日期范围等）
  2. 显示每只股票的数据统计
  3. 显示最新的5条记录（按日期升序）
  4. 检查数据完整性（空值、重复值等）
  5. 检查资金流数据的合理性
  6. 检查数据字典的一致性
  7. 生成验证报告
  8. 保存验证结果到JSON文件
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

        # 向上两级到达项目根目录
        project_dir = script_path.parent.parent

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
# 导入股票列表加载工具
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
# 3. 数据字典加载和检查
# =====================================================

def load_data_dictionary():
    """加载数据字典"""
    dict_path = project_dir / 'Config' / 'hk_weekly_moneyflow_analysis_dictionary.json'
    
    if not dict_path.exists():
        print(f"[WARN] 数据字典文件不存在: {dict_path}")
        return None
    
    try:
        with open(dict_path, 'r', encoding='utf-8') as f:
            data_dict = json.load(f)
        print(f"[INFO] 成功加载数据字典: {dict_path}")
        return data_dict
    except Exception as e:
        print(f"[ERROR] 加载数据字典失败: {e}")
        return None

def check_data_dictionary_consistency(conn, table_name, data_dict):
    """检查数据字典与数据库表的一致性"""
    if not data_dict:
        return False
    
    issues = []
    
    # 1. 检查表名是否一致
    dict_table_name = data_dict.get('metadata', {}).get('table_name')
    if dict_table_name != table_name:
        issues.append(f"表名不一致: 数据字典 '{dict_table_name}' vs 数据库 '{table_name}'")
    
    # 2. 检查字段是否一致
    # 获取数据库表结构
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    db_columns = {row[1]: {'type': row[2], 'notnull': row[3]} for row in cursor.fetchall()}
    
    # 获取数据字典中的字段
    dict_columns = {}
    for col_def in data_dict.get('data_dictionary', {}).get('column_definitions', []):
        dict_columns[col_def['name']] = {
            'type': col_def['type'],
            'description': col_def.get('description', '')
        }
    
    # 检查缺失字段
    missing_in_db = set(dict_columns.keys()) - set(db_columns.keys())
    if missing_in_db:
        issues.append(f"数据字典中有但数据库中缺失的字段: {', '.join(missing_in_db)}")
    
    # 检查额外字段
    extra_in_db = set(db_columns.keys()) - set(dict_columns.keys())
    if extra_in_db:
        issues.append(f"数据库中有但数据字典中缺失的字段: {', '.join(extra_in_db)}")
    
    # 检查字段类型
    for col_name in set(dict_columns.keys()) & set(db_columns.keys()):
        dict_type = dict_columns[col_name]['type']
        db_type = db_columns[col_name]['type']
        # SQLite类型映射（简化版）
        if dict_type.upper() not in db_type.upper():
            issues.append(f"字段 '{col_name}' 类型不一致: 数据字典 '{dict_type}' vs 数据库 '{db_type}'")
    
    # 3. 检查索引
    dict_indexes = data_dict.get('table_schema', {}).get('indexes', [])
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?", (table_name,))
    db_indexes = [row[0] for row in cursor.fetchall()]
    
    for idx in dict_indexes:
        idx_name = idx.get('name')
        if idx_name and idx_name not in db_indexes:
            issues.append(f"索引 '{idx_name}' 在数据字典中但不在数据库中")
    
    if issues:
        print("\n⚠️ 发现数据字典一致性问题:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("\n✅ 数据字典与数据库表一致")
        return True

# =====================================================
# 4. 数据库操作函数
# =====================================================

def get_db_connection():
    """获取数据库连接"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.text_factory = str
    return conn

# =====================================================
# 5. 数据验证函数（修正版 - 动态适应表结构）
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

def get_numeric_columns(conn, table_name):
    """获取表中的数值列（不包括 id, stock_code, stock_name, date）"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    numeric_cols = []
    for col in columns:
        col_name = col[1]
        col_type = col[2].upper()
        # 排除非数值列
        if col_name in ['id', 'stock_code', 'stock_name', 'date']:
            continue
        # 检查是否为数值类型
        if any(t in col_type for t in ['REAL', 'FLOAT', 'DOUBLE', 'INT', 'NUMERIC', 'DECIMAL']):
            numeric_cols.append(col_name)
    
    return numeric_cols

def get_stock_statistics(conn, table_name):
    """获取每只股票的统计数据（动态适应表结构）"""
    # 获取表中的所有列
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    
    # 检查是否有 close 或 price 相关的列
    price_cols = [col for col in columns if col.lower() in ['close', 'price', 'price_chgpct']]
    
    # 构建查询
    select_parts = [
        'stock_code',
        'stock_name',
        'COUNT(*) as record_count',
        'MIN(date) as first_date',
        'MAX(date) as last_date',
        'COUNT(DISTINCT date) as trading_weeks'
    ]
    
    # 如果有价格列，添加价格统计
    if price_cols:
        price_col = price_cols[0]  # 使用第一个找到的价格列
        select_parts.extend([
            f'MIN({price_col}) as min_value',
            f'MAX({price_col}) as max_value',
            f'AVG({price_col}) as avg_value'
        ])
    
    # 如果有资金流列，添加资金流统计
    flow_cols = [col for col in columns if any(kw in col.lower() for kw in ['inflow', 'outflow', 'flow', 'trend'])]
    for col in flow_cols[:3]:  # 只取前3个资金流列
        select_parts.append(f'AVG({col}) as avg_{col}')
    
    query = f"""
        SELECT {', '.join(select_parts)}
        FROM {table_name}
        GROUP BY stock_code, stock_name
        ORDER BY stock_code
    """
    
    try:
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"  ⚠️ 获取股票统计失败: {e}")
        return pd.DataFrame()

def get_table_sample(conn, table_name, limit=10):
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

def check_moneyflow_logic(conn, table_name):
    """检查资金流数据的合理性"""
    try:
        # 获取所有数值字段
        numeric_cols = get_numeric_columns(conn, table_name)
        
        # 筛选资金流相关字段
        moneyflow_fields = []
        for col in numeric_cols:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['inflow', 'outflow', 'money', 'flow', 'trend']):
                moneyflow_fields.append(col)
        
        if not moneyflow_fields:
            return pd.DataFrame()
        
        # 检查负值
        conditions = []
        for field in moneyflow_fields:
            conditions.append(f"CAST({field} AS REAL) < 0")
        
        if conditions:
            where_clause = " OR ".join(conditions)
            query = f"""
                SELECT 
                    stock_code,
                    date,
                    {', '.join(moneyflow_fields)}
                FROM {table_name}
                WHERE {where_clause}
                LIMIT 100
            """
            df = pd.read_sql_query(query, conn)
            return df
        
        return pd.DataFrame()
        
    except Exception as e:
        print(f"  ⚠️ 资金流逻辑检查失败: {e}")
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

def get_date_range_per_stock(conn, table_name):
    """获取每只股票的日期范围"""
    query = f"""
        SELECT 
            stock_code,
            stock_name,
            MIN(date) as first_date,
            MAX(date) as last_date,
            COUNT(*) as record_count
        FROM {table_name}
        GROUP BY stock_code, stock_name
        ORDER BY stock_code
    """
    df = pd.read_sql_query(query, conn)
    return df

def get_moneyflow_summary(conn, table_name):
    """获取资金流汇总统计"""
    try:
        # 获取所有数值字段
        numeric_cols = get_numeric_columns(conn, table_name)
        
        # 筛选资金流相关字段
        flow_cols = [col for col in numeric_cols if any(kw in col.lower() for kw in ['inflow', 'outflow', 'flow', 'trend'])]
        
        if not flow_cols:
            return pd.DataFrame()
        
        # 构建汇总查询
        sum_fields = [f"SUM({col}) as sum_{col}" for col in flow_cols]
        avg_fields = [f"AVG({col}) as avg_{col}" for col in flow_cols]
        
        query = f"""
            SELECT 
                stock_code,
                stock_name,
                COUNT(*) as record_count,
                {', '.join(sum_fields)},
                {', '.join(avg_fields)}
            FROM {table_name}
            GROUP BY stock_code, stock_name
            ORDER BY stock_code
        """
        
        df = pd.read_sql_query(query, conn)
        return df
        
    except Exception as e:
        print(f"  ⚠️ 获取资金流汇总失败: {e}")
        return pd.DataFrame()

# =====================================================
# 6. 显示函数（修正版）
# =====================================================

def display_header(text, char='='):
    """显示标题"""
    print()
    print(char * 80)
    print(f" {text}")
    print(char * 80)

def display_table_summary(conn, table_name):
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

    # 股票统计（动态适应表结构）
    stock_stats = get_stock_statistics(conn, table_name)
    if not stock_stats.empty:
        print(f"\n  📈 股票统计:")
        print(f"    股票数量: {len(stock_stats)} 只")
        if 'trading_weeks' in stock_stats.columns:
            print(f"    总交易周数: {stock_stats['trading_weeks'].sum():,}")
        print(f"    平均每只股票记录数: {stock_stats['record_count'].mean():.1f}")

    # 日期范围
    date_range = get_date_range_per_stock(conn, table_name)
    if not date_range.empty:
        min_date = date_range['first_date'].min()
        max_date = date_range['last_date'].max()
        print(f"\n  📅 全局日期范围:")
        print(f"    最早日期: {min_date}")
        print(f"    最晚日期: {max_date}")

def display_stock_statistics(conn, table_name):
    """显示每只股票的统计信息（动态适应表结构）"""
    print("\n" + "-" * 80)
    print(" 📈 每只股票统计")
    print("-" * 80)

    stock_stats = get_stock_statistics(conn, table_name)

    if stock_stats.empty:
        print("  ⚠️ 无数据")
        return

    # 格式化显示
    display_data = []
    for _, row in stock_stats.iterrows():
        # 检查是否在配置文件中
        in_config = "✓" if row['stock_code'] in STOCK_MAP else "⚠️"
        
        row_data = [in_config, row['stock_code'], row['stock_name'], f"{row['record_count']:,}", row['first_date'], row['last_date']]
        
        # 添加数值统计
        if 'min_value' in row and 'max_value' in row:
            row_data.extend([
                f"{row['min_value']:.2f}" if pd.notna(row['min_value']) else 'N/A',
                f"{row['max_value']:.2f}" if pd.notna(row['max_value']) else 'N/A',
                f"{row['avg_value']:.2f}" if pd.notna(row['avg_value']) else 'N/A'
            ])
        
        display_data.append(row_data)

    # 构建表头
    headers = ['状态', '代码', '名称', '记录数', '开始日期', '结束日期']
    # 检查是否有数值统计列
    if 'min_value' in stock_stats.columns:
        headers.extend(['最小值', '最大值', '平均值'])

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

    # 选择要显示的列
    display_cols = ['stock_code', 'stock_name', 'date']
    # 添加常见的资金流字段
    for col in df.columns:
        if any(keyword in col.lower() for keyword in ['inflow', 'outflow', 'flow', 'trend', 'price']):
            if col not in display_cols:
                display_cols.append(col)
    
    available_cols = [col for col in display_cols if col in df.columns]
    
    if not available_cols:
        available_cols = df.columns.tolist()

    df_display = df[available_cols].copy()

    # 格式化数值
    numeric_cols = get_numeric_columns(conn, table_name)
    for col in df_display.columns:
        if col in numeric_cols:
            try:
                df_display[col] = df_display[col].apply(lambda x: f"{x:.4f}" if pd.notna(x) and isinstance(x, (int, float)) else '')
            except:
                pass

    print(tabulate(df_display,
                   headers='keys',
                   tablefmt='grid',
                   stralign='right',
                   showindex=False))

def display_quality_checks(conn, table_name):
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

    # 3. 资金流逻辑检查
    moneyflow_errors = check_moneyflow_logic(conn, table_name)
    print(f"\n  3. 资金流逻辑检查:")
    if moneyflow_errors.empty:
        print("     ✅ 资金流数据逻辑正常")
    else:
        print(f"     ⚠️ 发现 {len(moneyflow_errors)} 条资金流异常记录（负值）")
        if not moneyflow_errors.empty:
            # 获取所有列名
            cols = list(moneyflow_errors.columns)
            error_data = []
            for _, row in moneyflow_errors.head(5).iterrows():
                row_data = []
                for col in cols:
                    if col in ['stock_code', 'date']:
                        row_data.append(str(row[col]))
                    elif pd.notna(row[col]) and isinstance(row[col], (int, float)):
                        if row[col] < 0:
                            row_data.append(f"{row[col]:.4f}*")
                        else:
                            row_data.append(f"{row[col]:.4f}")
                    else:
                        row_data.append(str(row[col]))
                error_data.append(row_data)
            
            if error_data:
                print("     异常记录示例 (前5条, *表示负值):")
                print(tabulate(error_data,
                               headers=cols,
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
    
    # 5. 额外股票检查
    if extra_stocks:
        print(f"\n  5. 额外股票检查:")
        print(f"     ⚠️ 发现 {len(extra_stocks)} 只额外股票（在数据库中但不在配置文件中）:")
        for code in sorted(extra_stocks):
            query = f"SELECT stock_name FROM {table_name} WHERE stock_code='{code}' LIMIT 1"
            df = pd.read_sql_query(query, conn)
            name = df['stock_name'].iloc[0] if not df.empty else '未知'
            print(f"       - {code} {name}")
    else:
        print("\n  5. 额外股票检查: ✅ 无额外股票")

def display_moneyflow_summary(conn, table_name):
    """显示资金流汇总统计"""
    print("\n" + "-" * 80)
    print(" 💰 资金流汇总统计（前10只股票）")
    print("-" * 80)

    df = get_moneyflow_summary(conn, table_name)
    
    if df.empty:
        print("  ⚠️ 无资金流数据")
        return
    
    # 选择要显示的列
    display_cols = ['stock_code', 'stock_name', 'record_count']
    
    # 添加资金流相关的汇总列
    for col in df.columns:
        if col.startswith('sum_') or col.startswith('avg_'):
            display_cols.append(col)
    
    available_cols = [col for col in display_cols if col in df.columns]
    
    if len(available_cols) <= 3:
        print("  ⚠️ 未找到资金流字段")
        return
    
    df_display = df[available_cols].head(10).copy()
    
    # 格式化数值
    for col in df_display.columns:
        if col not in ['stock_code', 'stock_name']:
            try:
                df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else '')
            except:
                pass
    
    print(tabulate(df_display,
                   headers='keys',
                   tablefmt='grid',
                   stralign='right',
                   showindex=False))

# =====================================================
# 7. 生成验证报告（修正版）
# =====================================================

def generate_report(conn, table_name, data_dict):
    """生成验证报告"""
    REPORT_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"Stock_Weekly_Moneyflow_Verify_{timestamp}.txt"
    report_path = REPORT_DIR / report_filename
    json_report_path = REPORT_DIR / f"Stock_Weekly_Moneyflow_Verify_{timestamp}.json"

    # 收集验证数据
    validation_data = {
        'metadata': {
            'table_name': table_name,
            'generated_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'database_path': str(DB_PATH),
            'project_dir': str(project_dir)
        },
        'basic_info': {},
        'stock_statistics': [],
        'sample_data': [],
        'quality_checks': {
            'null_values': {},
            'duplicates': [],
            'moneyflow_errors': [],
            'missing_stocks': [],
            'extra_stocks': []
        },
        'data_dictionary_check': {}
    }

    # 基本信息
    total_records = get_table_count(conn, table_name)
    validation_data['basic_info']['total_records'] = total_records
    validation_data['basic_info']['columns'] = get_table_info(conn, table_name).to_dict('records')

    # 股票统计
    stock_stats = get_stock_statistics(conn, table_name)
    validation_data['stock_statistics'] = stock_stats.to_dict('records')

    # 样本数据
    sample_df = get_table_sample(conn, table_name, limit=10)
    validation_data['sample_data'] = sample_df.to_dict('records')

    # 质量检查
    null_counts = check_null_values(conn, table_name)
    validation_data['quality_checks']['null_values'] = null_counts

    duplicates = check_duplicates(conn, table_name)
    validation_data['quality_checks']['duplicates'] = duplicates.to_dict('records')

    moneyflow_errors = check_moneyflow_logic(conn, table_name)
    validation_data['quality_checks']['moneyflow_errors'] = moneyflow_errors.to_dict('records')

    missing_stocks, extra_stocks = check_missing_stocks(conn, table_name)
    validation_data['quality_checks']['missing_stocks'] = list(missing_stocks)
    validation_data['quality_checks']['extra_stocks'] = list(extra_stocks)

    # 数据字典检查
    if data_dict:
        validation_data['data_dictionary_check']['exists'] = True
        validation_data['data_dictionary_check']['version'] = data_dict.get('metadata', {}).get('version')
        validation_data['data_dictionary_check']['created_date'] = data_dict.get('metadata', {}).get('created_date')
    else:
        validation_data['data_dictionary_check']['exists'] = False

    # 保存JSON报告
    with open(json_report_path, 'w', encoding='utf-8') as f:
        json.dump(validation_data, f, ensure_ascii=False, indent=2, default=str)

    # 生成文本报告
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("周资金流数据验证报告\n")
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
        f.write(f"股票数量: {len(stock_stats)}\n\n")

        # 股票统计
        f.write("-" * 80 + "\n")
        f.write("每只股票统计\n")
        f.write("-" * 80 + "\n")
        for _, row in stock_stats.iterrows():
            in_config = "✓" if row['stock_code'] in STOCK_MAP else "⚠️"
            f.write(f"  {in_config} {row['stock_code']} {row['stock_name']}: ")
            f.write(f"{row['record_count']:,} 条记录, ")
            f.write(f"{row['first_date']} ~ {row['last_date']}")
            if 'min_value' in row:
                f.write(f", 值范围: {row['min_value']:.2f} ~ {row['max_value']:.2f}")
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
        f.write(f"3. 资金流逻辑检查: {len(moneyflow_errors)} 条异常\n")
        if not moneyflow_errors.empty:
            for _, row in moneyflow_errors.head(10).iterrows():
                f.write(f"     {row['stock_code']} {row['date']}: 存在负值\n")
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

        # 数据字典检查
        f.write("-" * 80 + "\n")
        f.write("数据字典检查\n")
        f.write("-" * 80 + "\n")
        if data_dict:
            f.write(f"✅ 数据字典存在\n")
            f.write(f"   版本: {data_dict.get('metadata', {}).get('version', 'N/A')}\n")
            f.write(f"   创建时间: {data_dict.get('metadata', {}).get('created_date', 'N/A')}\n")
            f.write(f"   字段数: {len(data_dict.get('data_dictionary', {}).get('column_definitions', []))}\n")
        else:
            f.write("❌ 数据字典不存在\n")
        f.write("\n")

        # 样本数据
        f.write("-" * 80 + "\n")
        f.write("样本数据 (最新10条)\n")
        f.write("-" * 80 + "\n")
        if not sample_df.empty:
            f.write(sample_df.to_string(index=False))
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
    print("周资金流数据验证工具")
    print("=" * 80)
    print(f"项目目录: {project_dir}")
    print(f"数据库路径: {DB_PATH}")
    print(f"配置文件股票数: {len(STOCK_LIST)}")
    print("=" * 80)

    # 检查数据库是否存在
    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("请先运行 Import_Weekly_Moneyflow_Analysis.py 导入数据")
        sys.exit(1)

    TABLE_NAME = 'hk_weekly_moneyflow_analysis'

    # 获取数据库连接
    conn = get_db_connection()

    try:
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}'")
        if not cursor.fetchone():
            print(f"❌ 表 {TABLE_NAME} 不存在")
            print("请先运行 Import_Weekly_Moneyflow_Analysis.py 导入数据")
            return

        # 加载数据字典
        data_dict = load_data_dictionary()
        
        # 检查数据字典一致性
        if data_dict:
            check_data_dictionary_consistency(conn, TABLE_NAME, data_dict)

        # 显示表摘要
        display_table_summary(conn, TABLE_NAME)

        # 显示股票统计
        display_stock_statistics(conn, TABLE_NAME)

        # 显示资金流汇总
        display_moneyflow_summary(conn, TABLE_NAME)

        # 显示样本数据
        display_sample_data(conn, TABLE_NAME, limit=10)

        # 显示数据质量检查
        display_quality_checks(conn, TABLE_NAME)

        # 生成报告
        print("\n" + "-" * 80)
        print("生成验证报告...")
        print("-" * 80)

        txt_report, json_report = generate_report(conn, TABLE_NAME, data_dict)
        print(f"✅ 文本报告已生成: {txt_report}")
        print(f"✅ JSON报告已生成: {json_report}")

        # 汇总统计
        print("\n" + "=" * 80)
        print("验证完成!")
        print("=" * 80)
        
        # 显示验证摘要
        total_records = get_table_count(conn, TABLE_NAME)
        print(f"📊 总记录数: {total_records:,}")
        
        stock_stats = get_stock_statistics(conn, TABLE_NAME)
        print(f"📈 股票数量: {len(stock_stats)}")
        
        if data_dict:
            print(f"📋 数据字典: 已加载")
        else:
            print(f"⚠️ 数据字典: 未找到")
        
        # 检查质量
        null_counts = check_null_values(conn, TABLE_NAME)
        total_nulls = sum(null_counts.values())
        if total_nulls == 0:
            print(f"✅ 空值检查: 通过")
        else:
            print(f"⚠️ 空值检查: 发现 {total_nulls:,} 个空值")
        
        duplicates = check_duplicates(conn, TABLE_NAME)
        if duplicates.empty:
            print(f"✅ 重复检查: 通过")
        else:
            print(f"⚠️ 重复检查: 发现 {len(duplicates)} 组重复")

    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    main()
    