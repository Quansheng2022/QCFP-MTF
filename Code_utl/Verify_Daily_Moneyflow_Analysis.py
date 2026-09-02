#!/usr/bin/env python
# coding: utf-8

"""
Verify_Daily_Moneyflow_Analysis.py
数据验证程序 - 验证 hk_daily_moneyflow_analysis 表的日资金流数据

功能:
  1. 显示表的基本信息（字段、记录数、日期范围等）
  2. 显示每只股票的数据统计
  3. 显示最新的5条记录（按日期升序）
  4. 检查数据完整性（空值、重复值等）
  5. 检查资金流数据的合理性
  6. 生成验证报告
  7. 保存验证结果到JSON文件
  8. 检查数据字典文件
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
# 3. 数据字典检查
# =====================================================

def check_data_dictionary():
    """检查数据字典文件"""
    print("\n" + "-" * 80)
    print(" 📋 数据字典检查")
    print("-" * 80)
    
    dict_path = project_dir / 'Config' / 'hk_stock_daily_moneyflow_dictionary.json'
    
    if not dict_path.exists():
        print(f"  ⚠️ 数据字典文件不存在: {dict_path}")
        return False
    
    try:
        with open(dict_path, 'r', encoding='utf-8') as f:
            data_dict = json.load(f)
        
        print(f"  ✅ 数据字典文件存在: {dict_path}")
        
        # 显示数据字典摘要
        print(f"\n  数据字典摘要:")
        print(f"    表名: {data_dict.get('metadata', {}).get('table_name', 'N/A')}")
        print(f"    创建日期: {data_dict.get('metadata', {}).get('created_date', 'N/A')}")
        print(f"    版本: {data_dict.get('metadata', {}).get('version', 'N/A')}")
        
        if 'stock_info' in data_dict:
            stock_info = data_dict['stock_info']
            print(f"    股票: {stock_info.get('code', 'N/A')} {stock_info.get('name', 'N/A')}")
            print(f"    行业: {stock_info.get('sector', 'N/A')}")
        
        if 'data_dictionary' in data_dict:
            columns = data_dict['data_dictionary'].get('column_definitions', [])
            print(f"    字段数: {len(columns)}")
            
            # 显示前10个字段
            print(f"\n    字段列表 (前10个):")
            col_data = []
            for col in columns[:10]:
                col_data.append([
                    col.get('name', 'N/A'),
                    col.get('type', 'N/A'),
                    col.get('description', 'N/A')[:30] + '...' if len(col.get('description', '')) > 30 else col.get('description', 'N/A')
                ])
            
            if col_data:
                print(tabulate(col_data,
                              headers=['字段名', '类型', '描述'],
                              tablefmt='simple',
                              stralign='left'))
                if len(columns) > 10:
                    print(f"    ... 还有 {len(columns) - 10} 个字段")
        
        if 'data_statistics' in data_dict:
            stats = data_dict['data_statistics']
            print(f"\n    统计信息:")
            print(f"      总记录数: {stats.get('total_records', 0):,}")
            date_range = stats.get('date_range', {})
            print(f"      日期范围: {date_range.get('earliest', 'N/A')} ~ {date_range.get('latest', 'N/A')}")
        
        if 'update_history' in data_dict:
            history = data_dict['update_history']
            print(f"\n    更新历史: {len(history)} 次更新")
            if history:
                last_update = history[-1]
                print(f"      最近更新: {last_update.get('update_date', 'N/A')}")
                print(f"      操作: {last_update.get('action', 'N/A')}")
                print(f"      股票: {last_update.get('stock_code', 'N/A')} {last_update.get('stock_name', 'N/A')}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"  ❌ 数据字典JSON格式错误: {e}")
        return False
    except Exception as e:
        print(f"  ❌ 读取数据字典失败: {e}")
        return False

# =====================================================
# 4. 数据库连接
# =====================================================

def get_db_connection():
    """获取数据库连接"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.text_factory = str
    return conn

# =====================================================
# 5. 数据验证函数
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

def get_stock_statistics(conn, table_name):
    """获取每只股票的统计数据"""
    # 先获取日期字段名（可能是 date 或 Date）
    date_col = get_date_column(conn, table_name)
    
    query = f"""
        SELECT 
            stock_code,
            stock_name,
            COUNT(*) as record_count,
            MIN({date_col}) as first_date,
            MAX({date_col}) as last_date,
            COUNT(DISTINCT {date_col}) as trading_days
        FROM {table_name}
        GROUP BY stock_code, stock_name
        ORDER BY stock_code
    """
    df = pd.read_sql_query(query, conn)
    return df

