#!/usr/bin/env python
# coding: utf-8

"""
Import_Monthly_Moneyflow.py
将月资金流数据CSV文件导入SQLite数据库
从CSV文件解析股票代码，匹配股票名称，创建hk_hist_monthly_moneyflow表

脚本位置: TA_Workflow2/Code_utl/Import_Monthly_Moneyflow.py
"""

import os
import sys
import pandas as pd
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import warnings
import re
import configparser

warnings.filterwarnings('ignore')

# =====================================================
# 1. 路径设置（参考Import_Daily_Kline_Data.py）
# =====================================================

def get_project_dir():
    """
    获取项目根目录 (TA_Workflow2)
    脚本位于 TA_Workflow2/Code_utl/ 目录下
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
        
        # 验证是否真的是项目根目录（检查是否存在config目录）
        if (project_dir / 'Config').exists():
            return project_dir
        
        # 如果找不到config，尝试其他方式
        if script_path.parent.name == 'Code_utl':
            return script_path.parent.parent
        
        # 尝试从当前工作目录向上查找
        cwd = Path(os.getcwd()).resolve()
        for parent in [cwd] + list(cwd.parents):
            if (parent / 'Config').exists() and (parent / 'Code_utl').exists():
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

# 添加必要的路径到 sys.path
# 1. 项目根目录
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))
    print(f"[INFO] 已添加项目根目录到 sys.path: {project_dir}")

# 2. Core 目录（包含 Utl 子目录）
core_dir = project_dir / 'Core'
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))
    print(f"[INFO] 已添加 Core 目录到 sys.path: {core_dir}")

# 3. 直接添加 Utl 目录
utl_dir = project_dir / 'Core' / 'Utl'
if str(utl_dir) not in sys.path:
    sys.path.insert(0, str(utl_dir))
    print(f"[INFO] 已添加 Utl 目录到 sys.path: {utl_dir}")

# 导入股票列表加载工具
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

# 验证配置文件存在
if not config_path.exists():
    alt_path = project_dir.parent / 'Config' / 'stock_data_analysis.par'
    if alt_path.exists():
        config_path = alt_path
        print(f"[INFO] 使用备用配置文件路径: {config_path}")
    else:
        print(f"[ERROR] 配置文件不存在: {config_path}")
        print("[ERROR] 程序退出")
        sys.exit(1)

# 加载配置
def load_config(config_path, project_dir):
    """加载配置文件"""
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
    
    # 构建完整路径
    data_rel = config.get('data_dir', 'Data')
    config['full_data_dir'] = os.path.join(str(project_dir), data_rel)
    
    sqlite_rel = config.get('sqlite_dir', 'SQLiteDB')
    config['full_sqlite_dir'] = os.path.join(str(project_dir), sqlite_rel)
    
    db_name = config.get('db_name', 'HK_Stock.db')
    config['full_db_path'] = os.path.join(config['full_sqlite_dir'], db_name)
    
    # 确保目录存在
    for path_key in ['full_data_dir', 'full_sqlite_dir']:
        path = config.get(path_key)
        if path and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
    
    return config

# 加载配置
CONFIG = load_config(str(config_path), str(project_dir))

# 强制 UTF-8 输出
setup_windows_encoding()

# 路径设置
DATA_DIR = Path(CONFIG.get('full_data_dir'))
DB_DIR = Path(CONFIG.get('full_sqlite_dir'))
DB_PATH = Path(CONFIG.get('full_db_path'))

print(f"[INFO] 数据目录: {DATA_DIR}")
print(f"[INFO] 数据库目录: {DB_DIR}")
print(f"[INFO] 数据库路径: {DB_PATH}")

# 显示股票列表摘要
print(f"\n[INFO] 股票列表摘要:")
print(f"  总股票数: {len(STOCK_LIST)}")
if STOCK_LIST:
    print(f"  股票代码范围: {STOCK_LIST[0]['code']} ~ {STOCK_LIST[-1]['code']}")
    sectors = set(s.get('sector', 'N/A') for s in STOCK_LIST)
    print(f"  涉及行业: {', '.join(sectors)}")
print()

# =====================================================
# 3. 辅助函数：列名转小写
# =====================================================

def to_lower_column_name(col_name):
    """
    将列名转换为小写，同时处理特殊字符
    """
    if not col_name:
        return col_name
    
    # 去除首尾空格并转为小写
    col_lower = col_name.strip().lower()
    
    # 处理特殊字符
    col_lower = col_lower.replace(' ', '_')
    col_lower = col_lower.replace('/', '_')
    col_lower = col_lower.replace('(', '')
    col_lower = col_lower.replace(')', '')
    col_lower = col_lower.replace('%', 'pct')
    col_lower = col_lower.replace('-', '_')
    col_lower = col_lower.replace('+', '_')
    col_lower = col_lower.replace('*', '_')
    col_lower = col_lower.replace('&', '_')
    col_lower = col_lower.replace('@', '_')
    col_lower = col_lower.replace('#', '_')
    col_lower = col_lower.replace('$', '_')
    col_lower = col_lower.replace('!', '_')
    col_lower = col_lower.replace('?', '_')
    col_lower = col_lower.replace('.', '_')
    
    # 去除连续的下划线
    while '__' in col_lower:
        col_lower = col_lower.replace('__', '_')
    
    # 去除首尾下划线
    col_lower = col_lower.strip('_')
    
    return col_lower

# =====================================================
# 4. 数据库操作函数
# =====================================================

def get_db_connection():
    """获取数据库连接"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.text_factory = str
    return conn

