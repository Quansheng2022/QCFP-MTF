#!/usr/bin/env python
# coding: utf-8

"""
Import_Daily_Kline_Analysis.py
将日K线分析数据CSV文件导入SQLite数据库
从CSV文件解析股票代码，匹配股票名称，创建hk_daily_kline_analysis表

脚本位置: TA_Workflow2/Code_utl/Import_Daily_Kline_Analysis.py
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
# 1. 路径设置（参考Import_Daily_Moneyflow.py）
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
    将含有%符号的列名改成 ...Pct
    例如: Close_Chg% => Close_ChgPct
    """
    col_name = col_name.strip()
    # 替换 % 为 Pct
    if '%' in col_name:
        col_name = col_name.replace('%', 'Pct')
    # 替换其他特殊字符
    col_name = col_name.replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
    col_name = col_name.replace('-', '_').replace('.', '_')
    return col_name

def detect_boolean_column(series):
    """
    检测列是否包含布尔值（TRUE/FALSE）
    返回: (is_boolean, boolean_values)
    """
    if len(series) == 0:
        return False, None
    
    # 获取非空值
    non_null_values = series.dropna()
    if len(non_null_values) == 0:
        return False, None
    
    # 获取前100个非空值进行检测（如果数据量很大）
    sample_size = min(100, len(non_null_values))
    sample_values = non_null_values.iloc[:sample_size]
    
    # 检查是否所有值都是布尔值或类布尔值
    boolean_patterns = [
        r'(?i)^(true|false)$',     # TRUE/FALSE (不区分大小写)
        r'(?i)^(t|f)$',            # T/F (不区分大小写)
        r'(?i)^(yes|no)$',         # YES/NO (不区分大小写)
        r'(?i)^(y|n)$',            # Y/N (不区分大小写)
        r'^(1|0)$',                # 1/0 (数字)
        r'(?i)^(on|off)$'          # ON/OFF (不区分大小写)
    ]
    
    # 转换为字符串进行匹配
    str_values = sample_values.astype(str).str.strip()
    
    # 检查是否所有值都匹配布尔模式
    is_boolean = True
    for val in str_values:
        matched = False
        for pattern in boolean_patterns:
            try:
                if re.match(pattern, val):
                    matched = True
                    break
            except re.error:
                # 如果正则表达式有错误，跳过
                continue
        if not matched:
            is_boolean = False
            break
    
    if is_boolean:
        # 规范化布尔值
        boolean_mapping = {
            'true': True, 'TRUE': True, 'True': True,
            't': True, 'T': True,
            'yes': True, 'YES': True, 'Yes': True,
            'y': True, 'Y': True,
            '1': True,
            'on': True, 'ON': True, 'On': True,
            'false': False, 'FALSE': False, 'False': False,
            'f': False, 'F': False,
            'no': False, 'NO': False, 'No': False,
            'n': False, 'N': False,
            '0': False,
            'off': False, 'OFF': False, 'Off': False
        }
        # 使用apply进行映射，处理可能的NaN
        boolean_values = str_values.map(lambda x: boolean_mapping.get(x.lower(), False))
        return True, boolean_values
    
    return False, None

