#!/usr/bin/env python
# coding: utf-8

"""
Verify_Monthly_Kline_Analysis.py
数据验证程序 - 验证 hk_monthly_kline_analysis 表的月K线技术分析数据
功能:
  1. 显示表的基本信息（字段、记录数、日期范围等）
  2. 显示每只股票的数据统计
  3. 显示最新的10条记录及最前面的15个列
  4. 检查数据完整性（空值、重复值等）
  5. 检查价格数据的合理性（OHLC逻辑）
  6. 验证数据字典是否与表结构匹配
  7. 生成验证报告到 Report 目录
  8. 保存验证结果到JSON文件

脚本位置: TA_Workflow2/Code_utl/Verify_Monthly_Kline_Analysis.py
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
import re

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

# 添加必要的路径到 sys.path
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))
    print(f"[INFO] 已添加项目根目录到 sys.path: {project_dir}")

core_dir = project_dir / 'Core'
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))
    print(f"[INFO] 已添加 Core 目录到 sys.path: {core_dir}")

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
    from Core.Utl.stock_analysis_utl import load_config, GlobalConfig
    print("[INFO] 成功导入 Core.Utl.stock_analysis_utl")
except ImportError as e:
    print(f"[WARN] 无法导入 Core.Utl.stock_analysis_utl: {e}")
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
# 3. 数据字典验证函数
# =====================================================

def load_data_dictionary():
    """加载数据字典文件"""
    dict_path = project_dir / 'Config' / 'hk_monthly_kline_analysis.json'
    
    if not dict_path.exists():
        return None, "数据字典文件不存在"
    
    try:
        with open(dict_path, 'r', encoding='utf-8') as f:
            data_dict = json.load(f)
        return data_dict, None
    except json.JSONDecodeError as e:
        return None, f"JSON解析失败: {e}"
    except Exception as e:
        return None, f"加载失败: {e}"

def verify_data_dictionary(conn, table_name):
    """验证数据字典是否与表结构匹配"""
    print("\n" + "-" * 80)
    print(" 📋 数据字典验证")
    print("-" * 80)
    
    data_dict, error = load_data_dictionary()
    if error:
        print(f"  ⚠️ 数据字典验证跳过: {error}")
        return False
    
    if not data_dict:
        print("  ⚠️ 数据字典为空")
        return False
    
    print(f"  ✅ 数据字典文件存在")
    
    # 检查基本结构
    required_keys = ['metadata', 'table_schema', 'data_dictionary']
    missing_keys = [key for key in required_keys if key not in data_dict]
    if missing_keys:
        print(f"  ⚠️ 数据字典缺少必要的键: {missing_keys}")
        return False
    
    # 检查表名
    table_name_from_dict = data_dict.get('metadata', {}).get('table_name', '')
    if table_name_from_dict != table_name:
        print(f"  ⚠️ 数据字典中的表名 '{table_name_from_dict}' 与当前表名 '{table_name}' 不匹配")
    else:
        print(f"  ✅ 表名匹配: {table_name}")
    
    # 获取表结构
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        db_columns = {col[1]: {'type': col[2], 'notnull': col[3], 'pk': col[5]} for col in columns}
    except Exception as e:
        print(f"  ⚠️ 无法获取表结构: {e}")
        return False
    
    # 获取数据字典中的字段定义
    dict_columns = {}
    for field in data_dict.get('data_dictionary', {}).get('column_definitions', []):
        name = field.get('name', '')
        if name:
            dict_columns[name] = field
    
    # 比较字段
    db_field_names = set(db_columns.keys())
    dict_field_names = set(dict_columns.keys())
    
    # 检查缺失字段
    missing_in_dict = db_field_names - dict_field_names
    if missing_in_dict:
        print(f"\n  ⚠️ 数据库中有但数据字典中缺失的字段 ({len(missing_in_dict)}):")
        for field in sorted(missing_in_dict):
            print(f"     - {field}")
    else:
        print(f"\n  ✅ 所有数据库字段都在数据字典中")
    
    # 检查额外字段
    extra_in_dict = dict_field_names - db_field_names
    if extra_in_dict:
        print(f"\n  ⚠️ 数据字典中有但数据库中不存在的字段 ({len(extra_in_dict)}):")
        for field in sorted(extra_in_dict):
            print(f"     - {field}")
    else:
        print(f"  ✅ 数据字典中的所有字段都在数据库中")
    
    # 检查字段类型一致性（支持布尔列的特殊处理）
    type_errors = []
    type_warnings = []
    boolean_columns_verified = []
    
    for field_name in db_field_names.intersection(dict_field_names):
        db_type = db_columns[field_name]['type'].upper()
        
        # 获取字典中的类型信息
        dict_field = dict_columns[field_name]
        dict_type = dict_field.get('type', '').upper()
        logical_type = dict_field.get('logical_type', '').upper()
        is_boolean = dict_field.get('is_boolean', False)
        
        # 如果是布尔列，进行特殊处理
        if is_boolean:
            boolean_columns_verified.append(field_name)
            # 检查是否使用INTEGER存储
            if db_type in ['INTEGER', 'INT']:
                # 这是正确的 - SQLite使用INTEGER存储布尔值
                # 检查字典中的type字段是否也是INTEGER
                if dict_type in ['INTEGER', 'INT']:
                    continue
                else:
                    # 如果字典中的type不是INTEGER，给出警告
                    type_warnings.append(
                        f"     {field_name}: 布尔列应使用INTEGER存储，"
                        f"但数据字典中type为 {dict_type} (逻辑类型: {logical_type})"
                    )
            else:
                # 如果数据库类型不是INTEGER，这是错误
                type_errors.append(
                    f"     {field_name}: 布尔列应该使用INTEGER类型，"
                    f"但数据库类型是 {db_type}"
                )
            continue
        
        # 对于非布尔列，进行正常的类型检查
        # SQLite类型映射
        type_mapping = {
            'INTEGER': ['INTEGER', 'INT'],
            'REAL': ['REAL', 'FLOAT', 'DOUBLE', 'NUMERIC'],
            'TEXT': ['TEXT', 'VARCHAR', 'CHAR', 'STRING', 'CLOB'],
            'BLOB': ['BLOB']
        }
        
        # 检查类型是否兼容
        compatible = False
        for key, types in type_mapping.items():
            if db_type in types and dict_type in types:
                compatible = True
                break
        
        if not compatible:
            # 特殊情况：如果数据库类型是NUMERIC但字典是REAL，也算兼容
            if db_type == 'NUMERIC' and dict_type == 'REAL':
                continue
            type_errors.append(f"     {field_name}: 数据库 {db_type} vs 数据字典 {dict_type}")
    
    # 显示布尔列验证结果
    if boolean_columns_verified:
        print(f"\n  🔍 布尔列验证 ({len(boolean_columns_verified)} 个):")
        for col in boolean_columns_verified:
            # 获取统计信息
            dict_field = dict_columns[col]
            stats = dict_field.get('boolean_stats', {})
            if stats:
                true_count = stats.get('true_count', 0)
                false_count = stats.get('false_count', 0)
                null_count = stats.get('null_count', 0)
                true_pct = stats.get('true_percentage', '0%')
                false_pct = stats.get('false_percentage', '0%')
                print(f"     ✅ {col}: True={true_count:,} ({true_pct}), False={false_count:,} ({false_pct}), Null={null_count:,}")
            else:
                print(f"     ✅ {col}: 布尔列 (存储为INTEGER)")
    
    # 显示警告和错误
    if type_warnings:
        print(f"\n  ⚠️ 类型警告 ({len(type_warnings)}):")
        for warning in type_warnings:
            print(warning)
    
    if type_errors:
        print(f"\n  ❌ 类型不匹配 ({len(type_errors)}):")
        for error in type_errors:
            print(error)
        return False
    else:
        print(f"\n  ✅ 所有字段类型匹配")
        if boolean_columns_verified:
            print(f"     (布尔列使用INTEGER存储是正常的，符合SQLite规范)")
    
    # 检查索引
    dict_indexes = data_dict.get('table_schema', {}).get('indexes', [])
    if dict_indexes:
        print(f"\n  数据字典中的索引:")
        for idx in dict_indexes:
            idx_name = idx.get('name', '未命名')
            idx_fields = idx.get('fields', [])
            print(f"     - {idx_name}: {idx_fields}")
        
        # 验证索引是否在数据库中存在
        try:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table_name}'")
            db_indexes = [row[0] for row in cursor.fetchall()]
            
            missing_indexes = []
            for idx in dict_indexes:
                idx_name = idx.get('name', '')
                if idx_name and idx_name not in db_indexes:
                    missing_indexes.append(idx_name)
            
            if missing_indexes:
                print(f"\n  ⚠️ 数据字典中定义但数据库中不存在的索引:")
                for idx_name in missing_indexes:
                    print(f"     - {idx_name}")
            else:
                print(f"\n  ✅ 所有索引都已创建")
        except Exception as e:
            print(f"\n  ⚠️ 无法验证索引: {e}")
    
    # 检查字段顺序
    print(f"\n  字段顺序验证:")
    db_field_list = list(db_columns.keys())
    dict_field_list = [f['name'] for f in data_dict.get('data_dictionary', {}).get('column_definitions', []) 
                      if f['name'] in db_columns]
    
    # 检查前几个关键字段的顺序
    priority_fields = ['id', 'stock_code', 'stock_name', 'date']
    order_mismatch = False
    
    for field in priority_fields:
        if field in db_field_list and field in dict_field_list:
            db_pos = db_field_list.index(field)
            dict_pos = dict_field_list.index(field)
            if db_pos != dict_pos:
                print(f"     ⚠️ 字段 '{field}' 位置不匹配: 数据库第{db_pos+1}位 vs 数据字典第{dict_pos+1}位")
                order_mismatch = True
    
    if not order_mismatch:
        print(f"     ✅ 关键字段顺序匹配")
    
    # 检查业务规则
    business_rules = data_dict.get('data_dictionary', {}).get('business_rules', [])
    if business_rules:
        print(f"\n  业务规则 ({len(business_rules)}):")
        for i, rule in enumerate(business_rules[:10], 1):
            rule_name = rule.get('rule', '')
            rule_desc = rule.get('description', '')
            print(f"     {i}. {rule_name}: {rule_desc[:80]}{'...' if len(rule_desc) > 80 else ''}")
        if len(business_rules) > 10:
            print(f"     ... 还有 {len(business_rules) - 10} 条规则")
    
    # 检查布尔列映射
    boolean_mapping = data_dict.get('data_dictionary', {}).get('boolean_column_mapping', {})
    if boolean_mapping:
        print(f"\n  布尔列映射 ({len(boolean_mapping)} 个):")
        for col, desc in boolean_mapping.items():
            print(f"     - {col}: {desc}")
    
    # 检查类型映射说明
    type_notes = data_dict.get('data_dictionary', {}).get('type_mapping_notes', {})
    if type_notes:
        print(f"\n  类型映射说明:")
        for type_name, note in type_notes.items():
            print(f"     - {type_name}: {note}")
    
    # 检查示例查询
    usage_examples = data_dict.get('usage_examples', {})
    if usage_examples:
        print(f"\n  使用示例 ({len(usage_examples)} 个):")
        for example_name, example_sql in list(usage_examples.items())[:3]:
            print(f"     - {example_name}: {example_sql[:60]}{'...' if len(example_sql) > 60 else ''}")
    
    # 总结
    print(f"\n  ✅ 数据字典验证完成")
    print(f"     字段总数: {len(db_columns)}")
    print(f"     布尔列数: {len(boolean_columns_verified)}")
    print(f"     索引数: {len(dict_indexes)}")
    print(f"     业务规则: {len(business_rules)}")
    
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
    query = f"""
        SELECT 
            stock_code,
            stock_name,
            COUNT(*) as record_count,
            MIN(date) as first_date,
            MAX(date) as last_date,
            COUNT(DISTINCT date) as trading_months,
            MIN(Close) as min_close,
            MAX(Close) as max_close,
            AVG(Close) as avg_close
        FROM {table_name}
        GROUP BY stock_code, stock_name
        ORDER BY stock_code
    """
    df = pd.read_sql_query(query, conn)
    return df

def get_table_sample(conn, table_name, limit=10, max_cols=15):
    """获取表的最新记录（按日期升序），只显示前15个列"""
    try:
        # 获取所有列名
        col_info = get_table_info(conn, table_name)
        all_columns = col_info['name'].tolist()
        
        # 优先显示重要的列
        priority_cols = ['stock_code', 'stock_name', 'date', 'Open', 'High', 'Low', 'Close', 'Volume']
        other_cols = [col for col in all_columns if col not in priority_cols and col != 'id']
        
        # 构建显示列列表（id 放在最后）
        display_cols = ['id'] if 'id' in all_columns else []
        display_cols.extend([col for col in priority_cols if col in all_columns])
        
        # 限制显示列数
        remaining_slots = max_cols - len(display_cols)
        if remaining_slots > 0 and other_cols:
            display_cols.extend(other_cols[:remaining_slots])
        
        # 获取最新的 N 条记录（按日期降序取最新，然后升序显示）
        select_cols = ', '.join([f'"{col}"' for col in display_cols])
        query = f"""
            SELECT {select_cols} FROM {table_name} 
            ORDER BY date DESC 
            LIMIT {limit}
        """
        df = pd.read_sql_query(query, conn)
        
        # 按日期升序排列
        if not df.empty and 'date' in df.columns:
            df = df.sort_values('date', ascending=True)
        
        # 如果实际列数少于15，说明还有其他列未显示
        if len(all_columns) > len(display_cols):
            remaining = len(all_columns) - len(display_cols)
            # 在DataFrame中添加注释列
            df['...'] = f'... 还有 {remaining} 个列未显示'
        
        return df, display_cols, all_columns
    except Exception as e:
        print(f"  ⚠️ 获取样本数据失败: {e}")
        return pd.DataFrame(), [], []

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

def check_ohlc_logic(conn, table_name):
    """检查OHLC价格逻辑（High >= Low, High >= Open/Close, Low <= Open/Close）"""
    try:
        # 检查价格逻辑错误
        query = f"""
            SELECT 
                stock_code,
                date,
                Open,
                High,
                Low,
                Close,
                CASE 
                    WHEN High < Low THEN 'High < Low'
                    WHEN High < Open THEN 'High < Open'
                    WHEN High < Close THEN 'High < Close'
                    WHEN Low > Open THEN 'Low > Open'
                    WHEN Low > Close THEN 'Low > Close'
                    WHEN Open < 0 OR High < 0 OR Low < 0 OR Close < 0 THEN 'Negative price'
                    ELSE NULL
                END as error_type
            FROM {table_name}
            WHERE 
                High < Low 
                OR High < Open 
                OR High < Close
                OR Low > Open 
                OR Low > Close
                OR Open < 0 
                OR High < 0 
                OR Low < 0 
                OR Close < 0
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"  ⚠️ OHLC逻辑检查失败: {e}")
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

