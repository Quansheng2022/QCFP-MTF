#!/usr/bin/env python
# coding: utf-8

"""
Import_Weekly_Kline_Data.py
将周K线分析数据CSV文件导入SQLite数据库
从CSV文件解析股票代码，匹配股票名称，创建hk_hist_weekly_kline表

脚本位置: TA_Workflow2/Code_utl/Import_Weekly_Kline_Data.py
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
# 3. 数据库操作函数
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

def clean_column_name(col_name):
    """
    清理列名
    将包含%的列名改为 ...Pct
    移除特殊字符，替换空格为下划线
    """
    # 去除前后空格
    col_name = col_name.strip()
    
    # 将 % 替换为 Pct（放在最后处理，因为可能与其他字符组合）
    col_name = col_name.replace('%', 'Pct')
    
    # 替换其他特殊字符
    col_name = col_name.replace(' ', '_')
    col_name = col_name.replace('/', '_')
    col_name = col_name.replace('(', '')
    col_name = col_name.replace(')', '')
    col_name = col_name.replace('-', '_')
    col_name = col_name.replace('.', '_')
    
    # 移除连续的多个下划线
    while '__' in col_name:
        col_name = col_name.replace('__', '_')
    
    return col_name

def create_table_if_not_exists(conn):
    """
    创建 hk_hist_weekly_kline 表（如果不存在）
    将 stock_code 和 stock_name 放在最前面
    创建复合索引 (stock_code, date)
    """
    # 先读取一个CSV文件样例来获取列结构
    csv_files = list(DATA_DIR.glob("*_weekly_historical_data.csv"))
    if not csv_files:
        print(f"[ERROR] 未找到任何 *_weekly_historical_data.csv 文件")
        return False
    
    # 读取第一个CSV文件获取列结构
    sample_file = csv_files[0]
    try:
        df_sample = pd.read_csv(sample_file)
        
        # 构建CREATE TABLE语句 - 将 stock_code 和 stock_name 放在最前面
        columns = [
            'stock_code TEXT NOT NULL',
            'stock_name TEXT NOT NULL',
            'date TEXT NOT NULL'
        ]
        
        # 添加其他列
        for col in df_sample.columns:
            col_clean = clean_column_name(col)
            
            # 如果是date列，跳过（我们已经添加了date字段）
            if col_clean.lower() == 'date':
                continue
            
            # 如果列名包含 'date' 但被清理后变成了 'date'，也跳过
            if col_clean.lower() == 'date':
                continue
            
            # 根据列名和数据类型选择合适的SQLite类型
            col_lower = col.lower()
            
            # 价格相关字段
            if any(keyword in col_lower for keyword in ['open', 'high', 'low', 'close', 'adj_close', 'adjclose']):
                col_type = 'REAL'
            # 成交量相关字段
            elif any(keyword in col_lower for keyword in ['volume', 'amount', 'turnover', 'value']):
                col_type = 'REAL'
            # 涨跌幅相关字段（包含Pct或%）
            elif any(keyword in col_lower for keyword in ['pct', '%', 'change_percent', 'amplitude']):
                col_type = 'REAL'
            # 其他数值字段
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
            
            columns.append(f'"{col_clean}" {col_type}')
        
        # 创建表
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS hk_hist_weekly_kline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(columns)}
        )
        """
        
        conn.execute(create_sql)
        print(f"[INFO] 表 hk_hist_weekly_kline 已创建或已存在")
        
        # 创建复合索引 (stock_code, date)
        try:
            # 检查索引是否已存在
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name='idx_weekly_stock_code_date'
            """)
            if not cursor.fetchone():
                create_index_sql = """
                CREATE INDEX idx_weekly_stock_code_date 
                ON hk_hist_weekly_kline (stock_code, date)
                """
                conn.execute(create_index_sql)
                print(f"[INFO] 已创建复合索引 idx_weekly_stock_code_date")
            else:
                print(f"[INFO] 复合索引 idx_weekly_stock_code_date 已存在")
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
        if table_exists(conn, 'hk_hist_weekly_kline'):
            conn.execute("DROP TABLE hk_hist_weekly_kline")
            print("[INFO] 已删除旧表 hk_hist_weekly_kline")
        
        # 创建新表
        if create_table_if_not_exists(conn):
            print("[INFO] 已重新创建表 hk_hist_weekly_kline")
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
    确保字段顺序与表结构匹配
    """
    try:
        # 读取CSV文件
        df = pd.read_csv(csv_path)
        
        # 清理列名 - 将包含%的列名改为...Pct
        df.columns = [clean_column_name(col) for col in df.columns]
        
        # 确保有date列，并提取date数据
        date_col = None
        for col in df.columns:
            if 'date' in col.lower():
                date_col = col
                break
        
        if date_col is None:
            print(f"   ⚠️ 未找到日期列")
            return 0
        
        # 获取所有列（除了date列）
        other_cols = [col for col in df.columns if col != date_col]
        
        # 创建新的DataFrame，按正确顺序排列
        df_new = pd.DataFrame()
        
        # 确保 stock_code 和 stock_name 不是空值，且为字符串类型
        df_new['stock_code'] = str(stock_code).strip()
        df_new['stock_name'] = str(stock_name).strip()
        df_new['date'] = pd.to_datetime(df[date_col]).dt.strftime('%Y-%m-%d')
        
        # 添加其他列
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
        
        # 导入数据
        df_new.to_sql('hk_hist_weekly_kline', conn, if_exists='append', index=False)
        
        print(f"   ✅ 已导入 {len(df_new)} 条记录")
        return len(df_new)
        
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
# 4. 创建数据字典（完整JSON格式）
# =====================================================