def create_table_if_not_exists(conn):
    """
    创建 hk_daily_kline_analysis 表（如果不存在）
    根据CSV文件列名创建表结构
    """
    # 先读取一个CSV文件样例来获取列结构
    csv_files = list(DATA_DIR.glob("*_daily_technical_analysis.csv"))
    if not csv_files:
        print(f"[ERROR] 未找到任何 *_daily_technical_analysis.csv 文件")
        return False
    
    # 读取第一个CSV文件获取列结构
    sample_file = csv_files[0]
    try:
        df_sample = pd.read_csv(sample_file)
        
        # 检测并标记布尔列
        boolean_columns = {}
        for col in df_sample.columns:
            try:
                is_bool, _ = detect_boolean_column(df_sample[col])
                if is_bool:
                    boolean_columns[col] = 'BOOLEAN'
                    print(f"   🔍 检测到布尔列: {col}")
            except Exception as e:
                print(f"   ⚠️ 检测列 '{col}' 时出错: {e}")
                continue
        
        # 构建CREATE TABLE语句 - 将 stock_code 和 stock_name 放在最前面
        columns = [
            'stock_code TEXT NOT NULL',
            'stock_name TEXT NOT NULL'
        ]
        
        # 添加其他列（排除date列，因为我们要单独处理）
        date_col_found = False
        for col in df_sample.columns:
            col_clean = clean_column_name(col)
            
            # 检查是否是日期列
            if 'date' in col.lower():
                # 如果已经添加了date列，跳过
                if date_col_found:
                    continue
                columns.append('date TEXT NOT NULL')
                date_col_found = True
                continue
            
            # 检查是否是布尔列 - 使用 INTEGER 类型存储 (0/1)
            if col in boolean_columns:
                columns.append(f'"{col_clean}" INTEGER DEFAULT 0')
                continue
            
            # 根据列名和数据类型选择合适的SQLite类型
            col_lower = col.lower()
            
            # 检查是否是价格相关字段
            if any(keyword in col_lower for keyword in ['price', 'open', 'high', 'low', 'close', 'adj']):
                col_type = 'REAL'
            # 检查是否是百分比字段（包含Pct或%）
            elif 'pct' in col_lower or '%' in col:
                col_type = 'REAL'
            # 检查是否是成交量或金额字段
            elif any(keyword in col_lower for keyword in ['volume', 'amount', 'turnover', 'money']):
                col_type = 'REAL'
            # 检查是否是技术指标
            elif any(keyword in col_lower for keyword in ['ma', 'ema', 'rsi', 'macd', 'kdj', 'boll', 'atr', 'adx']):
                col_type = 'REAL'
            # 检查是否是信号字段
            elif any(keyword in col_lower for keyword in ['signal', 'trend', 'direction']):
                col_type = 'TEXT'
            else:
                # 自动检测数据类型
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
        
        # 如果没有找到date列，添加一个默认的date列
        if not date_col_found:
            columns.append('date TEXT NOT NULL')
        
        # 创建表
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS hk_daily_kline_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(columns)}
        )
        """
        
        conn.execute(create_sql)
        print(f"[INFO] 表 hk_daily_kline_analysis 已创建或已存在")
        print(f"[INFO] 表结构包含 {len(columns)} 个数据列")
        
        # 显示布尔列信息
        if boolean_columns:
            print(f"[INFO] 布尔列 ({len(boolean_columns)} 个): {', '.join(boolean_columns.keys())}")
        
        # 创建复合索引 (stock_code, date)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name='idx_daily_kline_analysis'
            """)
            if not cursor.fetchone():
                create_index_sql = """
                CREATE INDEX idx_daily_kline_analysis 
                ON hk_daily_kline_analysis (stock_code, date)
                """
                conn.execute(create_index_sql)
                print(f"[INFO] 已创建复合索引 idx_daily_kline_analysis")
            else:
                print(f"[INFO] 复合索引 idx_daily_kline_analysis 已存在")
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
        if table_exists(conn, 'hk_daily_kline_analysis'):
            conn.execute("DROP TABLE hk_daily_kline_analysis")
            print("[INFO] 已删除旧表 hk_daily_kline_analysis")
        
        # 创建新表
        if create_table_if_not_exists(conn):
            print("[INFO] 已重新创建表 hk_daily_kline_analysis")
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
    自动检测并转换布尔类型列
    """
    try:
        # 读取CSV文件
        df = pd.read_csv(csv_path)
        
        # 清理列名（替换%为Pct）
        df.columns = [clean_column_name(col) for col in df.columns]
        
        # 检测并转换布尔列
        boolean_converted = []
        for col in df.columns:
            # 跳过基础列
            if col in ['stock_code', 'stock_name', 'date']:
                continue
            
            # 检测是否为布尔列
            try:
                is_bool, bool_values = detect_boolean_column(df[col])
                if is_bool and bool_values is not None:
                    # 确保所有值都转换为整数 (1=True, 0=False)
                    # 处理可能的NaN值，将其转换为False
                    bool_values = bool_values.fillna(False)
                    # 转换为整数
                    df[col] = bool_values.astype(int)
                    boolean_converted.append(col)
                    print(f"   🔄 转换列 '{col}' 为布尔类型 (INTEGER: 1=True, 0=False)")
            except Exception as e:
                print(f"   ⚠️ 检测列 '{col}' 时出错: {e}")
                continue
        
        if boolean_converted:
            print(f"   ✅ 共转换 {len(boolean_converted)} 列为布尔类型: {', '.join(boolean_converted)}")
        
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
        
        # 添加 stock_code 和 stock_name 在最前面
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
        
        # 处理可能的空值
        df_new['stock_code'] = df_new['stock_code'].fillna(stock_code).astype(str)
        df_new['stock_name'] = df_new['stock_name'].fillna(stock_name).astype(str)
        df_new['date'] = df_new['date'].astype(str)
        
        # 对于布尔列，确保值为整数 (0 或 1)
        for col in boolean_converted:
            if col in df_new.columns:
                # 先填充NaN为0，然后转换为整数
                df_new[col] = df_new[col].fillna(0)
                # 确保所有值都是0或1
                df_new[col] = df_new[col].astype(int)
                # 再次确保值在0和1之间
                df_new[col] = df_new[col].apply(lambda x: 1 if x > 0 else 0)
                print(f"   ✅ 布尔列 '{col}' 已转换为整数类型 (值范围: {df_new[col].min()} - {df_new[col].max()})")
        
        # 导入数据
        df_new.to_sql('hk_daily_kline_analysis', conn, if_exists='append', index=False)
        
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
# 4. 创建数据字典（从数据库表结构生成）
# =====================================================

def create_data_dictionary(conn, csv_files):
    """
    创建完整的数据字典 hk_daily_kline_analysis.json
    从数据库表结构生成字段定义，确保与数据库完全一致
    """
    print("\n" + "-"*60)
    print("创建数据字典...")
    print("-"*60)
    
    if not csv_files:
        print(f"[WARN] 未找到CSV文件，无法创建数据字典")
        return
    
    # 检查表是否存在
    if not table_exists(conn, 'hk_daily_kline_analysis'):
        print(f"[WARN] 表 hk_daily_kline_analysis 不存在，无法创建数据字典")
        return
    
    try:
        cursor = conn.cursor()
        
        # 从数据库获取表结构
        cursor.execute("PRAGMA table_info(hk_daily_kline_analysis)")
        table_columns = cursor.fetchall()
        
        # 获取表的总记录数
        cursor.execute("SELECT COUNT(*) FROM hk_daily_kline_analysis")
        total_records = cursor.fetchone()[0]
        
        # 获取每个股票的记录数
        cursor.execute("""
            SELECT stock_code, stock_name, COUNT(*) as count
            FROM hk_daily_kline_analysis
            GROUP BY stock_code, stock_name
            ORDER BY stock_code
        """)
        stocks_loaded = cursor.fetchall()
        
        # 获取日期范围
        cursor.execute("""
            SELECT MIN(date), MAX(date)
            FROM hk_daily_kline_analysis
            WHERE date IS NOT NULL AND date != ''
        """)
        min_date, max_date = cursor.fetchone()
        
        # 获取示例数据（用于推断字段描述）
        cursor.execute("SELECT * FROM hk_daily_kline_analysis LIMIT 1")
        sample_row = cursor.fetchone()
        
        # 获取示例数据的列名
        column_names = [col[1] for col in table_columns]
        
        # 技术指标字段描述映射
        field_descriptions = {
            'open': '开盘价',
            'high': '最高价',
            'low': '最低价',
            'close': '收盘价',
            'adjclose': '调整后收盘价（考虑分红、拆股等）',
            'volume': '成交量（股数）',
            'amount': '成交金额',
            'turnover': '换手率（%）',
            'turnover_rate': '换手率（%）',
            'amplitude': '振幅（%）',
            'ma5': '5日移动平均线',
            'ma10': '10日移动平均线',
            'ma20': '20日移动平均线',
            'ma30': '30日移动平均线',
            'ma60': '60日移动平均线',
            'ma120': '120日移动平均线',
            'ma250': '250日移动平均线',
            'ema5': '5日指数移动平均线',
            'ema8': '8日指数移动平均线',
            'ema10': '10日指数移动平均线',
            'ema12': '12日指数移动平均线',
            'ema13': '13日指数移动平均线',
            'ema20': '20日指数移动平均线',
            'ema21': '21日指数移动平均线',
            'ema26': '26日指数移动平均线',
            'ema30': '30日指数移动平均线',
            'ema34': '34日指数移动平均线',
            'ema50': '50日指数移动平均线',
            'ema60': '60日指数移动平均线',
            'ema63': '63日指数移动平均线',
            'ema100': '100日指数移动平均线',
            'ema120': '120日指数移动平均线',
            'ema200': '200日指数移动平均线',
            'ema250': '250日指数移动平均线',
            'rsi6': '6日相对强弱指标(RSI)',
            'rsi14': '14日相对强弱指标(RSI)',
            'rsi24': '24日相对强弱指标(RSI)',
            'macd_dif': 'MACD指标值',
            'macd_signal': 'MACD信号线',
            'macd_histogram': 'MACD柱状线',
            'kdj_k': 'KDJ指标K值',
            'kdj_d': 'KDJ指标D值',
            'kdj_j': 'KDJ指标J值',
            'bollinger_upper': '布林带上轨',
            'bollinger_middle': '布林带中轨',
            'bollinger_lower': '布林带下轨',
            'atr14': '平均真实波幅(ATR)',
            'adx14': '平均趋向指数(ADX)',
            'obv': '能量潮(OBV)',
            'vwap': '成交量加权平均价',
            'parabolicsar': '抛物线转向指标',
            'mfi': '资金流量指标',
            'cci14': '顺势指标(CCI)',
            'williamsr': '威廉指标',
        }
        
        # 构建字段定义
        field_definitions = []
        
        for idx, col_info in enumerate(table_columns):
            col_name = col_info[1]
            col_type = col_info[2]
            is_nullable = not col_info[3]
            is_pk = col_info[5] == 1
            
            # 获取示例值
            sample_value = sample_row[idx] if sample_row and idx < len(sample_row) else None
            
            # 判断是否为布尔列（存储为INTEGER且值只有0和1）
            is_boolean = False
            if col_type.upper() == 'INTEGER':
                try:
                    cursor.execute(f"SELECT DISTINCT {col_name} FROM hk_daily_kline_analysis WHERE {col_name} IN (0, 1) LIMIT 2")
                    bool_values = cursor.fetchall()
                    if len(bool_values) <= 2:
                        cursor.execute(f"SELECT COUNT(*) FROM hk_daily_kline_analysis WHERE {col_name} NOT IN (0, 1) AND {col_name} IS NOT NULL")
                        other_values = cursor.fetchone()[0]
                        if other_values == 0:
                            is_boolean = True
                except:
                    pass
            
            # 确定字段类型描述
            if is_boolean:
                field_type_display = 'INTEGER (BOOLEAN)'
                description = f'{col_name} (布尔值: 1=True, 0=False)'
            elif is_pk:
                field_type_display = 'INTEGER'
                description = '自增主键'
            else:
                field_type_display = col_type
                
                # 查找匹配的描述
                description = None
                col_lower = col_name.lower()
                
                # 精确匹配
                if col_lower in field_descriptions:
                    description = field_descriptions[col_lower]
                else:
                    # 部分匹配
                    for key, desc in field_descriptions.items():
                        if key in col_lower or col_lower in key:
                            description = desc
                            break
                
                if description is None:
                    # 自动生成描述
                    if 'pct' in col_lower or '_pct' in col_lower:
                        description = f'{col_name} (百分比)'
                    elif any(kw in col_lower for kw in ['ma', 'ema']):
                        description = f'{col_name} (移动平均线)'
                    elif any(kw in col_lower for kw in ['rsi', 'macd', 'kdj', 'boll', 'atr', 'adx', 'mfi', 'cci']):
                        description = f'{col_name} (技术指标)'
                    elif 'status' in col_lower:
                        description = f'{col_name} (状态)'
                    elif 'streak' in col_lower:
                        description = f'{col_name} (连续天数)'
                    elif 'cond' in col_lower:
                        description = f'{col_name} (条件)'
                    elif 'signal' in col_lower:
                        description = f'{col_name} (信号)'
                    elif 'cross' in col_lower:
                        description = f'{col_name} (交叉)'
                    elif 'triangle' in col_lower:
                        description = f'{col_name} (三角形态)'
                    elif 'concentration' in col_lower:
                        description = f'{col_name} (筹码集中度)'
                    else:
                        description = f'原始字段: {col_name}'
            
            # 检查空值
            try:
                cursor.execute(f"SELECT COUNT(*) FROM hk_daily_kline_analysis WHERE {col_name} IS NULL OR {col_name} = ''")
                null_count = cursor.fetchone()[0]
            except:
                null_count = 0
            
            field_def = {
                'name': col_name,
                'original_name': col_name,
                'type': field_type_display,
                'description': description,
                'constraint': 'NOT NULL' if not is_nullable else '',
                'null_count': null_count,
                'sample_value': str(sample_value) if sample_value is not None else '',
                'example': '',
                'is_key': is_pk,
                'is_required': not is_nullable
            }
            
            field_definitions.append(field_def)
        
        # 构建数据字典
        data_dict = {
            'metadata': {
                'table_name': 'hk_daily_kline_analysis',
                'description': '港股日K线技术分析数据表',
                'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'version': '2.0',
                'database': str(DB_PATH.name),
                'data_source': 'CSV files from Data directory',
                'total_files': len(csv_files),
                'total_stocks': len(STOCK_LIST),
                'total_records': total_records,
                'date_range': {
                    'earliest': min_date if min_date else None,
                    'latest': max_date if max_date else None
                }
            },
            'table_schema': {
                'primary_key': 'id',
                'columns': [
                    {
                        'name': field['name'],
                        'type': field['type'],
                        'description': field['description'],
                        'is_key': field['is_key']
                    }
                    for field in field_definitions
                ],
                'indexes': [
                    {
                        'name': 'idx_daily_kline_analysis',
                        'fields': ['stock_code', 'date'],
                        'type': '复合索引',
                        'description': '用于快速查询特定股票的日K线分析数据'
                    }
                ],
                'constraints': [
                    'PRIMARY KEY (id)',
                    'UNIQUE (stock_code, date)'
                ]
            },
            'stock_list': STOCK_LIST,
            'data_statistics': {
                'total_records': total_records,
                'stocks_loaded': [
                    {
                        'code': code,
                        'name': name,
                        'record_count': count
                    }
                    for code, name, count in stocks_loaded
                ],
                'date_range': {
                    'earliest': min_date if min_date else None,
                    'latest': max_date if max_date else None
                }
            },
            'usage_examples': {
                'query_all': "SELECT * FROM hk_daily_kline_analysis LIMIT 10;",
                'query_by_stock': "SELECT * FROM hk_daily_kline_analysis WHERE stock_code = '01951' ORDER BY date;",
                'query_date_range': "SELECT * FROM hk_daily_kline_analysis WHERE date BETWEEN '2024-01-01' AND '2024-12-31';",
                'query_recent': "SELECT * FROM hk_daily_kline_analysis WHERE stock_code = '01951' ORDER BY date DESC LIMIT 10;"
            },
            'data_dictionary': {
                'column_definitions': field_definitions,
                'relationships': [
                    {
                        'type': '外键关联',
                        'table': 'hk_hist_daily_kline',
                        'field': ['stock_code', 'date'],
                        'description': '可通过股票代码和日期字段与日交易数据关联'
                    },
                    {
                        'type': '外键关联',
                        'table': 'hk_idx_hist',
                        'field': 'date',
                        'description': '可通过日期字段与港股指数数据关联'
                    }
                ],
                'business_rules': [
                    {
                        'rule': '每个股票每天只有一条分析记录',
                        'description': '数据按日期去重，同一股票在同一天只有一条技术分析数据'
                    },
                    {
                        'rule': '价格精度',
                        'description': '价格数据保留4位小数'
                    },
                    {
                        'rule': '技术指标精度',
                        'description': '技术指标数据保留4位小数'
                    },
                    {
                        'rule': '布尔类型转换',
                        'description': '自动检测并转换包含TRUE/FALSE值的列为布尔类型，存储为INTEGER (1=True, 0=False)'
                    }
                ]
            }
        }
        
        # 保存数据字典
        dict_path = project_dir / 'Config' / 'hk_daily_kline_analysis.json'
        try:
            # 备份旧文件
            if dict_path.exists():
                backup_path = dict_path.with_suffix('.json.bak')
                dict_path.rename(backup_path)
                print(f"[INFO] 已备份旧数据字典到: {backup_path}")
            
            with open(dict_path, 'w', encoding='utf-8') as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)
            
            print(f"[INFO] 数据字典已创建: {dict_path}")
            print(f"[INFO] 共 {len(field_definitions)} 个字段")
            
            # 显示摘要
            print("\n数据字典摘要:")
            print(f"   - 表名: {data_dict['metadata']['table_name']}")
            print(f"   - 字段数: {len(data_dict['data_dictionary']['column_definitions'])}")
            print(f"   - 股票数: {len(data_dict['data_statistics']['stocks_loaded'])}")
            print(f"   - 总记录数: {data_dict['data_statistics']['total_records']}")
            if data_dict['data_statistics']['date_range']['earliest']:
                print(f"   - 数据范围: {data_dict['data_statistics']['date_range']['earliest']} 至 {data_dict['data_statistics']['date_range']['latest']}")
            
        except Exception as e:
            print(f"[ERROR] 保存数据字典失败: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"[ERROR] 创建数据字典失败: {e}")
        import traceback
        traceback.print_exc()

# =====================================================
# 5. 主函数
# =====================================================

def main():
    print("\n" + "="*60)
    print("导入日K线分析数据到 SQLite 数据库")
    print("="*60 + "\n")
    
    # 获取所有CSV文件
    csv_files = list(DATA_DIR.glob("*_daily_technical_analysis.csv"))
    
    if not csv_files:
        print(f"[ERROR] 在 {DATA_DIR} 中未找到 *_daily_technical_analysis.csv 文件")
        print(f"[INFO] 请确认数据文件路径是否正确")
        return
    
    print(f"[INFO] 找到 {len(csv_files)} 个CSV文件:")
    for f in csv_files:
        print(f"   - {f.name}")
    
    # 连接数据库
    conn = get_db_connection()
    
    try:
        # 检查表是否存在
        if table_exists(conn, 'hk_daily_kline_analysis'):
            existing_count = conn.execute("SELECT COUNT(*) FROM hk_daily_kline_analysis").fetchone()[0]
            if existing_count > 0:
                print(f"\n[WARN] 表 hk_daily_kline_analysis 中已有 {existing_count} 条记录")
                print("选项:")
                print("  1. 删除表并重新创建 (d) - 将创建新表结构（stock_code在前）")
                print("  2. 清空现有数据并重新导入 (y)")
                print("  3. 保留现有数据，追加新数据 (n)")
                response = input("请选择 (d/y/n): ").strip().lower()
                
                if response == 'd':
                    if not recreate_table(conn):
                        print("[ERROR] 重新创建表失败")
                        return
                elif response == 'y' or response == 'yes':
                    clear_table(conn, 'hk_daily_kline_analysis')
                    print("[INFO] 已清空旧数据")
                else:
                    print("[INFO] 保留现有数据，将追加新数据")
            else:
                # 表存在但没有数据，检查表结构是否正确
                print("[INFO] 表存在但没有数据，检查表结构...")
                # 获取表结构
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(hk_daily_kline_analysis)")
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
        if table_exists(conn, 'hk_daily_kline_analysis'):
            count = conn.execute("SELECT COUNT(*) FROM hk_daily_kline_analysis").fetchone()[0]
            print(f"\n📋 表 hk_daily_kline_analysis 当前共有 {count} 条记录")
            
            # 显示表结构
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(hk_daily_kline_analysis)")
            columns = cursor.fetchall()
            print(f"📋 表结构（字段顺序）:")
            for i, col in enumerate(columns, 1):
                col_name = col[1]
                col_type = col[2]
                not_null = 'NOT NULL' if col[3] else ''
                # 标记关键字段
                if col_name in ['stock_code', 'stock_name', 'date']:
                    print(f"   {i}. {col_name} ({col_type}) {not_null} ⭐")
                else:
                    print(f"   {i}. {col_name} ({col_type}) {not_null}")
            
            # 显示索引
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='hk_daily_kline_analysis'")
            indexes = cursor.fetchall()
            if indexes:
                print(f"\n📋 索引:")
                for idx_name, idx_sql in indexes:
                    print(f"   - {idx_name}")
            
            # 显示股票统计
            stocks = conn.execute(
                "SELECT DISTINCT stock_code, stock_name FROM hk_daily_kline_analysis ORDER BY stock_code"
            ).fetchall()
            print(f"\n📈 包含 {len(stocks)} 只股票的数据:")
            for code, name in stocks:
                cnt = conn.execute(
                    f"SELECT COUNT(*) FROM hk_daily_kline_analysis WHERE stock_code='{code}'"
                ).fetchone()[0]
                # 检查是否在配置文件中
                in_config = "✓" if code in STOCK_MAP else "⚠️"
                print(f"   {in_config} {code} {name}: {cnt} 条记录")
        
        # 创建数据字典（从数据库表结构生成）
        create_data_dictionary(conn, csv_files)
        
    except Exception as e:
        print(f"\n[ERROR] 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    main()