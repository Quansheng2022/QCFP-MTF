#!/usr/bin/env python
# coding: utf-8

"""
Import_Daily_Moneyflow.py
将日资金流数据CSV文件导入SQLite数据库
从CSV文件解析股票代码，匹配股票名称，创建hk_hist_daily_moneyflow表

脚本位置: TA_Workflow2/Code_utl/Import_Daily_Moneyflow.py
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
        env_dir = os.environ.get('PROJECT_ROOT')
        if env_dir and Path(env_dir).exists():
            return Path(env_dir)

        script_path = Path(__file__).resolve()
        project_dir = script_path.parent.parent
        
        if (project_dir / 'Config').exists():
            return project_dir
        
        if script_path.parent.name == 'Code_utl':
            return script_path.parent.parent
        
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

project_dir = get_project_dir()
print(f"[INFO] 项目目录: {project_dir}")

# 添加必要路径
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))
core_dir = project_dir / 'Core'
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))
utl_dir = project_dir / 'Core' / 'Utl'
if str(utl_dir) not in sys.path:
    sys.path.insert(0, str(utl_dir))

# 导入股票列表加载工具
try:
    from stock_list_loader import load_stock_list, get_stock_name_map
    print("[INFO] 成功导入 stock_list_loader")
    STOCK_LIST = load_stock_list(project_dir / 'Config')
    STOCK_MAP = {item['code']: item for item in STOCK_LIST}
    print(f"[INFO] 从配置文件加载了 {len(STOCK_LIST)} 只股票")
except ImportError as e:
    print(f"[ERROR] 无法导入 stock_list_loader: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] 加载股票列表失败: {e}")
    sys.exit(1)

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

def load_config(config_path, project_dir):
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
    
    sqlite_rel = config.get('sqlite_dir', 'SQLiteDB')
    config['full_sqlite_dir'] = os.path.join(str(project_dir), sqlite_rel)
    
    db_name = config.get('db_name', 'HK_Stock.db')
    config['full_db_path'] = os.path.join(config['full_sqlite_dir'], db_name)
    
    for path_key in ['full_data_dir', 'full_sqlite_dir']:
        path = config.get(path_key)
        if path and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
    
    return config

CONFIG = load_config(str(config_path), str(project_dir))
setup_windows_encoding()

DATA_DIR = Path(CONFIG.get('full_data_dir'))
DB_DIR = Path(CONFIG.get('full_sqlite_dir'))
DB_PATH = Path(CONFIG.get('full_db_path'))

print(f"[INFO] 数据目录: {DATA_DIR}")
print(f"[INFO] 数据库目录: {DB_DIR}")
print(f"[INFO] 数据库路径: {DB_PATH}")

print(f"\n[INFO] 股票列表摘要:")
print(f"  总股票数: {len(STOCK_LIST)}")
if STOCK_LIST:
    print(f"  股票代码范围: {STOCK_LIST[0]['code']} ~ {STOCK_LIST[-1]['code']}")
    sectors = set(s.get('sector', 'N/A') for s in STOCK_LIST)
    print(f"  涉及行业: {', '.join(sectors)}")
print()

# =====================================================
# 3. 列名转换工具函数
# =====================================================

def clean_column_name(col_name):
    """
    清理列名并转换为小写
    1. 去除首尾空格
    2. 替换空格为下划线
    3. 替换/为下划线
    4. 删除括号
    5. 将%替换为pct
    6. 转换为小写
    """
    return (col_name.strip()
            .replace(' ', '_')
            .replace('/', '_')
            .replace('(', '')
            .replace(')', '')
            .replace('%', 'pct')
            .lower())

def clean_dataframe_columns(df):
    """
    清理DataFrame的所有列名并转换为小写
    """
    df.columns = [clean_column_name(col) for col in df.columns]
    return df

# =====================================================
# 4. 数据库操作函数
# =====================================================

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.text_factory = str
    return conn

def table_exists(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    return cursor.fetchone() is not None

def drop_table(conn, table_name):
    if table_exists(conn, table_name):
        conn.execute(f"DROP TABLE {table_name}")
        print(f"[INFO] 已删除表 {table_name}")
        return True
    return False

def create_table(conn):
    """
    创建 hk_hist_daily_moneyflow 表
    将 stock_code 和 stock_name 放在最前面
    创建索引 (stock_code, date)
    """
    csv_files = list(DATA_DIR.glob("*_daily_moneyflow.csv"))
    if not csv_files:
        print(f"[ERROR] 未找到任何 *_daily_moneyflow.csv 文件")
        return False
    
    sample_file = csv_files[0]
    try:
        df_sample = pd.read_csv(sample_file)
        # ---- 修改点：清理列名并转换为小写 ----
        df_sample = clean_dataframe_columns(df_sample)
        
        # 构建列定义：stock_code, stock_name, 其他列（date 作为第三个字段）
        columns = [
            'stock_code TEXT NOT NULL',
            'stock_name TEXT NOT NULL',
            'date TEXT NOT NULL'
        ]
        
        # 添加其他列（跳过date相关列）
        for col in df_sample.columns:
            col_clean = clean_column_name(col)
            col_lower = col.lower()
            if 'date' in col_lower:
                continue  # date 已经手动添加
            
            # 根据列名和数据类型推断SQLite类型
            if any(key in col_lower for key in ['open', 'high', 'low', 'close', 'adj', 'price']):
                col_type = 'REAL'
            elif any(key in col_lower for key in ['volume', 'amount', 'turnover', 'money', 'flow']):
                col_type = 'REAL'
            elif 'change' in col_lower or 'amplitude' in col_lower:
                col_type = 'REAL'
            else:
                try:
                    if pd.api.types.is_integer_dtype(df_sample[col]):
                        col_type = 'INTEGER'
                    elif pd.api.types.is_float_dtype(df_sample[col]):
                        col_type = 'REAL'
                    else:
                        col_type = 'TEXT'
                except:
                    col_type = 'TEXT'
            columns.append(f'"{col_clean}" {col_type}')
        
        create_sql = f"""
        CREATE TABLE hk_hist_daily_moneyflow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(columns)}
        )
        """
        conn.execute(create_sql)
        print(f"[INFO] 表 hk_hist_daily_moneyflow 已创建")
        
        # 创建索引 (stock_code, date)
        try:
            conn.execute("""
                CREATE INDEX idx_stock_code_date 
                ON hk_hist_daily_moneyflow (stock_code, date)
            """)
            print(f"[INFO] 已创建索引 idx_stock_code_date")
        except Exception as e:
            print(f"[WARN] 创建索引失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建表失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def import_csv_to_db(csv_path, conn, stock_code, stock_name):
    """
    将CSV文件导入数据库，确保字段顺序与表结构匹配
    特殊处理：对 price_chgpct 列的值乘以 100 后存储
    """
    try:
        df = pd.read_csv(csv_path)
        
        # ---- 清理列名并转换为小写 ----
        df = clean_dataframe_columns(df)
        
        # ---- 特殊处理：price_chgpct 列乘以 100 ----
        if 'price_chgpct' in df.columns:
            df['price_chgpct'] = pd.to_numeric(df['price_chgpct'], errors='coerce') * 100
            print(f"   [INFO] price_chgpct 列已乘以 100")
        
        # 查找日期列（小写）
        date_col = None
        for col in df.columns:
            if 'date' in col.lower():
                date_col = col
                break
        
        if date_col is None:
            print(f"   ⚠️ 未找到日期列")
            return 0
        
        other_cols = [col for col in df.columns if col != date_col]
        
        # 构建新DataFrame，顺序：stock_code, stock_name, date, 其他列
        df_new = pd.DataFrame()
        df_new['stock_code'] = str(stock_code).strip()
        df_new['stock_name'] = str(stock_name).strip()
        df_new['date'] = pd.to_datetime(df[date_col]).dt.strftime('%Y-%m-%d')
        
        for col in other_cols:
            df_new[col] = df[col]
        
        # 数值列四舍五入
        for col in df_new.select_dtypes(include=['float64', 'float32']).columns:
            if col not in ['stock_code', 'stock_name']:
                df_new[col] = df_new[col].round(4)
        
        # 处理空值
        if df_new['stock_code'].isna().any() or df_new['stock_code'].eq('').any():
            df_new['stock_code'] = df_new['stock_code'].fillna(stock_code).replace('', stock_code)
        if df_new['stock_name'].isna().any() or df_new['stock_name'].eq('').any():
            df_new['stock_name'] = df_new['stock_name'].fillna(stock_name).replace('', stock_name)
        
        df_new['stock_code'] = df_new['stock_code'].astype(str)
        df_new['stock_name'] = df_new['stock_name'].astype(str)
        df_new['date'] = df_new['date'].astype(str)
        
        # 导入数据
        df_new.to_sql('hk_hist_daily_moneyflow', conn, if_exists='append', index=False)
        
        print(f"   ✅ 已导入 {len(df_new)} 条记录")
        return len(df_new)
        
    except Exception as e:
        print(f"   ❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return 0

# =====================================================
# 5. 创建数据字典（完整JSON格式）
# =====================================================

def create_data_dictionary(conn):
    """
    创建完整的数据字典 hk_hist_daily_moneyflow_dictionary.json
    包含表结构、字段说明、数据类型、约束、统计信息等
    """
    print("\n" + "-"*60)
    print("创建数据字典...")
    
    csv_files = list(DATA_DIR.glob("*_daily_moneyflow.csv"))
    if not csv_files:
        print(f"[WARN] 未找到CSV文件，无法创建数据字典")
        return
    
    all_columns = set()
    sample_df = None
    file_info = []
    
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            # ---- 修改点：清理列名并转换为小写 ----
            df = clean_dataframe_columns(df)
            
            filename = csv_file.stem
            code = filename.split('_')[0] if filename.split('_') else filename
            
            date_col = None
            for col in df.columns:
                if 'date' in col.lower():
                    date_col = col
                    break
            
            file_info.append({
                'filename': csv_file.name,
                'code': code,
                'rows': len(df),
                'columns': list(df.columns),
                'date_range': {
                    'start': df[date_col].iloc[0] if date_col else None,
                    'end': df[date_col].iloc[-1] if date_col else None
                }
            })
            
            all_columns.update(df.columns)
            if sample_df is None:
                sample_df = df
        except Exception as e:
            print(f"   ⚠️ 读取 {csv_file.name} 失败: {e}")
    
    data_dict = {
        'metadata': {
            'table_name': 'hk_hist_daily_moneyflow',
            'description': '港股日资金流历史数据表',
            'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0',
            'database': str(DB_PATH.name),
            'data_source': 'CSV files from Data directory',
            'total_files': len(csv_files),
            'total_stocks': len(STOCK_LIST),
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
                    'description': '用于快速查询特定股票的资金流数据'
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
            'query_all': "SELECT * FROM hk_hist_daily_moneyflow LIMIT 10;",
            'query_by_stock': "SELECT * FROM hk_hist_daily_moneyflow WHERE stock_code = '01951';",
            'query_date_range': "SELECT * FROM hk_hist_daily_moneyflow WHERE date BETWEEN '2024-01-01' AND '2024-12-31';",
            'query_moneyflow': "SELECT date, stock_code, stock_name, net_inflow FROM hk_hist_daily_moneyflow;",
            'query_with_index': "SELECT * FROM hk_hist_daily_moneyflow WHERE stock_code = '01951' AND date = '2024-01-01';"
        },
        'data_dictionary': {
            'column_definitions': [],
            'relationships': [],
            'business_rules': []
        }
    }
    
    # 基础字段
    base_fields = [
        {'name': 'id', 'type': 'INTEGER', 'description': '自增主键', 'constraint': 'PRIMARY KEY AUTOINCREMENT', 'example': '1', 'is_key': True, 'is_required': True},
        {'name': 'stock_code', 'type': 'TEXT', 'description': '股票代码（5位数字）', 'constraint': 'NOT NULL', 'example': '01951', 'is_key': True, 'is_required': True},
        {'name': 'stock_name', 'type': 'TEXT', 'description': '股票名称', 'constraint': 'NOT NULL', 'example': '锦鑫生殖', 'is_key': True, 'is_required': True},
        {'name': 'date', 'type': 'TEXT', 'description': '交易日期（YYYY-MM-DD格式）', 'constraint': 'NOT NULL', 'example': '2024-01-01', 'is_key': True, 'is_required': True},
    ]
    
    # 从CSV提取其他字段（列名已经是小写）
    if sample_df is not None:
        for col in sample_df.columns:
            col_clean = clean_column_name(col)
            col_lower = col.lower()
            if 'date' in col_lower:
                continue
            
            if 'open' in col_lower:
                field_type, desc = 'REAL', '开盘价'
            elif 'high' in col_lower:
                field_type, desc = 'REAL', '最高价'
            elif 'low' in col_lower:
                field_type, desc = 'REAL', '最低价'
            elif 'close' in col_lower:
                field_type, desc = 'REAL', '收盘价'
            elif 'volume' in col_lower:
                field_type, desc = 'REAL', '成交量'
            elif 'amount' in col_lower:
                field_type, desc = 'REAL', '成交金额'
            elif 'net' in col_lower and ('inflow' in col_lower or 'outflow' in col_lower):
                field_type, desc = 'REAL', '资金净流入'
            elif 'flow' in col_lower:
                field_type, desc = 'REAL', '资金流'
            elif 'turnover' in col_lower:
                field_type, desc = 'REAL', '换手率'
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
                desc = f'原始字段: {col}'
            
            null_count = sample_df[col].isnull().sum() if col in sample_df.columns else 0
            
            field_def = {
                'name': col_clean,
                'original_name': col,
                'type': field_type,
                'description': desc,
                'constraint': '',
                'null_count': int(null_count),
                'sample_value': str(sample_df[col].iloc[0]) if len(sample_df) > 0 and not pd.isna(sample_df[col].iloc[0]) else '',
                'example': '',
                'is_key': False,
                'is_required': False
            }
            data_dict['data_dictionary']['column_definitions'].append(field_def)
    
    # 添加基础字段到开头
    base_field_defs = []
    for field in base_fields:
        base_field_defs.append({
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
        })
    
    data_dict['data_dictionary']['column_definitions'] = base_field_defs + data_dict['data_dictionary']['column_definitions']
    
    # 更新table_schema的columns
    for field in data_dict['data_dictionary']['column_definitions']:
        data_dict['table_schema']['columns'].append({
            'name': field['name'],
            'type': field['type'],
            'description': field['description'],
            'is_key': field['is_key']
        })
    
    # 获取统计信息
    if table_exists(conn, 'hk_hist_daily_moneyflow'):
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM hk_hist_daily_moneyflow")
            total_records = cursor.fetchone()[0]
            data_dict['data_statistics']['total_records'] = total_records
            
            cursor.execute("""
                SELECT stock_code, stock_name, COUNT(*) as count
                FROM hk_hist_daily_moneyflow
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
            
            cursor.execute("""
                SELECT MIN(date), MAX(date)
                FROM hk_hist_daily_moneyflow
                WHERE date IS NOT NULL AND date != ''
            """)
            min_date, max_date = cursor.fetchone()
            data_dict['data_statistics']['date_range'] = {
                'earliest': min_date if min_date else None,
                'latest': max_date if max_date else None
            }
        except Exception as e:
            print(f"   ⚠️ 获取统计信息失败: {e}")
    
    data_dict['data_dictionary']['business_rules'] = [
        {'rule': '每个股票每天只有一条记录', 'description': '数据按日期去重'},
        {'rule': '价格和资金数据精度', 'description': '数值保留4位小数'},
        {'rule': '索引优化', 'description': '使用索引 (stock_code, date) 优化查询'}
    ]
    
    data_dict['data_dictionary']['relationships'] = [
        {'type': '关联', 'table': 'hk_hist_daily_kline', 'field': 'date', 'description': '可通过日期与日K线数据关联'},
        {'type': '关联', 'table': 'macro_data_hist', 'field': 'date', 'description': '可通过日期与宏观数据关联'}
    ]
    
    dict_path = project_dir / 'Config' / 'hk_hist_daily_moneyflow_dictionary.json'
    try:
        with open(dict_path, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 数据字典已创建: {dict_path}")
        print(f"[INFO] 数据字典大小: {len(json.dumps(data_dict))} 字节")
        
        print("\n数据字典摘要:")
        print(f"   - 表名: {data_dict['metadata']['table_name']}")
        print(f"   - 字段数: {len(data_dict['data_dictionary']['column_definitions'])}")
        print(f"   - 股票数: {len(data_dict['data_statistics']['stocks_loaded'])}")
        print(f"   - 总记录数: {data_dict['data_statistics']['total_records']}")
        print(f"   - 数据范围: {data_dict['data_statistics']['date_range']['earliest']} 至 {data_dict['data_statistics']['date_range']['latest']}")
        print(f"   - 索引: {[idx['name'] for idx in data_dict['table_schema']['indexes']]}")
        
    except Exception as e:
        print(f"[ERROR] 保存数据字典失败: {e}")

# =====================================================
# 6. 主函数
# =====================================================

def main():
    print("\n" + "="*60)
    print("导入日资金流数据到 SQLite 数据库")
    print("="*60 + "\n")
    
    csv_files = list(DATA_DIR.glob("*_daily_moneyflow.csv"))
    if not csv_files:
        print(f"[ERROR] 在 {DATA_DIR} 中未找到 *_daily_moneyflow.csv 文件")
        print(f"[INFO] 请确认数据文件路径是否正确")
        return
    
    print(f"[INFO] 找到 {len(csv_files)} 个CSV文件:")
    for f in csv_files:
        print(f"   - {f.name}")
    
    conn = get_db_connection()
    
    try:
        # 若表存在则删除（需求：如果表已经存在，则先删除，再导入）
        if table_exists(conn, 'hk_hist_daily_moneyflow'):
            print("\n[INFO] 发现已存在的表 hk_hist_daily_moneyflow，正在删除...")
            drop_table(conn, 'hk_hist_daily_moneyflow')
        
        # 创建新表
        if not create_table(conn):
            print("[ERROR] 创建表失败，程序退出")
            return
        
        # 处理每个CSV文件
        total_records = 0
        processed_files = 0
        skipped_files = []
        
        print("\n开始导入数据...")
        print("-" * 60)
        
        for csv_file in csv_files:
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
            
            count = import_csv_to_db(csv_file, conn, code, stock_name)
            if count > 0:
                total_records += count
                processed_files += 1
            else:
                skipped_files.append(csv_file.name)
            
            conn.commit()
        
        # 结果摘要
        print("\n" + "="*60)
        print("导入完成!")
        print("="*60)
        print(f"✅ 成功处理 {processed_files}/{len(csv_files)} 个文件")
        if skipped_files:
            print(f"⚠️ 跳过的文件: {', '.join(skipped_files)}")
        print(f"📊 共导入 {total_records} 条记录")
        
        # 显示表信息
        if table_exists(conn, 'hk_hist_daily_moneyflow'):
            count = conn.execute("SELECT COUNT(*) FROM hk_hist_daily_moneyflow").fetchone()[0]
            print(f"\n📋 表 hk_hist_daily_moneyflow 当前共有 {count} 条记录")
            
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(hk_hist_daily_moneyflow)")
            columns = cursor.fetchall()
            print(f"📋 表结构（字段顺序）:")
            for i, col in enumerate(columns, 1):
                print(f"   {i}. {col[1]} ({col[2]}) {'NOT NULL' if col[3] else ''}")
            
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='hk_hist_daily_moneyflow'")
            indexes = cursor.fetchall()
            if indexes:
                print(f"\n📋 索引:")
                for idx_name, idx_sql in indexes:
                    print(f"   - {idx_name}")
            
            stocks = conn.execute(
                "SELECT DISTINCT stock_code, stock_name FROM hk_hist_daily_moneyflow ORDER BY stock_code"
            ).fetchall()
            print(f"\n📈 包含 {len(stocks)} 只股票的数据:")
            for code, name in stocks:
                cnt = conn.execute(
                    f"SELECT COUNT(*) FROM hk_hist_daily_moneyflow WHERE stock_code='{code}'"
                ).fetchone()[0]
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