#!/usr/bin/env python
# coding: utf-8

"""
Import_Monthly_Moneyflow_Analysis.py
将月度资金流分析CSV文件导入SQLite数据库
从CSV文件解析股票代码，匹配股票名称，创建hk_monthly_moneyflow_analysis表
支持批量导入多个股票的月度资金流分析数据
所有列名统一转换为小写

脚本位置: TA_Workflow2/Code_utl/Import_Monthly_Moneyflow_Analysis.py
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

def create_table_if_not_exists(conn, csv_files):
    """
    根据CSV文件创建 hk_monthly_moneyflow_analysis 表（如果不存在）
    将 stock_code 和 stock_name 放在最前面
    所有列名转换为小写
    创建复合索引 (stock_code, date)
    """
    try:
        # 使用第一个CSV文件获取列结构
        if not csv_files:
            print("[ERROR] 没有CSV文件可供参考")
            return False
        
        df_sample = pd.read_csv(csv_files[0])
        
        # 构建CREATE TABLE语句 - 将 stock_code 和 stock_name 放在最前面
        columns = [
            'stock_code TEXT NOT NULL',
            'stock_name TEXT NOT NULL',
            'date TEXT NOT NULL'
        ]
        
        # 添加其他列，处理含有%的列名，全部转换为小写
        for col in df_sample.columns:
            col_clean = col.strip()
            
            # 如果列名包含%，改成 ...Pct
            if '%' in col_clean:
                col_clean = col_clean.replace('%', 'Pct')
            
            # 清理列名：替换空格和特殊字符
            col_clean = col_clean.replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
            
            # 转换为小写
            col_clean = col_clean.lower()
            
            # 如果是date列，跳过（我们已经添加了date字段）
            if 'date' in col.lower() or 'Date' in col.lower():
                continue
            
            # 根据列名和数据类型选择合适的SQLite类型
            col_lower = col.lower()
            if 'pct' in col_lower or 'percent' in col_lower or 'ratio' in col_lower:
                col_type = 'REAL'
            elif 'amount' in col_lower or 'volume' in col_lower or 'value' in col_lower:
                col_type = 'REAL'
            elif 'price' in col_lower or 'close' in col_lower or 'open' in col_lower:
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
            
            columns.append(f'"{col_clean}" {col_type}')
        
        # 创建表
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS hk_monthly_moneyflow_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(columns)}
        )
        """
        
        conn.execute(create_sql)
        print(f"[INFO] 表 hk_monthly_moneyflow_analysis 已创建或已存在")
        print(f"[INFO] 所有列名已转换为小写")
        
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
                ON hk_monthly_moneyflow_analysis (stock_code, date)
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
    