def create_data_dictionary(conn):
    """
    创建完整的数据字典 hk_hist_weekly_kline.json
    如果数据字典文件已经存在，则添加新的数据字典
    包含表结构、字段说明、数据类型、约束、统计信息等
    """
    print("\n" + "-"*60)
    print("创建数据字典...")
    
    # 数据字典路径
    dict_path = project_dir / 'Config' / 'hk_hist_weekly_kline.json'
    
    # 如果文件已存在，加载现有数据
    existing_dict = {}
    if dict_path.exists():
        try:
            with open(dict_path, 'r', encoding='utf-8') as f:
                existing_dict = json.load(f)
            print(f"[INFO] 已加载现有数据字典: {dict_path}")
        except Exception as e:
            print(f"[WARN] 读取现有数据字典失败: {e}")
            existing_dict = {}
    
    # 获取CSV文件列表
    csv_files = list(DATA_DIR.glob("*_weekly_historical_data.csv"))
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
                if 'date' in col.lower():
                    date_col = col
                    break
            
            # 清理列名
            cleaned_columns = [clean_column_name(col) for col in df.columns]
            
            file_info.append({
                'filename': csv_file.name,
                'code': code,
                'rows': len(df),
                'columns': list(df.columns),
                'cleaned_columns': cleaned_columns,
                'date_range': {
                    'start': df[date_col].iloc[0] if date_col and len(df) > 0 else None,
                    'end': df[date_col].iloc[-1] if date_col and len(df) > 0 else None
                }
            })
            
            all_columns.update(df.columns)
            if sample_df is None:
                sample_df = df
        except Exception as e:
            print(f"   ⚠️ 读取 {csv_file.name} 失败: {e}")
    
    # 构建数据字典
    data_dict = {
        'metadata': {
            'table_name': 'hk_hist_weekly_kline',
            'description': '港股周K线历史数据表',
            'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0',
            'database': str(DB_PATH.name),
            'data_source': 'CSV files from Data directory',
            'total_files': len(csv_files),
            'total_stocks': len(STOCK_LIST),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'table_schema': {
            'primary_key': 'id',
            'columns_order': ['stock_code', 'stock_name', 'date', '...'],
            'columns': [],
            'indexes': [
                {
                    'name': 'idx_weekly_stock_code_date',
                    'fields': ['stock_code', 'date'],
                    'type': '复合索引',
                    'description': '用于快速查询特定股票的周K线数据'
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
            'query_all': "SELECT * FROM hk_hist_weekly_kline LIMIT 10;",
            'query_by_stock': "SELECT * FROM hk_hist_weekly_kline WHERE stock_code = '01951';",
            'query_date_range': "SELECT * FROM hk_hist_weekly_kline WHERE date BETWEEN '2024-01-01' AND '2024-12-31';",
            'query_closing_prices': "SELECT date, stock_code, stock_name, close FROM hk_hist_weekly_kline;",
            'query_with_index': "SELECT * FROM hk_hist_weekly_kline WHERE stock_code = '01951' AND date = '2024-01-01';"
        },
        'data_dictionary': {
            'column_definitions': [],
            'relationships': [],
            'business_rules': []
        }
    }
    
    # 如果已有数据字典，继承部分信息
    if existing_dict:
        # 保留已有的metadata版本信息
        if 'metadata' in existing_dict:
            data_dict['metadata']['version'] = existing_dict.get('metadata', {}).get('version', '1.0')
            data_dict['metadata']['created_date'] = existing_dict.get('metadata', {}).get('created_date', 
                                                                                     data_dict['metadata']['created_date'])
        
        # 保留已有的业务规则
        if 'data_dictionary' in existing_dict and 'business_rules' in existing_dict['data_dictionary']:
            data_dict['data_dictionary']['business_rules'] = existing_dict['data_dictionary']['business_rules']
        
        # 保留已有的关系说明
        if 'data_dictionary' in existing_dict and 'relationships' in existing_dict['data_dictionary']:
            data_dict['data_dictionary']['relationships'] = existing_dict['data_dictionary']['relationships']
    
    # 添加字段定义（按照表的实际顺序）
    # 基础字段（放在最前面）
    base_fields = [
        {'name': 'id', 'type': 'INTEGER', 'description': '自增主键', 'constraint': 'PRIMARY KEY AUTOINCREMENT', 'example': '1', 'is_key': True, 'is_required': True},
        {'name': 'stock_code', 'type': 'TEXT', 'description': '股票代码（5位数字）', 'constraint': 'NOT NULL', 'example': '01951', 'is_key': True, 'is_required': True},
        {'name': 'stock_name', 'type': 'TEXT', 'description': '股票名称', 'constraint': 'NOT NULL', 'example': '锦鑫生殖', 'is_key': True, 'is_required': True},
        {'name': 'date', 'type': 'TEXT', 'description': '交易日期（YYYY-MM-DD格式）', 'constraint': 'NOT NULL', 'example': '2024-01-01', 'is_key': True, 'is_required': True},
    ]
    
    # 从CSV文件提取其他字段
    if sample_df is not None:
        for col in sample_df.columns:
            col_clean = clean_column_name(col)
            
            # 如果是date列，跳过（已经添加）
            if col_clean.lower() == 'date':
                continue
            
            # 确定字段类型和描述
            col_lower = col.lower()
            
            # 识别字段含义（支持周K线特有的字段）
            if 'open' in col_lower:
                field_type = 'REAL'
                description = '周开盘价'
                constraint = ''
                example = '10.50'
            elif 'high' in col_lower:
                field_type = 'REAL'
                description = '周最高价'
                constraint = ''
                example = '11.00'
            elif 'low' in col_lower:
                field_type = 'REAL'
                description = '周最低价'
                constraint = ''
                example = '10.20'
            elif 'close' in col_lower and 'prev' not in col_lower and 'adj' not in col_lower:
                field_type = 'REAL'
                description = '周收盘价'
                constraint = ''
                example = '10.80'
            elif 'adj_close' in col_lower or 'adjclose' in col_lower:
                field_type = 'REAL'
                description = '调整后周收盘价（考虑分红、拆股等）'
                constraint = ''
                example = '10.75'
            elif 'prev_close' in col_lower:
                field_type = 'REAL'
                description = '上周收盘价'
                constraint = ''
                example = '10.55'
            elif 'volume' in col_lower:
                field_type = 'REAL'
                description = '周成交量（股数）'
                constraint = ''
                example = '1000000'
            elif 'amount' in col_lower:
                field_type = 'REAL'
                description = '周成交金额'
                constraint = ''
                example = '10000000'
            elif 'amplitude' in col_lower:
                field_type = 'REAL'
                description = '周振幅（%）'
                constraint = ''
                example = '3.5'
            elif 'change' in col_lower and 'pct' in col_clean.lower():
                field_type = 'REAL'
                description = '周涨跌幅（%）'
                constraint = ''
                example = '2.5'
            elif 'change' in col_lower and 'pct' not in col_clean.lower() and 'amount' not in col_lower:
                field_type = 'REAL'
                description = '周涨跌幅（%）'
                constraint = ''
                example = '2.5'
            elif 'change' in col_lower and 'amount' in col_lower:
                field_type = 'REAL'
                description = '周涨跌额'
                constraint = ''
                example = '0.25'
            elif 'turnover' in col_lower:
                field_type = 'REAL'
                description = '周换手率（%）'
                constraint = ''
                example = '1.5'
            elif 'week' in col_lower or 'weekly' in col_lower:
                field_type = 'TEXT'
                description = '周标识'
                constraint = ''
                example = '2024-W01'
            elif 'year' in col_lower:
                field_type = 'INTEGER'
                description = '年份'
                constraint = ''
                example = '2024'
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
                'name': col_clean,
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
    if table_exists(conn, 'hk_hist_weekly_kline'):
        try:
            cursor = conn.cursor()
            
            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM hk_hist_weekly_kline")
            total_records = cursor.fetchone()[0]
            data_dict['data_statistics']['total_records'] = total_records
            
            # 获取每个股票的记录数
            cursor.execute("""
                SELECT stock_code, stock_name, COUNT(*) as count
                FROM hk_hist_weekly_kline
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
                FROM hk_hist_weekly_kline
                WHERE date IS NOT NULL AND date != ''
            """)
            min_date, max_date = cursor.fetchone()
            data_dict['data_statistics']['date_range'] = {
                'earliest': min_date if min_date else None,
                'latest': max_date if max_date else None
            }
            
        except Exception as e:
            print(f"   ⚠️ 获取统计信息失败: {e}")
    
    # 添加周K线特有的业务规则（如果不存在）
    weekly_business_rules = [
        {
            'rule': '每个股票每周只有一条记录',
            'description': '数据按周去重，同一股票在同一周只有一条交易数据'
        },
        {
            'rule': '价格精度',
            'description': '价格数据保留4位小数'
        },
        {
            'rule': '数据完整性',
            'description': '所有周K线数据应包含完整的OHLC（开高低收）和成交量信息'
        },
        {
            'rule': '索引优化',
            'description': '使用复合索引 (stock_code, date) 优化查询性能'
        },
        {
            'rule': '周数据周期',
            'description': '周K线数据以自然周为周期，周五（或最后一个交易日）为周数据点'
        }
    ]
    
    # 如果已有业务规则，则合并
    if data_dict['data_dictionary']['business_rules']:
        # 如果已有业务规则，添加新的规则（去重）
        existing_rules = [rule['rule'] for rule in data_dict['data_dictionary']['business_rules']]
        for rule in weekly_business_rules:
            if rule['rule'] not in existing_rules:
                data_dict['data_dictionary']['business_rules'].append(rule)
    else:
        data_dict['data_dictionary']['business_rules'] = weekly_business_rules
    
    # 添加周K线关系说明（如果不存在）
    weekly_relationships = [
        {
            'type': '外键关联',
            'table': 'hk_hist_daily_kline',
            'field': 'date',
            'description': '可通过日期字段与日K线数据关联，周数据通常为周五数据'
        },
        {
            'type': '外键关联',
            'table': 'macro_data_hist',
            'field': 'date',
            'description': '可通过日期字段与宏观数据关联'
        }
    ]
    
    if data_dict['data_dictionary']['relationships']:
        existing_rels = [rel['table'] for rel in data_dict['data_dictionary']['relationships']]
        for rel in weekly_relationships:
            if rel['table'] not in existing_rels:
                data_dict['data_dictionary']['relationships'].append(rel)
    else:
        data_dict['data_dictionary']['relationships'] = weekly_relationships
    
    # 保存数据字典
    try:
        with open(dict_path, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 数据字典已创建/更新: {dict_path}")
        print(f"[INFO] 数据字典大小: {len(json.dumps(data_dict))} 字节")
        
        # 显示数据字典摘要
        print("\n数据字典摘要:")
        print(f"   - 表名: {data_dict['metadata']['table_name']}")
        print(f"   - 字段数: {len(data_dict['data_dictionary']['column_definitions'])}")
        print(f"   - 股票数: {len(data_dict['data_statistics']['stocks_loaded'])}")
        print(f"   - 总记录数: {data_dict['data_statistics']['total_records']}")
        print(f"   - 数据范围: {data_dict['data_statistics']['date_range']['earliest']} 至 {data_dict['data_statistics']['date_range']['latest']}")
        print(f"   - 索引: {[idx['name'] for idx in data_dict['table_schema']['indexes']]}")
        
    except Exception as e:
        print(f"[ERROR] 保存数据字典失败: {e}")
        import traceback
        traceback.print_exc()

# =====================================================
# 5. 主函数
# =====================================================

def main():
    print("\n" + "="*60)
    print("导入周K线分析数据到 SQLite 数据库")
    print("="*60 + "\n")
    
    # 获取所有CSV文件
    csv_files = list(DATA_DIR.glob("*_weekly_historical_data.csv"))
    
    if not csv_files:
        print(f"[ERROR] 在 {DATA_DIR} 中未找到 *_weekly_historical_data.csv 文件")
        print(f"[INFO] 请确认数据文件路径是否正确")
        return
    
    print(f"[INFO] 找到 {len(csv_files)} 个CSV文件:")
    for f in csv_files:
        print(f"   - {f.name}")
    
    # 连接数据库
    conn = get_db_connection()
    
    try:
        # 检查表是否存在
        if table_exists(conn, 'hk_hist_weekly_kline'):
            existing_count = conn.execute("SELECT COUNT(*) FROM hk_hist_weekly_kline").fetchone()[0]
            if existing_count > 0:
                print(f"\n[WARN] 表 hk_hist_weekly_kline 中已有 {existing_count} 条记录")
                print("选项:")
                print("  1. 清空现有数据并重新导入 (y)")
                print("  2. 保留现有数据，追加新数据 (n)")
                print("  3. 删除表并重新创建 (d) - 将创建新表结构（stock_code在前）")
                response = input("请选择 (y/n/d): ").strip().lower()
                
                if response == 'd':
                    if not recreate_table(conn):
                        print("[ERROR] 重新创建表失败")
                        return
                elif response == 'y' or response == 'yes':
                    clear_table(conn, 'hk_hist_weekly_kline')
                    print("[INFO] 已清空旧数据")
                else:
                    print("[INFO] 保留现有数据，将追加新数据")
            else:
                # 表存在但没有数据，检查表结构是否正确
                print("[INFO] 表存在但没有数据，检查表结构...")
                # 获取表结构
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(hk_hist_weekly_kline)")
                columns = cursor.fetchall()
                # 检查是否包含stock_code、stock_name、date字段
                col_names = [col[1] for col in columns]
                if 'stock_code' not in col_names or 'stock_name' not in col_names or 'date' not in col_names:
                    print("[WARN] 表结构不完整，重新创建表")
                    if not recreate_table(conn):
                        print("[ERROR] 重新创建表失败")
                        return
        else:
            # 表不存在，创建新表
            print("[INFO] 创建新表...")
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
        if table_exists(conn, 'hk_hist_weekly_kline'):
            count = conn.execute("SELECT COUNT(*) FROM hk_hist_weekly_kline").fetchone()[0]
            print(f"\n📋 表 hk_hist_weekly_kline 当前共有 {count} 条记录")
            
            # 显示表结构
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(hk_hist_weekly_kline)")
            columns = cursor.fetchall()
            print(f"📋 表结构（字段顺序）:")
            for i, col in enumerate(columns, 1):
                print(f"   {i}. {col[1]} ({col[2]}) {'NOT NULL' if col[3] else ''}")
            
            # 显示索引
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='hk_hist_weekly_kline'")
            indexes = cursor.fetchall()
            if indexes:
                print(f"\n📋 索引:")
                for idx_name, idx_sql in indexes:
                    print(f"   - {idx_name}")
            
            # 显示股票统计
            stocks = conn.execute(
                "SELECT DISTINCT stock_code, stock_name FROM hk_hist_weekly_kline ORDER BY stock_code"
            ).fetchall()
            print(f"\n📈 包含 {len(stocks)} 只股票的周K线数据:")
            for code, name in stocks:
                cnt = conn.execute(
                    f"SELECT COUNT(*) FROM hk_hist_weekly_kline WHERE stock_code='{code}'"
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