def get_date_column(conn, table_name):
    """获取表中的日期列名（可能是 date 或 Date）"""
    col_info = get_table_info(conn, table_name)
    for _, row in col_info.iterrows():
        col_name = row['name']
        if col_name.lower() == 'date':
            return col_name
    return 'date'  # 默认返回 'date'

def get_table_sample(conn, table_name, limit=10):
    """获取表的最新记录（按日期升序）"""
    try:
        date_col = get_date_column(conn, table_name)
        
        # 获取最新的 N 条记录（按日期降序取最新，然后升序显示）
        query = f"""
            SELECT * FROM {table_name} 
            ORDER BY {date_col} DESC 
            LIMIT {limit}
        """
        df = pd.read_sql_query(query, conn)
        
        # 按日期升序排列
        if not df.empty and date_col in df.columns:
            df = df.sort_values(date_col, ascending=True)
        
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
        date_col = get_date_column(conn, table_name)
        query = f"""
            SELECT stock_code, {date_col} as date, COUNT(*) as count 
            FROM {table_name} 
            GROUP BY stock_code, {date_col} 
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"  ⚠️ 重复检查失败: {e}")
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
    date_col = get_date_column(conn, table_name)
    query = f"""
        SELECT 
            stock_code,
            stock_name,
            MIN({date_col}) as first_date,
            MAX({date_col}) as last_date,
            COUNT(*) as record_count
        FROM {table_name}
        GROUP BY stock_code, stock_name
        ORDER BY stock_code
    """
    df = pd.read_sql_query(query, conn)
    return df

def check_moneyflow_rules(conn, table_name):
    """检查资金流数据的合理性规则"""
    print("\n" + "-" * 80)
    print(" 💰 资金流数据合理性检查")
    print("-" * 80)
    
    # 获取所有数值字段
    col_info = get_table_info(conn, table_name)
    numeric_cols = [col['name'] for col in col_info.to_dict('records') 
                    if col['type'].upper() in ['REAL', 'FLOAT', 'NUMERIC'] 
                    and col['name'] not in ['id']]
    
    if not numeric_cols:
        print("  ⚠️ 未找到数值字段")
        return []
    
    print(f"  检查 {len(numeric_cols)} 个数值字段")
    
    issues = []
    total_records = get_table_count(conn, table_name)
    
    # 资金流字段（可以正负）
    money_flow_fields = ['Capital_Trend', 'Extra_Large', 'Large', 'Medium', 'Small', 
                         'Institutional_Flow', 'Individual_Flow', 'Inst_5MA', 'Ind_5MA', 'FBI']
    
    # 百分比字段（可以正负）
    pct_fields = ['Price_ChgPct']
    
    # 应该非负的字段
    non_negative_fields = ['IDR']  # IDR 通常是非负的
    
    # 1. 检查资金流字段的统计信息
    print(f"\n  1. 资金流字段统计:")
    flow_fields = [col for col in numeric_cols if col in money_flow_fields]
    
    if flow_fields:
        for col in flow_fields:
            try:
                query = f"""
                    SELECT 
                        MIN({col}) as min_val,
                        MAX({col}) as max_val,
                        AVG({col}) as avg_val,
                        COUNT(*) as total_count
                    FROM {table_name}
                    WHERE {col} IS NOT NULL
                """
                df = pd.read_sql_query(query, conn)
                if not df.empty and df['total_count'].iloc[0] > 0:
                    min_val = df['min_val'].iloc[0]
                    max_val = df['max_val'].iloc[0]
                    avg_val = df['avg_val'].iloc[0]
                    print(f"     - {col}: 最小={min_val:,.2f}, 最大={max_val:,.2f}, 平均={avg_val:,.2f}")
                    
                    # 检查是否有正负值
                    if min_val < 0 and max_val > 0:
                        print(f"       ✓ 包含正负值（正常）")
                    elif min_val >= 0:
                        print(f"       ⚠️ 全部为非负值（可能异常）")
                    elif max_val <= 0:
                        print(f"       ⚠️ 全部为非正值（可能异常）")
            except Exception as e:
                print(f"     - {col}: 分析失败 - {e}")
    else:
        print("     未找到资金流字段")
    
    # 2. 检查百分比字段
    print(f"\n  2. 百分比字段统计:")
    pct_flow_fields = [col for col in numeric_cols if col in pct_fields]
    
    if pct_flow_fields:
        for col in pct_flow_fields:
            try:
                query = f"""
                    SELECT 
                        MIN({col}) as min_val,
                        MAX({col}) as max_val,
                        AVG({col}) as avg_val,
                        COUNT(*) as total_count
                    FROM {table_name}
                    WHERE {col} IS NOT NULL
                """
                df = pd.read_sql_query(query, conn)
                if not df.empty and df['total_count'].iloc[0] > 0:
                    min_val = df['min_val'].iloc[0]
                    max_val = df['max_val'].iloc[0]
                    avg_val = df['avg_val'].iloc[0]
                    print(f"     - {col}: 最小={min_val:.2f}%, 最大={max_val:.2f}%, 平均={avg_val:.2f}%")
                    
                    # 检查百分比范围是否合理
                    if min_val < -20 or max_val > 20:
                        print(f"       ⚠️ 百分比范围可能过大（正常应在 ±20% 以内）")
                    else:
                        print(f"       ✓ 百分比范围合理")
            except Exception as e:
                print(f"     - {col}: 分析失败 - {e}")
    else:
        print("     未找到百分比字段")
    
    # 3. 检查非负字段
    print(f"\n  3. 非负字段检查:")
    non_neg_fields = [col for col in numeric_cols if col in non_negative_fields]
    
    if non_neg_fields:
        for col in non_neg_fields:
            try:
                query = f"""
                    SELECT COUNT(*) as negative_count 
                    FROM {table_name} 
                    WHERE {col} < 0
                """
                df = pd.read_sql_query(query, conn)
                count = df['negative_count'].iloc[0]
                if count > 0:
                    percentage = (count / total_records * 100) if total_records > 0 else 0
                    print(f"     ⚠️ {col}: {count:,} 条负值记录 ({percentage:.1f}%)")
                    issues.append(f"字段 {col} 包含负值（应为非负）")
                else:
                    print(f"     ✅ {col}: 全部为非负值")
            except Exception as e:
                print(f"     - {col}: 检查失败 - {e}")
    else:
        print("     无非负字段需要检查")
    
    # 4. 检查数据完整性
    print(f"\n  4. 数据完整性检查:")
    
    # 检查每只股票的记录数是否一致
    stock_stats = get_stock_statistics(conn, table_name)
    if not stock_stats.empty:
        avg_records = stock_stats['record_count'].mean()
        min_records = stock_stats['record_count'].min()
        max_records = stock_stats['record_count'].max()
        
        print(f"     每只股票记录数:")
        print(f"       平均: {avg_records:.1f} 条")
        print(f"       最少: {min_records} 条")
        print(f"       最多: {max_records} 条")
        
        # 检查是否有股票记录数明显偏少
        threshold = avg_records * 0.5
        low_count_stocks = stock_stats[stock_stats['record_count'] < threshold]
        if not low_count_stocks.empty:
            print(f"       ⚠️ 发现 {len(low_count_stocks)} 只股票记录数偏少（少于平均值50%）:")
            for _, row in low_count_stocks.head(5).iterrows():
                print(f"         - {row['stock_code']} {row['stock_name']}: {row['record_count']} 条")
    
    return issues

def check_moneyflow_integrity(conn, table_name):
    """检查资金流数据完整性"""
    print("\n" + "-" * 80)
    print(" 🔍 资金流数据完整性检查")
    print("-" * 80)
    
    col_info = get_table_info(conn, table_name)
    columns = [col['name'] for col in col_info.to_dict('records')]
    
    # 检查必要的字段是否存在（不区分大小写）
    required_fields = ['stock_code', 'stock_name']
    # 检查日期字段（可能是 date 或 Date）
    date_fields = [col for col in columns if col.lower() == 'date']
    
    missing_fields = [f for f in required_fields if f not in columns]
    
    if missing_fields:
        print(f"  ❌ 缺少必要字段: {missing_fields}")
        return False
    
    if not date_fields:
        print(f"  ❌ 缺少日期字段（date 或 Date）")
        return False
    else:
        print(f"  ✅ 找到日期字段: {', '.join(date_fields)}")
    
    # 检查资金流字段是否存在
    flow_keywords = ['flow', 'trend', 'large', 'medium', 'small', 'institutional', 'individual']
    flow_fields = [col for col in columns if any(keyword in col.lower() for keyword in flow_keywords)]
    
    if flow_fields:
        print(f"  ✅ 找到资金流字段: {', '.join(flow_fields[:5])}")
        if len(flow_fields) > 5:
            print(f"     ... 还有 {len(flow_fields) - 5} 个资金流字段")
    else:
        print(f"  ⚠️ 未找到资金流字段")
    
    # 检查日期格式
    try:
        date_col = date_fields[0]
        query = f"SELECT {date_col} FROM {table_name} LIMIT 100"
        df = pd.read_sql_query(query, conn)
        if not df.empty:
            # 检查日期格式是否为 YYYY-MM-DD
            invalid_dates = 0
            for date_str in df[date_col]:
                if date_str and not re.match(r'^\d{4}-\d{2}-\d{2}$', str(date_str)):
                    invalid_dates += 1
            if invalid_dates > 0:
                print(f"  ⚠️ 发现 {invalid_dates} 条日期格式不正确的记录（样例中）")
            else:
                print("  ✅ 日期格式正确")
    except Exception as e:
        print(f"  ⚠️ 日期格式检查失败: {e}")
    
    return True

# =====================================================
# 6. 显示函数
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

    # 股票统计
    stock_stats = get_stock_statistics(conn, table_name)
    if not stock_stats.empty:
        print(f"\n  📈 股票统计:")
        print(f"    股票数量: {len(stock_stats)} 只")
        print(f"    总交易天数: {stock_stats['trading_days'].sum():,}")
        print(f"    平均每只股票记录数: {stock_stats['record_count'].mean():.1f}")

    # 日期范围
    date_range = get_date_range_per_stock(conn, table_name)
    if not date_range.empty:
        min_date = date_range['first_date'].min()
        max_date = date_range['last_date'].max()
        print(f"\n  📅 全局日期范围:")
        print(f"    最早日期: {min_date}")
        print(f"    最晚日期: {max_date}")
        if min_date and max_date:
            try:
                days = (pd.to_datetime(max_date) - pd.to_datetime(min_date)).days + 1
                print(f"    总交易日数: {days}")
            except:
                pass

def display_stock_statistics(conn, table_name):
    """显示每只股票的统计信息"""
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
        display_data.append([
            in_config,
            row['stock_code'],
            row['stock_name'],
            f"{row['record_count']:,}",
            row['first_date'],
            row['last_date']
        ])

    print(tabulate(display_data,
                   headers=['状态', '代码', '名称', '记录数', '开始日期', '结束日期'],
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

    # 选择要显示的列（优先显示资金流相关字段）
    priority_cols = ['stock_code', 'stock_name', 'date']
    # 查找资金流相关字段
    flow_cols = [col for col in df.columns if 'flow' in col.lower() or 'trend' in col.lower() 
                 or 'large' in col.lower() or 'medium' in col.lower() or 'small' in col.lower()
                 or 'institutional' in col.lower() or 'individual' in col.lower()]
    # 取前几个资金流字段
    flow_cols = flow_cols[:5] if len(flow_cols) > 5 else flow_cols
    
    display_cols = priority_cols + flow_cols
    
    # 如果资金流字段不够，补充其他字段
    if len(display_cols) < 10:
        other_cols = [col for col in df.columns if col not in display_cols and col != 'id']
        display_cols += other_cols[:10 - len(display_cols)]
    
    available_cols = [col for col in display_cols if col in df.columns]

    if not available_cols:
        available_cols = df.columns.tolist()

    df_display = df[available_cols].copy()

    # 格式化数值
    for col in df_display.columns:
        if col not in ['stock_code', 'stock_name', 'date']:
            try:
                df_display[col] = df_display[col].apply(lambda x: f"{float(x):.2f}" if pd.notna(x) and x != '' else '')
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

    # 3. 缺失股票检查
    missing_stocks, extra_stocks = check_missing_stocks(conn, table_name)
    print(f"\n  3. 缺失股票检查:")
    if missing_stocks:
        print(f"     ⚠️ 缺失 {len(missing_stocks)} 只股票（在配置文件中但不在数据库中）:")
        for code in sorted(missing_stocks):
            stock_info = STOCK_MAP.get(code, {})
            name = stock_info.get('name', '未知')
            sector = stock_info.get('sector', 'N/A')
            print(f"       - {code} {name} ({sector})")
    else:
        print("     ✅ 所有配置的股票都有数据")
    
    # 4. 额外股票检查（数据库中有的但配置文件中没有）
    if extra_stocks:
        print(f"\n  4. 额外股票检查:")
        print(f"     ⚠️ 发现 {len(extra_stocks)} 只额外股票（在数据库中但不在配置文件中）:")
        for code in sorted(extra_stocks):
            # 从数据库获取名称
            query = f"SELECT stock_name FROM {table_name} WHERE stock_code='{code}' LIMIT 1"
            df = pd.read_sql_query(query, conn)
            name = df['stock_name'].iloc[0] if not df.empty else '未知'
            print(f"       - {code} {name}")
    else:
        print("\n  4. 额外股票检查: ✅ 无额外股票")

    # 5. 资金流数据完整性检查
    check_moneyflow_integrity(conn, table_name)
    check_moneyflow_rules(conn, table_name)

# =====================================================
# 7. 生成验证报告
# =====================================================

def generate_report(conn, table_name):
    """生成验证报告"""
    REPORT_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"Moneyflow_Daily_Verify_{timestamp}.txt"
    report_path = REPORT_DIR / report_filename
    json_report_path = REPORT_DIR / f"Moneyflow_Daily_Verify_{timestamp}.json"

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
            'missing_stocks': [],
            'extra_stocks': []
        }
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

    missing_stocks, extra_stocks = check_missing_stocks(conn, table_name)
    validation_data['quality_checks']['missing_stocks'] = list(missing_stocks)
    validation_data['quality_checks']['extra_stocks'] = list(extra_stocks)

    # 保存JSON报告
    with open(json_report_path, 'w', encoding='utf-8') as f:
        json.dump(validation_data, f, ensure_ascii=False, indent=2, default=str)

    # 生成文本报告
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("日资金流分析数据验证报告\n")
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
            f.write(f"{row['first_date']} ~ {row['last_date']}\n")
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

        # 缺失股票
        f.write(f"3. 缺失股票检查: {len(missing_stocks)} 只缺失\n")
        for code in sorted(missing_stocks):
            stock_info = STOCK_MAP.get(code, {})
            name = stock_info.get('name', '未知')
            sector = stock_info.get('sector', 'N/A')
            f.write(f"     {code} {name} ({sector})\n")
        f.write("\n")

        # 额外股票
        f.write(f"4. 额外股票检查: {len(extra_stocks)} 只额外\n")
        for code in sorted(extra_stocks):
            query = f"SELECT stock_name FROM {table_name} WHERE stock_code='{code}' LIMIT 1"
            df = pd.read_sql_query(query, conn)
            name = df['stock_name'].iloc[0] if not df.empty else '未知'
            f.write(f"     {code} {name}\n")
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
    print("日资金流分析数据验证工具")
    print("=" * 80)
    print(f"项目目录: {project_dir}")
    print(f"数据库路径: {DB_PATH}")
    print(f"配置文件股票数: {len(STOCK_LIST)}")
    print("=" * 80)

    # 检查数据库是否存在
    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("请先运行 Import_Daily_Moneyflow_Analysis.py 导入数据")
        sys.exit(1)

    TABLE_NAME = 'hk_daily_moneyflow_analysis'

    # 获取数据库连接
    conn = get_db_connection()

    try:
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}'")
        if not cursor.fetchone():
            print(f"❌ 表 {TABLE_NAME} 不存在")
            print("请先运行 Import_Daily_Moneyflow_Analysis.py 导入数据")
            return

        # 检查数据字典
        check_data_dictionary()

        # 显示表摘要
        display_table_summary(conn, TABLE_NAME)

        # 显示股票统计
        display_stock_statistics(conn, TABLE_NAME)

        # 显示样本数据
        display_sample_data(conn, TABLE_NAME, limit=10)

        # 显示数据质量检查
        display_quality_checks(conn, TABLE_NAME)

        # 生成报告
        print("\n" + "-" * 80)
        print("生成验证报告...")
        print("-" * 80)

        txt_report, json_report = generate_report(conn, TABLE_NAME)
        print(f"✅ 文本报告已生成: {txt_report}")
        print(f"✅ JSON报告已生成: {json_report}")

        # 汇总统计
        print("\n" + "=" * 80)
        print("验证完成!")
        print("=" * 80)
        
        # 显示验证摘要
        total_records = get_table_count(conn, TABLE_NAME)
        stock_stats = get_stock_statistics(conn, TABLE_NAME)
        print(f"\n📊 验证摘要:")
        print(f"  表名: {TABLE_NAME}")
        print(f"  总记录数: {total_records:,}")
        print(f"  股票数量: {len(stock_stats)} 只")
        
        # 检查质量状态
        null_counts = check_null_values(conn, TABLE_NAME)
        total_nulls = sum(null_counts.values())
        duplicates = check_duplicates(conn, TABLE_NAME)
        missing_stocks, extra_stocks = check_missing_stocks(conn, TABLE_NAME)
        
        print(f"\n✅ 质量状态:")
        print(f"  空值: {'✅ 无' if total_nulls == 0 else f'⚠️ {total_nulls} 个'}")
        print(f"  重复: {'✅ 无' if duplicates.empty else f'⚠️ {len(duplicates)} 组'}")
        print(f"  缺失股票: {'✅ 无' if not missing_stocks else f'⚠️ {len(missing_stocks)} 只'}")
        print(f"  额外股票: {'✅ 无' if not extra_stocks else f'⚠️ {len(extra_stocks)} 只'}")

    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    import re
    main()