def get_technical_indicators_summary(conn, table_name):
    """获取技术指标字段摘要"""
    try:
        col_info = get_table_info(conn, table_name)
        all_columns = col_info['name'].tolist()
        
        # 识别技术指标字段（排除基础字段）
        base_fields = ['id', 'stock_code', 'stock_name', 'date']
        tech_indicators = [col for col in all_columns if col not in base_fields]
        
        return tech_indicators
    except Exception as e:
        print(f"  ⚠️ 获取技术指标摘要失败: {e}")
        return []

# =====================================================
# 5. 显示函数
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
        print(f"    总交易月数: {stock_stats['trading_months'].sum():,}")
        print(f"    平均每只股票记录数: {stock_stats['record_count'].mean():.1f}")

    # 日期范围
    date_range = get_date_range_per_stock(conn, table_name)
    if not date_range.empty:
        min_date = date_range['first_date'].min()
        max_date = date_range['last_date'].max()
        print(f"\n  📅 全局日期范围:")
        print(f"    最早日期: {min_date}")
        print(f"    最晚日期: {max_date}")
    
    # 技术指标摘要
    tech_indicators = get_technical_indicators_summary(conn, table_name)
    if tech_indicators:
        print(f"\n  📊 技术指标字段 ({len(tech_indicators)} 个):")
        # 按类别分组显示
        ma_fields = [col for col in tech_indicators if re.search(r'ma\d+', col.lower())]
        other_fields = [col for col in tech_indicators if col not in ma_fields]
        
        if ma_fields:
            print(f"    移动平均线: {', '.join(ma_fields[:10])}")
            if len(ma_fields) > 10:
                print(f"      ... 还有 {len(ma_fields)-10} 个")
        
        if other_fields:
            print(f"    其他指标: {', '.join(other_fields[:10])}")
            if len(other_fields) > 10:
                print(f"      ... 还有 {len(other_fields)-10} 个")

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
            row['last_date'],
            f"{row['min_close']:.2f}",
            f"{row['max_close']:.2f}",
            f"{row['avg_close']:.2f}"
        ])

    print(tabulate(display_data,
                   headers=['状态', '代码', '名称', '记录数', '开始日期', '结束日期', '最低价', '最高价', '均价'],
                   tablefmt='grid',
                   stralign='left'))