def table_exists(conn, table_name):
    """检查表是否存在"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    return cursor.fetchone() is not None

def get_table_schema(conn, table_name):
    """获取表结构"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()

def create_table_if_not_exists(conn):
    """
    创建 hk_hist_monthly_moneyflow 表（如果不存在）
    所有列名均为小写
    将 stock_code 和 stock_name 放在最前面
    创建复合索引 (stock_code, date)
    """
    # 先读取一个CSV文件样例来获取列结构
    csv_files = list(DATA_DIR.glob("*_monthly_moneyflow.csv"))
    if not csv_files:
        print(f"[ERROR] 未找到任何 *_monthly_moneyflow.csv 文件")
        return False
    
    # 读取第一个CSV文件获取列结构
    sample_file = csv_files[0]
    try:
        df_sample = pd.read_csv(sample_file)
        
        # 构建CREATE TABLE语句 - 将 stock_code 和 stock_name 放在最前面
        columns = [
            'stock_code TEXT',
            'stock_name TEXT',
            'date TEXT'
        ]
        
        # 添加其他列（所有列名转为小写）
        for col in df_sample.columns:
            # 转换为小写列名
            col_lower = to_lower_column_name(col)
            
            # 如果是date列，跳过（我们已经添加了date字段）
            if col_lower == 'date':
                continue
            
            # 根据列名和数据类型选择合适的SQLite类型
            # 资金流相关字段用REAL类型
            if 'amount' in col_lower or 'volume' in col_lower or 'value' in col_lower:
                col_type = 'REAL'
            elif 'pct' in col_lower or 'ratio' in col_lower:
                col_type = 'REAL'
            elif 'count' in col_lower:
                col_type = 'INTEGER'
            elif 'net' in col_lower and ('inflow' in col_lower or 'outflow' in col_lower):
                col_type = 'REAL'
            elif 'main' in col_lower or 'force' in col_lower or 'retail' in col_lower:
                col_type = 'REAL'
            elif 'price' in col_lower and 'chg' in col_lower:
                col_type = 'REAL'
            elif 'turnover' in col_lower:
                col_type = 'REAL'
            else:
                # 检查数据类型
                try:
                    if pd.api.types.is_integer_dtype(df_sample[col]):
                        col_type = 'INTEGER'
                    elif pd.api.types.is_float_dtype(df_sample[col]):
                        col_type = 'REAL'
                    elif pd.api.types.is_datetime64_any_dtype(df_sample[col]):
                        col_type = 'TEXT'
                    else:
                        col_type = 'TEXT'
                except:
                    col_type = 'TEXT'
            
            columns.append(f'"{col_lower}" {col_type}')
        
        # 创建表
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS hk_hist_monthly_moneyflow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(columns)}
        )
        """
        
        conn.execute(create_sql)
        print(f"[INFO] 表 hk_hist_monthly_moneyflow 已创建或已存在（所有列名已转为小写）")
        
        # 创建复合索引 (stock_code, date)
        try:
            # 检查索引是否已存在
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name='idx_stock_code_date'
            """)
            if not cursor.fetchone():
                create_index_sql = """
                CREATE INDEX idx_stock_code_date 
                ON hk_hist_monthly_moneyflow (stock_code, date)
                """
                conn.execute(create_index_sql)
                print(f"[INFO] 已创建复合索引 idx_stock_code_date")
            else:
                print(f"[INFO] 复合索引 idx_stock_code_date 已存在")
        except Exception as e:
            print(f"[WARN] 创建索引失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建表失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
def recreate_table(conn):
    """
    重新创建表（删除旧表并创建新表）
    """
    try:
        # 删除旧表
        if table_exists(conn, 'hk_hist_monthly_moneyflow'):
            conn.execute("DROP TABLE hk_hist_monthly_moneyflow")
            print("[INFO] 已删除旧表 hk_hist_monthly_moneyflow")
        
        # 创建新表
        if create_table_if_not_exists(conn):
            print("[INFO] 已重新创建表 hk_hist_monthly_moneyflow（所有列名已转为小写）")
            return True
        else:
            print("[ERROR] 重新创建表失败")
            return False
    except Exception as e:
        print(f"[ERROR] 重新创建表失败: {e}")
        return False

def import_csv_to_db(csv_path, conn, stock_code, stock_name):
    """
    将CSV文件导入数据库
    所有列名转为小写
    处理特殊字段：将 price_chgpct 数值乘以100
    """
    try:
        # ========== 修复：确保表存在 ==========
        if not table_exists(conn, 'hk_hist_monthly_moneyflow'):
            print(f"   ⚠️ 表 hk_hist_monthly_moneyflow 不存在，正在创建...")
            if not create_table_if_not_exists(conn):
                print(f"   ❌ 创建表失败")
                return 0
        
        # 读取CSV文件
        df = pd.read_csv(csv_path)
        
        # 将所有列名转为小写
        column_mapping = {}
        for col in df.columns:
            col_lower = to_lower_column_name(col)
            column_mapping[col] = col_lower
        
        df = df.rename(columns=column_mapping)
        
        # 确保有date列，并提取date数据
        date_col = None
        for col in df.columns:
            if col == 'date':
                date_col = col
                break
        
        if date_col is None:
            print(f"   ⚠️ 未找到日期列")
            return 0
        
        # 处理 price_chgpct 列：将数值乘以100
        price_chg_col = None
        for col in df.columns:
            if col == 'price_chgpct' or col == 'price_chg_pct':
                price_chg_col = col
                break
            elif 'price' in col and 'chg' in col and 'pct' in col:
                price_chg_col = col
                break
        
        if price_chg_col:
            # 将数值乘以100
            df[price_chg_col] = pd.to_numeric(df[price_chg_col], errors='coerce') * 100
            print(f"   📊 已将 {price_chg_col} 列数值乘以100")
        
        # 获取所有列（除了date列）
        other_cols = [col for col in df.columns if col != date_col]
        
        # 创建新的DataFrame，按正确顺序排列
        df_new = pd.DataFrame()
        
        # 确保 stock_code 和 stock_name 不是空值，且为字符串类型
        df_new['stock_code'] = str(stock_code).strip()
        df_new['stock_name'] = str(stock_name).strip()
        df_new['date'] = pd.to_datetime(df[date_col]).dt.strftime('%Y-%m-%d')
        
        # 添加其他列（保持小写）
        for col in other_cols:
            df_new[col] = df[col]
        
        # 数值列四舍五入
        for col in df_new.select_dtypes(include=['float64', 'float32']).columns:
            if col not in ['stock_code', 'stock_name']:
                df_new[col] = df_new[col].round(4)
        
        # 检查是否有空值在 stock_code 或 stock_name 中
        if df_new['stock_code'].isna().any() or df_new['stock_code'].eq('').any():
            print(f"   ⚠️ 发现空的 stock_code，填充为 {stock_code}")
            df_new['stock_code'] = df_new['stock_code'].fillna(stock_code).replace('', stock_code)
        
        if df_new['stock_name'].isna().any() or df_new['stock_name'].eq('').any():
            print(f"   ⚠️ 发现空的 stock_name，填充为 {stock_name}")
            df_new['stock_name'] = df_new['stock_name'].fillna(stock_name).replace('', stock_name)
        
        # 确保数据类型正确
        df_new['stock_code'] = df_new['stock_code'].astype(str)
        df_new['stock_name'] = df_new['stock_name'].astype(str)
        df_new['date'] = df_new['date'].astype(str)
        
        # ========== 修复：使用更安全的方式导入数据 ==========
        # 导入数据
        try:
            # 首先检查表是否存在
            if not table_exists(conn, 'hk_hist_monthly_moneyflow'):
                print(f"   ⚠️ 表不存在，正在创建...")
                create_table_if_not_exists(conn)
            
            # 使用 to_sql 追加数据
            df_new.to_sql('hk_hist_monthly_moneyflow', conn, if_exists='append', index=False)
            print(f"   ✅ 已导入 {len(df_new)} 条记录")
            return len(df_new)
            
        except Exception as e:
            # 如果出现 "table already exists" 错误，尝试重新创建表
            if "already exists" in str(e).lower():
                print(f"   ⚠️ 表存在但结构可能不匹配，尝试重新创建...")
                # 删除表
                conn.execute("DROP TABLE IF EXISTS hk_hist_monthly_moneyflow")
                # 重新创建表
                if create_table_if_not_exists(conn):
                    # 再次尝试导入
                    df_new.to_sql('hk_hist_monthly_moneyflow', conn, if_exists='append', index=False)
                    print(f"   ✅ 已导入 {len(df_new)} 条记录")
                    return len(df_new)
                else:
                    print(f"   ❌ 重新创建表失败")
                    return 0
            else:
                raise e
        
    except Exception as e:
        print(f"   ❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return 0

def clear_table(conn, table_name):
    """清空表数据"""
    if table_exists(conn, table_name):
        conn.execute(f"DELETE FROM {table_name}")
        conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")
        print(f"[INFO] 已清空表 {table_name}")
        return True
    return False

def drop_table(conn, table_name):
    """删除表"""
    if table_exists(conn, table_name):
        conn.execute(f"DROP TABLE {table_name}")
        print(f"[INFO] 已删除表 {table_name}")
        return True
    return False

# =====================================================
# 5. 创建数据字典（完整JSON格式）
# =====================================================

def create_data_dictionary(conn):
    """
    创建完整的数据字典 hk_hist_monthly_moneyflow_dictionary.json
    所有列名转为小写
    """
    print("\n" + "-"*60)
    print("创建数据字典...")
    
    dict_path = project_dir / 'Config' / 'hk_hist_monthly_moneyflow_dictionary.json'
    
    # 如果文件已存在，读取现有数据
    existing_dict = {}
    if dict_path.exists():
        try:
            with open(dict_path, 'r', encoding='utf-8') as f:
                existing_dict = json.load(f)
            print(f"[INFO] 读取现有数据字典: {dict_path}")
        except Exception as e:
            print(f"[WARN] 读取现有数据字典失败: {e}")
            existing_dict = {}
    
    # 获取CSV文件列表
    csv_files = list(DATA_DIR.glob("*_monthly_moneyflow.csv"))
    if not csv_files:
        print(f"[WARN] 未找到CSV文件，无法创建数据字典")
        return
    
    # 读取所有CSV文件获取完整信息
    all_columns = set()
    sample_df = None
    file_info = []
    
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            filename = csv_file.stem
            code = filename.split('_')[0] if filename.split('_') else filename
            
            # 获取日期范围
            date_col = None
            for col in df.columns:
                col_lower = to_lower_column_name(col)
                if col_lower == 'date':
                    date_col = col
                    break
            
            file_info.append({
                'filename': csv_file.name,
                'code': code,
                'rows': len(df),
                'columns': [to_lower_column_name(col) for col in df.columns],
                'date_range': {
                    'start': df[date_col].iloc[0] if date_col else None,
                    'end': df[date_col].iloc[-1] if date_col else None
                }
            })
            
            # 使用小写列名
            for col in df.columns:
                all_columns.add(to_lower_column_name(col))
                
            if sample_df is None:
                # 创建使用小写列名的DataFrame
                sample_df = df.copy()
                sample_df.columns = [to_lower_column_name(col) for col in sample_df.columns]
        except Exception as e:
            print(f"   ⚠️ 读取 {csv_file.name} 失败: {e}")
    
    # 构建数据字典
    data_dict = {
        'metadata': {
            'table_name': 'hk_hist_monthly_moneyflow',
            'description': '港股月资金流历史数据表（所有列名均为小写）',
            'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0',
            'database': str(DB_PATH.name),
            'data_source': 'CSV files from Data directory',
            'total_files': len(csv_files),
            'total_stocks': len(STOCK_LIST),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'column_naming': 'all lowercase'
        },
        'table_schema': {
            'primary_key': 'id',
            'columns_order': ['stock_code', 'stock_name', 'date', '...'],
            'columns': [],
            'indexes': [
                {
                    'name': 'idx_stock_code_date',
                    'fields': ['stock_code', 'date'],
                    'type': '复合索引',
                    'description': '用于快速查询特定股票的月资金流数据'
                }
            ],
            'constraints': [
                'PRIMARY KEY (id)',
                'UNIQUE (stock_code, date)'
            ]
        },
        'stock_list': STOCK_LIST,
        'data_statistics': {
            'total_records': 0,
            'stocks_loaded': [],
            'date_range': {
                'earliest': None,
                'latest': None
            },
            'file_details': file_info
        },
        'field_definitions': [],
        'usage_examples': {
            'query_all': "SELECT * FROM hk_hist_monthly_moneyflow LIMIT 10;",
            'query_by_stock': "SELECT * FROM hk_hist_monthly_moneyflow WHERE stock_code = '01951';",
            'query_date_range': "SELECT * FROM hk_hist_monthly_moneyflow WHERE date BETWEEN '2024-01-01' AND '2024-12-31';",
            'query_with_index': "SELECT * FROM hk_hist_monthly_moneyflow WHERE stock_code = '01951' AND date = '2024-01-01';"
        },
        'data_dictionary': {
            'column_definitions': [],
            'relationships': [],
            'business_rules': []
        }
    }
    
    # 合并现有数据字典的元数据（如果存在）
    if existing_dict and 'metadata' in existing_dict:
        # 保留历史创建日期和版本信息
        if 'created_date' in existing_dict['metadata']:
            data_dict['metadata']['original_created_date'] = existing_dict['metadata']['created_date']
        if 'version' in existing_dict['metadata']:
            data_dict['metadata']['version'] = existing_dict['metadata']['version']
    
    # 添加字段定义（按照表的实际顺序，所有列名小写）
    # 基础字段（放在最前面）
    base_fields = [
        {'name': 'id', 'type': 'INTEGER', 'description': '自增主键', 'constraint': 'PRIMARY KEY AUTOINCREMENT', 'example': '1', 'is_key': True, 'is_required': True},
        {'name': 'stock_code', 'type': 'TEXT', 'description': '股票代码（5位数字）', 'constraint': 'NOT NULL', 'example': '01951', 'is_key': True, 'is_required': True},
        {'name': 'stock_name', 'type': 'TEXT', 'description': '股票名称', 'constraint': 'NOT NULL', 'example': '锦鑫生殖', 'is_key': True, 'is_required': True},
        {'name': 'date', 'type': 'TEXT', 'description': '交易日期（YYYY-MM-DD格式，每月最后一天）', 'constraint': 'NOT NULL', 'example': '2024-01-31', 'is_key': True, 'is_required': True},
    ]
    
    # 从CSV文件提取其他字段（使用小写列名）
    if sample_df is not None:
        for col in sample_df.columns:
            col_lower = to_lower_column_name(col)
            
            # 如果是date列，跳过（已经添加）
            if col_lower == 'date':
                continue
            
            # 确定字段类型和描述
            col_lower_lower = col_lower.lower()
            
            # 资金流相关字段
            if 'net' in col_lower_lower and 'amount' in col_lower_lower:
                field_type = 'REAL'
                description = '净资金流入/流出金额'
                constraint = ''
                example = '10000000'
            elif 'main' in col_lower_lower and 'force' in col_lower_lower and 'inflow' in col_lower_lower:
                field_type = 'REAL'
                description = '主力资金流入金额'
                constraint = ''
                example = '8000000'
            elif 'main' in col_lower_lower and 'force' in col_lower_lower and 'outflow' in col_lower_lower:
                field_type = 'REAL'
                description = '主力资金流出金额'
                constraint = ''
                example = '6000000'
            elif 'main' in col_lower_lower and 'force' in col_lower_lower and 'net' in col_lower_lower:
                field_type = 'REAL'
                description = '主力资金净流入/流出'
                constraint = ''
                example = '2000000'
            elif 'retail' in col_lower_lower and 'inflow' in col_lower_lower:
                field_type = 'REAL'
                description = '散户资金流入金额'
                constraint = ''
                example = '2000000'
            elif 'retail' in col_lower_lower and 'outflow' in col_lower_lower:
                field_type = 'REAL'
                description = '散户资金流出金额'
                constraint = ''
                example = '3000000'
            elif 'retail' in col_lower_lower and 'net' in col_lower_lower:
                field_type = 'REAL'
                description = '散户资金净流入/流出'
                constraint = ''
                example = '-1000000'
            elif 'price' in col_lower_lower and 'chg' in col_lower_lower and 'pct' in col_lower_lower:
                field_type = 'REAL'
                description = '价格变化百分比（已乘以100）'
                constraint = ''
                example = '2.50'
            elif 'price' in col_lower_lower and 'chg' in col_lower_lower:
                field_type = 'REAL'
                description = '价格变化金额'
                constraint = ''
                example = '0.25'
            elif 'volume' in col_lower_lower:
                field_type = 'REAL'
                description = '成交量（股数）'
                constraint = ''
                example = '10000000'
            elif 'amount' in col_lower_lower and 'net' not in col_lower_lower and 'inflow' not in col_lower_lower and 'outflow' not in col_lower_lower:
                field_type = 'REAL'
                description = '成交金额'
                constraint = ''
                example = '50000000'
            elif 'turnover' in col_lower_lower and 'rate' in col_lower_lower:
                field_type = 'REAL'
                description = '换手率（%）'
                constraint = ''
                example = '1.50'
            elif 'turnover' in col_lower_lower:
                field_type = 'REAL'
                description = '换手率'
                constraint = ''
                example = '1.50'
            elif 'pct' in col_lower_lower:
                field_type = 'REAL'
                description = '百分比数据'
                constraint = ''
                example = '10.00'
            elif 'ratio' in col_lower_lower:
                field_type = 'REAL'
                description = '比率数据'
                constraint = ''
                example = '0.75'
            else:
                try:
                    if pd.api.types.is_integer_dtype(sample_df[col]):
                        field_type = 'INTEGER'
                    elif pd.api.types.is_float_dtype(sample_df[col]):
                        field_type = 'REAL'
                    else:
                        field_type = 'TEXT'
                except:
                    field_type = 'TEXT'
                description = f'原始字段: {col}'
                constraint = ''
                example = ''
            
            # 检查是否包含空值
            null_count = sample_df[col].isnull().sum() if col in sample_df.columns else 0
            
            field_def = {
                'name': col_lower,
                'original_name': col,
                'type': field_type,
                'description': description,
                'constraint': constraint,
                'null_count': int(null_count),
                'sample_value': str(sample_df[col].iloc[0]) if len(sample_df) > 0 and not pd.isna(sample_df[col].iloc[0]) else '',
                'example': example,
                'is_key': False,
                'is_required': False
            }
            
            data_dict['data_dictionary']['column_definitions'].append(field_def)
    
    # 添加基础字段到字段定义（放在最前面）
    base_field_defs = []
    for field in base_fields:
        field_def = {
            'name': field['name'],
            'original_name': field['name'],
            'type': field['type'],
            'description': field['description'],
            'constraint': field['constraint'],
            'null_count': 0,
            'sample_value': '',
            'example': field['example'],
            'is_key': field['is_key'],
            'is_required': field['is_required']
        }
        base_field_defs.append(field_def)
    
    # 合并字段定义（基础字段在前）
    data_dict['data_dictionary']['column_definitions'] = base_field_defs + data_dict['data_dictionary']['column_definitions']
    
    # 更新table_schema的columns
    for field in base_field_defs + data_dict['data_dictionary']['column_definitions'][len(base_field_defs):]:
        data_dict['table_schema']['columns'].append({
            'name': field['name'],
            'type': field['type'],
            'description': field['description'],
            'is_key': field['is_key']
        })
    
    # 获取数据库统计信息
    if table_exists(conn, 'hk_hist_monthly_moneyflow'):
        try:
            cursor = conn.cursor()
            
            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM hk_hist_monthly_moneyflow")
            total_records = cursor.fetchone()[0]
            data_dict['data_statistics']['total_records'] = total_records
            
            # 获取每个股票的记录数
            cursor.execute("""
                SELECT stock_code, stock_name, COUNT(*) as count
                FROM hk_hist_monthly_moneyflow
                GROUP BY stock_code, stock_name
                ORDER BY stock_code
            """)
            stocks_loaded = []
            for code, name, count in cursor.fetchall():
                stock_info = {
                    'code': code,
                    'name': name,
                    'record_count': count,
                    'details': next((s for s in STOCK_LIST if s['code'] == code), {})
                }
                stocks_loaded.append(stock_info)
            data_dict['data_statistics']['stocks_loaded'] = stocks_loaded
            
            # 日期范围
            cursor.execute("""
                SELECT MIN(date), MAX(date)
                FROM hk_hist_monthly_moneyflow
                WHERE date IS NOT NULL AND date != ''
            """)
            min_date, max_date = cursor.fetchone()
            data_dict['data_statistics']['date_range'] = {
                'earliest': min_date if min_date else None,
                'latest': max_date if max_date else None
            }
            
        except Exception as e:
            print(f"   ⚠️ 获取统计信息失败: {e}")
    
    # 添加业务规则
    data_dict['data_dictionary']['business_rules'] = [
        {
            'rule': '每月一条记录',
            'description': '数据按月汇总，每个股票每月只有一条记录'
        },
        {
            'rule': '价格变化百分比处理',
            'description': 'price_chg_pct 字段数值已乘以100'
        },
        {
            'rule': '资金流数据精度',
            'description': '资金流数据保留4位小数'
        },
        {
            'rule': '索引优化',
            'description': '使用复合索引 (stock_code, date) 优化查询性能'
        },
        {
            'rule': '列名规范',
            'description': '所有列名已转换为小写，特殊字符替换为下划线'
        }
    ]
    
    # 添加关系说明
    data_dict['data_dictionary']['relationships'] = [
        {
            'type': '外键关联',
            'table': 'hk_hist_daily_kline',
            'field': 'date',
            'description': '可通过日期字段与日交易数据关联（日期为每月最后一天）'
        },
        {
            'type': '外键关联',
            'table': 'macro_data_hist',
            'field': 'date',
            'description': '可通过日期字段与宏观数据关联'
        }
    ]
    
    # 保存数据字典
    try:
        with open(dict_path, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 数据字典已更新: {dict_path}")
        print(f"[INFO] 数据字典大小: {len(json.dumps(data_dict))} 字节")
        
        # 显示数据字典摘要
        print("\n数据字典摘要:")
        print(f"   - 表名: {data_dict['metadata']['table_name']}")
        print(f"   - 字段数: {len(data_dict['data_dictionary']['column_definitions'])}")
        print(f"   - 股票数: {len(data_dict['data_statistics']['stocks_loaded'])}")
        print(f"   - 总记录数: {data_dict['data_statistics']['total_records']}")
        print(f"   - 数据范围: {data_dict['data_statistics']['date_range']['earliest']} 至 {data_dict['data_statistics']['date_range']['latest']}")
        print(f"   - 索引: {[idx['name'] for idx in data_dict['table_schema']['indexes']]}")
        print(f"   - 列名规则: {data_dict['metadata']['column_naming']}")
        
    except Exception as e:
        print(f"[ERROR] 保存数据字典失败: {e}")
        import traceback
        traceback.print_exc()

# =====================================================
# 6. 主函数
# =====================================================

def main():
    print("\n" + "="*60)
    print("导入月资金流数据到 SQLite 数据库")
    print("所有列名将转换为小写")
    print("="*60 + "\n")
    
    # 获取所有CSV文件
    csv_files = list(DATA_DIR.glob("*_monthly_moneyflow.csv"))
    
    if not csv_files:
        print(f"[ERROR] 在 {DATA_DIR} 中未找到 *_monthly_moneyflow.csv 文件")
        print(f"[INFO] 请确认数据文件路径是否正确")
        return
    
    print(f"[INFO] 找到 {len(csv_files)} 个CSV文件:")
    for f in csv_files:
        print(f"   - {f.name}")
    
    # 连接数据库
    conn = get_db_connection()
    
    try:
        # ========== 修复：检查并处理表 ==========
        if table_exists(conn, 'hk_hist_monthly_moneyflow'):
            print(f"\n[WARN] 表 hk_hist_monthly_moneyflow 已存在")
            existing_count = conn.execute("SELECT COUNT(*) FROM hk_hist_monthly_moneyflow").fetchone()[0]
            if existing_count > 0:
                print(f"   ⚠️ 表中已有 {existing_count} 条记录")
            
            # 询问用户是否要删除表重新导入
            response = input("\n是否要删除现有表并重新导入？(y/n，输入n将追加数据): ").strip().lower()
            if response == 'y':
                # 删除表
                drop_table(conn, 'hk_hist_monthly_moneyflow')
                print("[INFO] 已删除旧表，将创建新表（所有列名小写）")
                # 创建新表
                print("[INFO] 创建新表...")
                if not create_table_if_not_exists(conn):
                    print("[ERROR] 创建表失败")
                    return
            else:
                print("[INFO] 将追加数据到现有表")
                # 确保表存在且结构正确
                if not create_table_if_not_exists(conn):
                    print("[ERROR] 表验证失败")
                    return
        else:
            # 创建新表
            print("[INFO] 创建新表（所有列名小写）...")
            if not create_table_if_not_exists(conn):
                print("[ERROR] 创建表失败")
                return
        
        # 处理每个CSV文件
        total_records = 0
        processed_files = 0
        skipped_files = []
        
        print("\n开始导入数据...")
        print("-" * 60)
        
        for csv_file in csv_files:
            # 从文件名解析股票代码
            filename = csv_file.stem
            parts = filename.split('_')
            code = parts[0] if parts else filename
            
            # 验证代码格式
            if not re.match(r'^\d{5}$', code):
                print(f"\n[WARN] 无法从文件名解析股票代码: {csv_file.name}")
                numbers = re.findall(r'\d+', filename)
                if numbers:
                    code = numbers[0]
                    if len(code) < 5:
                        code = code.zfill(5)
                    print(f"   使用提取的代码: {code}")
                else:
                    print(f"   ⚠️ 跳过此文件")
                    skipped_files.append(csv_file.name)
                    continue
            
            # 获取股票信息
            stock_info = STOCK_MAP.get(code, {})
            if not stock_info:
                print(f"\n[WARN] 股票 {code} 不在配置文件中")
                stock_name = f"股票_{code}"
                print(f"   使用默认名称: {stock_name}")
            else:
                stock_name = stock_info.get('name', f"股票_{code}")
            
            print(f"\n📊 处理: {csv_file.name}")
            print(f"   股票代码: {code}")
            print(f"   股票名称: {stock_name}")
            if stock_info:
                print(f"   行业: {stock_info.get('sector', 'N/A')}")
                print(f"   市场: {stock_info.get('market', 'N/A')}")
            
            # 导入数据
            count = import_csv_to_db(csv_file, conn, code, stock_name)
            if count > 0:
                total_records += count
                processed_files += 1
            else:
                skipped_files.append(csv_file.name)
            
            conn.commit()
        
        # 显示结果
        print("\n" + "="*60)
        print("导入完成!")
        print("="*60)
        print(f"✅ 成功处理 {processed_files}/{len(csv_files)} 个文件")
        if skipped_files:
            print(f"⚠️ 跳过的文件: {', '.join(skipped_files)}")
        print(f"📊 共导入 {total_records} 条记录")
        
        # 显示表信息
        if table_exists(conn, 'hk_hist_monthly_moneyflow'):
            count = conn.execute("SELECT COUNT(*) FROM hk_hist_monthly_moneyflow").fetchone()[0]
            print(f"\n📋 表 hk_hist_monthly_moneyflow 当前共有 {count} 条记录")
            
            # 显示表结构
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(hk_hist_monthly_moneyflow)")
            columns = cursor.fetchall()
            print(f"📋 表结构（所有列名均为小写）:")
            for i, col in enumerate(columns, 1):
                print(f"   {i}. {col[1]} ({col[2]}) {'NOT NULL' if col[3] else ''}")
            
            # 显示索引
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='hk_hist_monthly_moneyflow'")
            indexes = cursor.fetchall()
            if indexes:
                print(f"\n📋 索引:")
                for idx_name, idx_sql in indexes:
                    print(f"   - {idx_name}")
            
            # 显示股票统计
            stocks = conn.execute(
                "SELECT DISTINCT stock_code, stock_name FROM hk_hist_monthly_moneyflow ORDER BY stock_code"
            ).fetchall()
            print(f"\n📈 包含 {len(stocks)} 只股票的数据:")
            for code, name in stocks:
                cnt = conn.execute(
                    f"SELECT COUNT(*) FROM hk_hist_monthly_moneyflow WHERE stock_code='{code}'"
                ).fetchone()[0]
                # 检查是否在配置文件中
                in_config = "✓" if code in STOCK_MAP else "⚠️"
                print(f"   {in_config} {code} {name}: {cnt} 条记录")
        
        # 创建数据字典
        create_data_dictionary(conn)
        
    except Exception as e:
        print(f"\n[ERROR] 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    main()