def recreate_table(conn, csv_files):
    """
    重新创建表（删除旧表并创建新表）
    """
    try:
        # 删除旧表
        if table_exists(conn, 'hk_monthly_moneyflow_analysis'):
            conn.execute("DROP TABLE hk_monthly_moneyflow_analysis")
            print("[INFO] 已删除旧表 hk_monthly_moneyflow_analysis")
        
        # 创建新表
        if create_table_if_not_exists(conn, csv_files):
            print("[INFO] 已重新创建表 hk_monthly_moneyflow_analysis")
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
    所有列名转换为小写
    """
    try:
        # 读取CSV文件
        df = pd.read_csv(csv_path)
        
        # 清理列名：处理含有%的列名，全部转换为小写
        df.columns = [col.strip() for col in df.columns]
        new_columns = []
        for col in df.columns:
            col_clean = col
            if '%' in col_clean:
                col_clean = col_clean.replace('%', 'Pct')
            col_clean = col_clean.replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
            # 转换为小写
            col_clean = col_clean.lower()
            new_columns.append(col_clean)
        df.columns = new_columns
        
        # 确保有date列
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
        df_new.to_sql('hk_monthly_moneyflow_analysis', conn, if_exists='append', index=False)
        
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
# 4. 创建数据字典
# =====================================================

def create_data_dictionary(conn, csv_files, processed_stocks):
    """
    创建数据字典 hk_monthly_moneyflow_Analysis_dictionary.json
    如果数据字典文件已经存在，则添加新的数据字典
    所有列名转换为小写
    """
    print("\n" + "-"*60)
    print("创建数据字典...")
    
    dict_path = project_dir / 'Config' / 'hk_monthly_moneyflow_Analysis_dictionary.json'
    
    # 加载现有数据字典（如果存在）
    existing_dict = {}
    if dict_path.exists():
        try:
            with open(dict_path, 'r', encoding='utf-8') as f:
                existing_dict = json.load(f)
            print(f"[INFO] 加载现有数据字典: {dict_path}")
        except Exception as e:
            print(f"[WARN] 加载现有数据字典失败: {e}")
    
    try:
        # 使用第一个CSV文件获取列信息
        if not csv_files:
            print("[WARN] 没有CSV文件，无法创建数据字典")
            return
        
        df = pd.read_csv(csv_files[0])
        
        # 获取原始列名和清理后的列名的映射（全部转换为小写）
        original_columns = df.columns.tolist()
        clean_columns = []
        column_mapping = {}
        
        for col in original_columns:
            col_clean = col.strip()
            if '%' in col_clean:
                col_clean = col_clean.replace('%', 'Pct')
            col_clean = col_clean.replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
            # 转换为小写
            col_clean = col_clean.lower()
            clean_columns.append(col_clean)
            column_mapping[col_clean] = col  # 映射清理后的列名到原始列名
        
        # 创建清理后的列名列表
        df_columns = clean_columns
        
        # 构建数据字典
        data_dict = {
            'metadata': {
                'table_name': 'hk_monthly_moneyflow_analysis',
                'description': '港股月度资金流分析数据表（所有列名小写）',
                'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'version': '1.1',
                'database': str(DB_PATH.name),
                'total_files': len(csv_files),
                'total_stocks': len(processed_stocks),
                'column_case': 'lowercase'
            },
            'table_schema': {
                'primary_key': 'id',
                'columns_order': ['stock_code', 'stock_name', 'date'] + df_columns,
                'columns': [],
                'indexes': [
                    {
                        'name': 'idx_stock_code_date',
                        'fields': ['stock_code', 'date'],
                        'type': '复合索引',
                        'description': '用于快速查询特定股票的月度资金流分析数据'
                    }
                ],
                'constraints': [
                    'PRIMARY KEY (id)',
                    'UNIQUE (stock_code, date)'
                ]
            },
            'field_definitions': [],
            'data_dictionary': {
                'column_definitions': [],
                'relationships': [
                    {
                        'type': '外键关联',
                        'table': 'hk_monthly_moneyflow_analysis',
                        'field': 'stock_code',
                        'description': '可通过股票代码与股票列表关联'
                    }
                ],
                'business_rules': [
                    {
                        'rule': '每月每个股票只有一条记录',
                        'description': '数据按月去重，同一股票在同一个月份只有一条资金流分析数据'
                    },
                    {
                        'rule': '数据精度',
                        'description': '金额和百分比数据保留4位小数'
                    },
                    {
                        'rule': '索引优化',
                        'description': '使用复合索引 (stock_code, date) 优化查询性能'
                    },
                    {
                        'rule': '列名规范',
                        'description': '所有列名统一使用小写字母'
                    }
                ]
            }
        }
        
        # 添加基础字段定义
        base_fields = [
            {'name': 'id', 'type': 'INTEGER', 'description': '自增主键', 'constraint': 'PRIMARY KEY AUTOINCREMENT', 'example': '1', 'is_key': True, 'is_required': True},
            {'name': 'stock_code', 'type': 'TEXT', 'description': '股票代码（5位数字）', 'constraint': 'NOT NULL', 'example': '01951', 'is_key': True, 'is_required': True},
            {'name': 'stock_name', 'type': 'TEXT', 'description': '股票名称', 'constraint': 'NOT NULL', 'example': '锦鑫生殖', 'is_key': True, 'is_required': True},
            {'name': 'date', 'type': 'TEXT', 'description': '交易日期（YYYY-MM-DD格式）', 'constraint': 'NOT NULL', 'example': '2024-01-01', 'is_key': True, 'is_required': True},
        ]
        
        # 添加其他字段定义（使用小写列名）
        for clean_col, original_col in column_mapping.items():
            # 确定字段类型和描述
            col_lower = clean_col.lower()
            
            # 根据列名确定字段类型和描述
            if 'pct' in col_lower or 'percent' in col_lower:
                field_type = 'REAL'
                description = f'百分比指标: {original_col}'
            elif 'amount' in col_lower or 'value' in col_lower or 'volume' in col_lower:
                field_type = 'REAL'
                description = f'金额/数量指标: {original_col}'
            elif 'price' in col_lower or 'close' in col_lower or 'open' in col_lower:
                field_type = 'REAL'
                description = f'价格指标: {original_col}'
            else:
                # 根据数据类型判断
                try:
                    if pd.api.types.is_integer_dtype(df[original_col]):
                        field_type = 'INTEGER'
                    elif pd.api.types.is_float_dtype(df[original_col]):
                        field_type = 'REAL'
                    else:
                        field_type = 'TEXT'
                except:
                    field_type = 'TEXT'
                description = f'资金流分析指标: {original_col}'
            
            # 检查是否包含空值
            null_count = df[original_col].isnull().sum() if original_col in df.columns else 0
            
            field_def = {
                'name': clean_col,  # 使用小写列名
                'original_name': original_col,
                'type': field_type,
                'description': description,
                'constraint': '',
                'null_count': int(null_count),
                'sample_value': str(df[original_col].iloc[0]) if len(df) > 0 and not pd.isna(df[original_col].iloc[0]) else '',
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
        if table_exists(conn, 'hk_monthly_moneyflow_analysis'):
            try:
                cursor = conn.cursor()
                
                # 总记录数
                cursor.execute("SELECT COUNT(*) FROM hk_monthly_moneyflow_analysis")
                total_records = cursor.fetchone()[0]
                data_dict['data_statistics'] = {
                    'total_records': total_records
                }
                
                # 日期范围
                cursor.execute("""
                    SELECT MIN(date), MAX(date)
                    FROM hk_monthly_moneyflow_analysis
                    WHERE date IS NOT NULL AND date != ''
                """)
                min_date, max_date = cursor.fetchone()
                data_dict['data_statistics']['date_range'] = {
                    'earliest': min_date if min_date else None,
                    'latest': max_date if max_date else None
                }
                
                # 获取每个股票的记录数
                cursor.execute("""
                    SELECT stock_code, stock_name, COUNT(*) as count
                    FROM hk_monthly_moneyflow_analysis
                    GROUP BY stock_code, stock_name
                    ORDER BY stock_code
                """)
                stock_records = []
                for code, name, count in cursor.fetchall():
                    stock_records.append({
                        'code': code,
                        'name': name,
                        'record_count': count
                    })
                data_dict['data_statistics']['stocks'] = stock_records
                
            except Exception as e:
                print(f"   ⚠️ 获取统计信息失败: {e}")
                data_dict['data_statistics'] = {
                    'total_records': 0,
                    'date_range': {
                        'earliest': None,
                        'latest': None
                    },
                    'stocks': []
                }
        else:
            data_dict['data_statistics'] = {
                'total_records': 0,
                'date_range': {
                    'earliest': None,
                    'latest': None
                },
                'stocks': []
            }
        
        # 添加股票列表信息
        data_dict['stocks_info'] = []
        for stock_code, stock_name in processed_stocks:
            data_dict['stocks_info'].append({
                'stock_code': stock_code,
                'stock_name': stock_name,
                'added_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # 合并到现有数据字典（如果是追加）
        if existing_dict:
            # 如果存在，更新内容，但保留历史信息
            print("[INFO] 更新现有数据字典")
            
            # 更新或添加新的股票信息
            if 'stocks_info' not in existing_dict:
                existing_dict['stocks_info'] = []
            
            # 创建现有股票代码集合
            existing_codes = {s.get('stock_code') for s in existing_dict['stocks_info']}
            
            # 添加新股票
            for stock_code, stock_name in processed_stocks:
                if stock_code not in existing_codes:
                    existing_dict['stocks_info'].append({
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'added_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            # 更新元数据
            existing_dict['metadata']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            existing_dict['metadata']['total_stocks'] = len(existing_dict['stocks_info'])
            existing_dict['metadata']['total_files'] = len(csv_files)
            existing_dict['metadata']['column_case'] = 'lowercase'
            existing_dict['metadata']['version'] = '1.1'
            
            # 更新表结构信息（如果字段有变化）
            existing_dict['table_schema']['columns'] = data_dict['table_schema']['columns']
            existing_dict['data_dictionary']['column_definitions'] = data_dict['data_dictionary']['column_definitions']
            existing_dict['data_dictionary']['business_rules'] = data_dict['data_dictionary']['business_rules']
            existing_dict['data_statistics'] = data_dict['data_statistics']
            
            # 保存合并后的数据字典
            with open(dict_path, 'w', encoding='utf-8') as f:
                json.dump(existing_dict, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 数据字典已更新: {dict_path}")
        else:
            # 创建新的数据字典
            data_dict['metadata']['total_stocks'] = len(processed_stocks)
            
            # 保存数据字典
            with open(dict_path, 'w', encoding='utf-8') as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 数据字典已创建: {dict_path}")
        
        # 显示数据字典摘要
        print("\n数据字典摘要:")
        print(f"   - 表名: {data_dict['metadata']['table_name']}")
        print(f"   - 字段数: {len(data_dict['data_dictionary']['column_definitions'])}")
        print(f"   - 股票数: {len(data_dict.get('stocks_info', []))}")
        print(f"   - 总记录数: {data_dict['data_statistics'].get('total_records', 0)}")
        date_range = data_dict['data_statistics'].get('date_range', {})
        if date_range.get('earliest') and date_range.get('latest'):
            print(f"   - 数据范围: {date_range['earliest']} 至 {date_range['latest']}")
        print(f"   - 列名规范: {data_dict['metadata'].get('column_case', 'lowercase')}")
        
    except Exception as e:
        print(f"[ERROR] 创建数据字典失败: {e}")
        import traceback
        traceback.print_exc()

# =====================================================
# 5. 主函数
# =====================================================

def main():
    print("\n" + "="*60)
    print("导入月度资金流分析数据到 SQLite 数据库")
    print("所有列名将转换为小写")
    print("="*60 + "\n")
    
    # 获取所有匹配的CSV文件
    csv_files = list(DATA_DIR.glob("*_monthly_moneyflow_analysis.csv"))
    
    if not csv_files:
        print(f"[ERROR] 在 {DATA_DIR} 中未找到 *_monthly_moneyflow_analysis.csv 文件")
        print(f"[INFO] 请确认数据文件路径是否正确")
        return
    
    print(f"[INFO] 找到 {len(csv_files)} 个CSV文件:")
    for f in csv_files:
        print(f"   - {f.name}")
    
    # 解析所有股票信息
    stock_info_list = []
    for csv_file in csv_files:
        # 从文件名解析股票代码
        filename = csv_file.stem
        parts = filename.split('_')
        code = parts[0] if parts else filename
        
        # 验证代码格式
        if not re.match(r'^\d{5}$', code):
            print(f"[WARN] 无法从文件名解析股票代码: {csv_file.name}")
            numbers = re.findall(r'\d+', filename)
            if numbers:
                code = numbers[0]
                if len(code) < 5:
                    code = code.zfill(5)
                print(f"   使用提取的代码: {code}")
            else:
                print(f"   ⚠️ 跳过此文件")
                continue
        
        # 获取股票信息
        stock_info = STOCK_MAP.get(code, {})
        if not stock_info:
            print(f"[WARN] 股票 {code} 不在配置文件中")
            stock_name = f"股票_{code}"
        else:
            stock_name = stock_info.get('name', f"股票_{code}")
        
        stock_info_list.append({
            'code': code,
            'name': stock_name,
            'file': csv_file,
            'info': stock_info
        })
    
    if not stock_info_list:
        print("[ERROR] 没有有效的股票数据文件")
        return
    
    print(f"\n[INFO] 解析到 {len(stock_info_list)} 只股票:")
    for item in stock_info_list:
        print(f"   - {item['code']} {item['name']}")
    
    # 连接数据库
    conn = get_db_connection()
    
    try:
        # 检查表是否存在
        if table_exists(conn, 'hk_monthly_moneyflow_analysis'):
            existing_count = conn.execute("SELECT COUNT(*) FROM hk_monthly_moneyflow_analysis").fetchone()[0]
            if existing_count > 0:
                print(f"\n[WARN] 表 hk_monthly_moneyflow_analysis 中已有 {existing_count} 条记录")
                print("选项:")
                print("  1. 清空现有数据并重新导入 (y)")
                print("  2. 保留现有数据，追加新数据 (n)")
                print("  3. 删除表并重新创建 (d) - 将创建新表结构（所有列名小写）")
                response = input("请选择 (y/n/d): ").strip().lower()
                
                if response == 'd':
                    if not recreate_table(conn, csv_files):
                        print("[ERROR] 重新创建表失败")
                        return
                elif response == 'y' or response == 'yes':
                    clear_table(conn, 'hk_monthly_moneyflow_analysis')
                    print("[INFO] 已清空旧数据")
                else:
                    print("[INFO] 保留现有数据，将追加新数据")
            else:
                # 表存在但没有数据，检查表结构是否正确
                print("[INFO] 表存在但没有数据，检查表结构...")
                # 获取表结构
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(hk_monthly_moneyflow_analysis)")
                columns = cursor.fetchall()
                # 检查是否包含stock_code、stock_name、date字段
                col_names = [col[1] for col in columns]
                if 'stock_code' not in col_names or 'stock_name' not in col_names or 'date' not in col_names:
                    print("[WARN] 表结构不完整，重新创建表")
                    if not recreate_table(conn, csv_files):
                        print("[ERROR] 重新创建表失败")
                        return
                else:
                    print("[INFO] 表结构完整，可以继续导入")
        else:
            # 表不存在，创建新表
            print("[INFO] 创建新表...")
            if not create_table_if_not_exists(conn, csv_files):
                print("[ERROR] 创建表失败")
                return
        
        # 导入数据
        print("\n开始导入数据...")
        print("-" * 60)
        
        total_records = 0
        processed_stocks = []
        
        for stock_item in stock_info_list:
            code = stock_item['code']
            stock_name = stock_item['name']
            csv_file = stock_item['file']
            stock_info = stock_item['info']
            
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
                processed_stocks.append((code, stock_name))
            
            conn.commit()
        
        # 显示结果
        print("\n" + "="*60)
        print("导入完成!")
        print("="*60)
        print(f"✅ 成功处理 {len(processed_stocks)}/{len(stock_info_list)} 只股票")
        print(f"📊 共导入 {total_records} 条记录")
        
        # 显示表信息
        if table_exists(conn, 'hk_monthly_moneyflow_analysis'):
            count = conn.execute("SELECT COUNT(*) FROM hk_monthly_moneyflow_analysis").fetchone()[0]
            print(f"\n📋 表 hk_monthly_moneyflow_analysis 当前共有 {count} 条记录")
            
            # 显示表结构
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(hk_monthly_moneyflow_analysis)")
            columns = cursor.fetchall()
            print(f"\n📋 表结构（字段顺序）:")
            for i, col in enumerate(columns, 1):
                print(f"   {i}. {col[1]} ({col[2]}) {'NOT NULL' if col[3] else ''}")
            
            # 显示索引
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='hk_monthly_moneyflow_analysis'")
            indexes = cursor.fetchall()
            if indexes:
                print(f"\n📋 索引:")
                for idx_name, idx_sql in indexes:
                    print(f"   - {idx_name}")
            
            # 显示股票统计
            stocks = conn.execute(
                "SELECT DISTINCT stock_code, stock_name FROM hk_monthly_moneyflow_analysis ORDER BY stock_code"
            ).fetchall()
            print(f"\n📈 包含 {len(stocks)} 只股票的数据:")
            for code_val, name_val in stocks:
                cnt = conn.execute(
                    f"SELECT COUNT(*) FROM hk_monthly_moneyflow_analysis WHERE stock_code='{code_val}'"
                ).fetchone()[0]
                # 检查是否在配置文件中
                in_config = "✓" if code_val in STOCK_MAP else "⚠️"
                print(f"   {in_config} {code_val} {name_val}: {cnt} 条记录")
        
        # 创建数据字典
        if processed_stocks:
            create_data_dictionary(conn, csv_files, processed_stocks)
        else:
            print("\n[WARN] 没有成功导入任何数据，跳过创建数据字典")
        
    except Exception as e:
        print(f"\n[ERROR] 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    main()