def display_sample_data(conn, table_name, limit=10, max_cols=15):
    """显示样本数据 - 最新10条记录及最前面的15个列"""
    print("\n" + "-" * 80)
    print(f" 📋 最新 {limit} 条记录 (按日期升序) - 显示前 {max_cols} 个列")
    print("-" * 80)

    df, display_cols, all_columns = get_table_sample(conn, table_name, limit, max_cols)

    if df.empty:
        print("  ⚠️ 无数据")
        return

    # 选择要显示的列（排除id，除非它是唯一的）
    if 'id' in df.columns and len(df.columns) > 1:
        df_display = df.drop(columns=['id'], errors='ignore')
    else:
        df_display = df

    # 如果还有...列，保留它
    if '...' in df.columns:
        # 将...列移到最后一列
        cols = [col for col in df_display.columns if col != '...']
        cols.append('...')
        df_display = df_display[cols]

    # 格式化数值
    for col in df_display.columns:
        if col in ['Open', 'High', 'Low', 'Close']:
            df_display[col] = df_display[col].apply(lambda x: f"{x:.4f}" if pd.notna(x) else '')
        elif col == 'Volume':
            df_display[col] = df_display[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else '')
        elif col not in ['stock_code', 'stock_name', 'date', '...'] and col != '...':
            # 其他数值列
            if pd.api.types.is_numeric_dtype(df_display[col]):
                df_display[col] = df_display[col].apply(lambda x: f"{x:.4f}" if pd.notna(x) else '')

    print(tabulate(df_display,
                   headers='keys',
                   tablefmt='grid',
                   stralign='right',
                   showindex=False))
    
    # 显示列统计信息
    if display_cols:
        print(f"\n  显示列数: {len(display_cols)} (共 {len(all_columns)} 列)")
        if len(all_columns) > len(display_cols):
            remaining = len(all_columns) - len(display_cols)
            print(f"  还有 {remaining} 个列未显示")

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

    # 3. OHLC逻辑检查
    ohlc_errors = check_ohlc_logic(conn, table_name)
    print(f"\n  3. OHLC价格逻辑检查:")
    if ohlc_errors.empty:
        print("     ✅ 所有OHLC逻辑正确")
    else:
        print(f"     ⚠️ 发现 {len(ohlc_errors)} 条OHLC逻辑错误")
        error_data = []
        for _, row in ohlc_errors.head(5).iterrows():
            stock_code = row.get('stock_code', 'N/A')
            date_val = row.get('date', 'N/A')
            open_val = row.get('Open', 'N/A')
            high_val = row.get('High', 'N/A')
            low_val = row.get('Low', 'N/A')
            close_val = row.get('Close', 'N/A')
            error_type = row.get('error_type', 'Unknown')
            
            try:
                open_str = f"{float(open_val):.2f}" if open_val != 'N/A' and pd.notna(open_val) else 'N/A'
                high_str = f"{float(high_val):.2f}" if high_val != 'N/A' and pd.notna(high_val) else 'N/A'
                low_str = f"{float(low_val):.2f}" if low_val != 'N/A' and pd.notna(low_val) else 'N/A'
                close_str = f"{float(close_val):.2f}" if close_val != 'N/A' and pd.notna(close_val) else 'N/A'
            except (ValueError, TypeError):
                open_str = str(open_val)
                high_str = str(high_val)
                low_str = str(low_val)
                close_str = str(close_val)
            
            error_data.append([
                stock_code,
                date_val,
                open_str,
                high_str,
                low_str,
                close_str,
                error_type
            ])
        
        if error_data:
            print("     错误记录示例 (前5条):")
            print(tabulate(error_data,
                           headers=['股票代码', '日期', '开盘', '最高', '最低', '收盘', '错误类型'],
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

# =====================================================
# 6. 生成验证报告
# =====================================================

def generate_report(conn, table_name):
    """生成验证报告"""
    REPORT_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"Verify_Monthly_Kline_Analysis_{timestamp}.txt"
    report_path = REPORT_DIR / report_filename
    json_report_path = REPORT_DIR / f"Verify_Monthly_Kline_Analysis_{timestamp}.json"

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
            'ohlc_errors': [],
            'missing_stocks': [],
            'extra_stocks': []
        },
        'data_dictionary_validation': {}
    }

    # 基本信息
    total_records = get_table_count(conn, table_name)
    validation_data['basic_info']['total_records'] = total_records
    validation_data['basic_info']['columns'] = get_table_info(conn, table_name).to_dict('records')

    # 股票统计
    stock_stats = get_stock_statistics(conn, table_name)
    validation_data['stock_statistics'] = stock_stats.to_dict('records')

    # 样本数据（保存所有列，但只显示前15个）
    sample_df, display_cols, all_columns = get_table_sample(conn, table_name, limit=10, max_cols=15)
    validation_data['sample_data'] = sample_df.to_dict('records')
    validation_data['sample_data_columns'] = {
        'displayed': display_cols,
        'all_columns': all_columns,
        'displayed_count': len(display_cols),
        'total_count': len(all_columns)
    }

    # 质量检查
    null_counts = check_null_values(conn, table_name)
    validation_data['quality_checks']['null_values'] = null_counts

    duplicates = check_duplicates(conn, table_name)
    validation_data['quality_checks']['duplicates'] = duplicates.to_dict('records')

    ohlc_errors = check_ohlc_logic(conn, table_name)
    validation_data['quality_checks']['ohlc_errors'] = ohlc_errors.to_dict('records')

    missing_stocks, extra_stocks = check_missing_stocks(conn, table_name)
    validation_data['quality_checks']['missing_stocks'] = list(missing_stocks)
    validation_data['quality_checks']['extra_stocks'] = list(extra_stocks)

    # 数据字典验证
    data_dict, error = load_data_dictionary()
    if data_dict:
        validation_data['data_dictionary_validation'] = {
            'exists': True,
            'valid': True,
            'table_name_match': data_dict.get('metadata', {}).get('table_name') == table_name
        }
    else:
        validation_data['data_dictionary_validation'] = {
            'exists': False,
            'valid': False,
            'error': error
        }

    # 保存JSON报告
    with open(json_report_path, 'w', encoding='utf-8') as f:
        json.dump(validation_data, f, ensure_ascii=False, indent=2, default=str)

    # 生成文本报告
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("月K线技术分析数据验证报告\n")
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
        f.write(f"字段数: {len(validation_data['basic_info']['columns'])}\n")
        
        # 技术指标
        tech_indicators = get_technical_indicators_summary(conn, table_name)
        f.write(f"技术指标字段数: {len(tech_indicators)}\n\n")

        # 股票统计
        f.write("-" * 80 + "\n")
        f.write("每只股票统计\n")
        f.write("-" * 80 + "\n")
        for _, row in stock_stats.iterrows():
            in_config = "✓" if row['stock_code'] in STOCK_MAP else "⚠️"
            f.write(f"  {in_config} {row['stock_code']} {row['stock_name']}: ")
            f.write(f"{row['record_count']:,} 条记录, ")
            f.write(f"{row['first_date']} ~ {row['last_date']}, ")
            f.write(f"价格区间: {row['min_close']:.2f} ~ {row['max_close']:.2f}\n")
        f.write("\n")

        # 样本数据显示
        f.write("-" * 80 + "\n")
        f.write(f"样本数据 (最新10条 - 显示前15个列)\n")
        f.write("-" * 80 + "\n")
        if not sample_df.empty:
            # 移除 id 列
            if 'id' in sample_df.columns:
                sample_df_display = sample_df.drop(columns=['id'], errors='ignore')
            else:
                sample_df_display = sample_df
            
            # 如果还有...列，保留它
            if '...' in sample_df_display.columns:
                cols = [col for col in sample_df_display.columns if col != '...']
                cols.append('...')
                sample_df_display = sample_df_display[cols]
            
            f.write(sample_df_display.to_string(index=False))
            f.write("\n")
            f.write(f"\n显示列数: {len(validation_data['sample_data_columns']['displayed'])} (共 {validation_data['sample_data_columns']['total_count']} 列)\n")
            if validation_data['sample_data_columns']['total_count'] > validation_data['sample_data_columns']['displayed_count']:
                remaining = validation_data['sample_data_columns']['total_count'] - validation_data['sample_data_columns']['displayed_count']
                f.write(f"还有 {remaining} 个列未显示\n")
        else:
            f.write("  无样本数据\n")
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

        # OHLC错误
        f.write(f"3. OHLC逻辑检查: {len(ohlc_errors)} 条错误\n")
        if not ohlc_errors.empty:
            for _, row in ohlc_errors.head(10).iterrows():
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

        # 数据字典验证
        f.write("-" * 80 + "\n")
        f.write("数据字典验证\n")
        f.write("-" * 80 + "\n")
        data_dict, error = load_data_dictionary()
        if data_dict:
            f.write(f"  ✅ 数据字典文件存在: hk_monthly_kline_analysis.json\n")
            dict_table_name = data_dict.get('metadata', {}).get('table_name', '')
            if dict_table_name == table_name:
                f.write(f"  ✅ 表名匹配: {dict_table_name}\n")
            else:
                f.write(f"  ⚠️ 表名不匹配: 字典中的 '{dict_table_name}' vs 实际 '{table_name}'\n")
            
            dict_fields = len(data_dict.get('data_dictionary', {}).get('column_definitions', []))
            f.write(f"  数据字典字段数: {dict_fields}\n")
            
            # 检查索引
            indexes = data_dict.get('table_schema', {}).get('indexes', [])
            if indexes:
                f.write(f"  索引定义: {len(indexes)} 个\n")
                for idx in indexes:
                    f.write(f"     - {idx.get('name')}: {idx.get('fields')}\n")
        else:
            f.write(f"  ⚠️ 数据字典文件不存在: {error}\n")

        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write("报告结束\n")
        f.write("=" * 80 + "\n")

    return report_path, json_report_path

# =====================================================
# 7. 主函数
# =====================================================

def main():
    print("\n" + "=" * 80)
    print("月K线技术分析数据验证工具")
    print("=" * 80)
    print(f"项目目录: {project_dir}")
    print(f"数据库路径: {DB_PATH}")
    print(f"配置文件股票数: {len(STOCK_LIST)}")
    print("=" * 80)

    # 检查数据库是否存在
    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("请先运行 Import_Monthly_Kline_Analysis.py 导入数据")
        sys.exit(1)

    TABLE_NAME = 'hk_monthly_kline_analysis'

    # 获取数据库连接
    conn = get_db_connection()

    try:
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}'")
        if not cursor.fetchone():
            print(f"❌ 表 {TABLE_NAME} 不存在")
            print("请先运行 Import_Monthly_Kline_Analysis.py 导入数据")
            return

        # 显示表摘要
        display_table_summary(conn, TABLE_NAME)

        # 显示股票统计
        display_stock_statistics(conn, TABLE_NAME)

        # 显示样本数据（最新10条，显示前15个列）
        display_sample_data(conn, TABLE_NAME, limit=10, max_cols=15)

        # 显示数据质量检查
        display_quality_checks(conn, TABLE_NAME)

        # 验证数据字典
        verify_data_dictionary(conn, TABLE_NAME)

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

    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    main()