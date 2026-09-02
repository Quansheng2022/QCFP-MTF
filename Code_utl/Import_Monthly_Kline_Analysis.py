#!/usr/bin/env python
# coding: utf-8

"""
Import_Monthly_Kline_Analysis.py
将月K线技术分析数据CSV文件导入SQLite数据库
从CSV文件解析股票代码，匹配股票名称，创建hk_monthly_kline_analysis表

脚本位置: TA_Workflow2/Code_utl/Import_Monthly_Kline_Analysis.py
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
# 1. 路径设置
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
# 3. 布尔类型列定义
# =====================================================

# 定义需要转换为布尔类型的列
BOOLEAN_COLUMNS = {
    'EMA_Golden_Cross': 'EMA金叉信号',
    'EMA_Death_Cross': 'EMA死叉信号',
    'Golden_Triangle': '黄金三角形信号',
    'Death_Triangle': '死亡三角形信号',
    'MACD_Golden_Cross': 'MACD金叉信号',
    'MACD_Death_Cross': 'MACD死叉信号',
    'bottom_signal_cond': '底部信号条件',
    'top_signal_cond': '顶部信号条件',
    'bottom_entry_signal_cond': '底部入场信号条件',
    'top_exit_signal_cond': '顶部出场信号条件',
    'continuation_signal_cond': '持续信号条件',
    'decline_continuation_cond': '下跌持续条件',
    'accumulation_cond': '积累条件',
    'distribution_cond': '分配条件',
    'multi_timeframe_chip_confirm_bottom_cond': '多周期筹码确认底部条件',
    'multi_timeframe_chip_confirm_top_cond': '多周期筹码确认顶部条件'
}

def is_boolean_column(col_name):
    """检查列名是否属于布尔类型列"""
    return col_name in BOOLEAN_COLUMNS

def get_boolean_description(col_name):
    """获取布尔列的描述"""
    return BOOLEAN_COLUMNS.get(col_name, f'{col_name} (布尔信号)')

def convert_to_boolean_value(value):
    """
    将各种格式的值转换为布尔值
    支持: True/False, 1/0, 'True'/'False', 'true'/'false', 'Y'/'N', 'Yes'/'No'
    """
    if pd.isna(value):
        return None
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, (int, float)):
        return bool(value)
    
    if isinstance(value, str):
        value_lower = value.strip().lower()
        if value_lower in ('true', '1', 'yes', 'y', 't'):
            return True
        elif value_lower in ('false', '0', 'no', 'n', 'f'):
            return False
    
    # 尝试转换为数值
    try:
        return bool(float(value))
    except (ValueError, TypeError):
        return None

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

def clean_column_name(col_name):
    """
    清理列名：将含有%符号的列名改成 ...Pct
    例如: Close_Chg% => Close_ChgPct
    """
    col_name = col_name.strip()
    # 替换 % 为 Pct
    if '%' in col_name:
        col_name = col_name.replace('%', 'Pct')
    # 替换其他特殊字符
    col_name = col_name.replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
    col_name = col_name.replace('-', '_').replace('+', '_')
    return col_name

def create_table_if_not_exists(conn):
    """
    创建 hk_monthly_kline_analysis 表（如果不存在）
    将 stock_code 和 stock_name 放在最前面
    创建复合索引 (stock_code, date)
    支持布尔类型列
    """
    # 读取CSV文件样例来获取列结构
    csv_files = list(DATA_DIR.glob("*_monthly_TA_indicators.csv"))
    if not csv_files:
        print(f"[ERROR] 未找到任何 *_monthly_TA_indicators.csv 文件")
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
        
        # 添加其他列（排除可能的date列）
        for col in df_sample.columns:
            col_clean = clean_column_name(col)
            
            # 如果是date列，跳过（我们已经添加了date字段）
            if 'date' in col.lower() or 'Date' in col.lower():
                continue
            
            # 检查是否为布尔类型列
            if is_boolean_column(col_clean):
                col_type = 'INTEGER'  # SQLite使用INTEGER存储布尔值 (0/1)
            else:
                # 根据列名和数据类型选择合适的SQLite类型
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in ['close', 'open', 'high', 'low', 'adj']):
                    col_type = 'REAL'
                elif 'volume' in col_lower or 'amount' in col_lower or 'turnover' in col_lower:
                    col_type = 'REAL'
                elif 'amplitude' in col_lower or 'change' in col_lower or 'pct' in col_lower:
                    col_type = 'REAL'
                elif 'rsi' in col_lower or 'macd' in col_lower or 'kdj' in col_lower:
                    col_type = 'REAL'
                elif 'ma' in col_lower:
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
        CREATE TABLE IF NOT EXISTS hk_monthly_kline_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(columns)}
        )
        """
        
        conn.execute(create_sql)
        print(f"[INFO] 表 hk_monthly_kline_analysis 已创建或已存在")
        
        # 创建复合索引 (stock_code, date)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name='idx_monthly_kline_analysis'
            """)
            if not cursor.fetchone():
                create_index_sql = """
                CREATE INDEX idx_monthly_kline_analysis 
                ON hk_monthly_kline_analysis (stock_code, date)
                """
                conn.execute(create_index_sql)
                print(f"[INFO] 已创建复合索引 idx_monthly_kline_analysis")
            else:
                print(f"[INFO] 复合索引 idx_monthly_kline_analysis 已存在")
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
        if table_exists(conn, 'hk_monthly_kline_analysis'):
            conn.execute("DROP TABLE hk_monthly_kline_analysis")
            print("[INFO] 已删除旧表 hk_monthly_kline_analysis")
        
        # 创建新表
        if create_table_if_not_exists(conn):
            print("[INFO] 已重新创建表 hk_monthly_kline_analysis")
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
    处理列名中的%符号
    处理布尔类型转换
    """
    try:
        # 读取CSV文件
        df = pd.read_csv(csv_path)
        
        # 清理列名（将%替换为Pct）
        df.columns = [clean_column_name(col) for col in df.columns]
        
        # 转换布尔类型列
        for col in df.columns:
            if is_boolean_column(col):
                df[col] = df[col].apply(convert_to_boolean_value)
                # 将布尔值转换为整数 (0/1) 以便在SQLite中存储
                df[col] = df[col].astype('Int64')  # 使用Int64支持Nullable整数
        
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
        
        # 数值列四舍五入（只处理非布尔列）
        for col in df_new.select_dtypes(include=['float64', 'float32']).columns:
            if col not in ['stock_code', 'stock_name'] and not is_boolean_column(col):
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
        df_new.to_sql('hk_monthly_kline_analysis', conn, if_exists='append', index=False)
        
        print(f"   ✅ 已导入 {len(df_new)} 条记录")
        
        # 统计布尔列的值分布
        boolean_cols = [col for col in df_new.columns if is_boolean_column(col)]
        if boolean_cols:
            print(f"   📊 布尔列统计:")
            for col in boolean_cols:
                true_count = (df_new[col] == 1).sum()
                false_count = (df_new[col] == 0).sum()
                null_count = df_new[col].isna().sum()
                print(f"      - {col}: True={true_count}, False={false_count}, Null={null_count}")
        
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
# 5. 创建数据字典
# =====================================================

def detect_boolean_column(conn, col_name):
    """
    检测列是否为布尔类型
    检查列中是否只包含 0/1 或 True/False 值
    """
    try:
        cursor = conn.cursor()
        query = f"""
        SELECT DISTINCT "{col_name}" 
        FROM hk_monthly_kline_analysis 
        WHERE "{col_name}" IS NOT NULL 
        LIMIT 100
        """
        cursor.execute(query)
        values = [row[0] for row in cursor.fetchall()]
        
        # 检查是否都是 0 或 1
        all_binary = all(v in (0, 1, 0.0, 1.0, '0', '1', 'True', 'False', 'true', 'false') for v in values)
        
        if all_binary and len(values) <= 2:
            return True
        
        # 检查列名是否在预定义列表中
        return is_boolean_column(col_name)
        
    except Exception as e:
        print(f"   ⚠️ 检测布尔列 {col_name} 时出错: {e}")
        return is_boolean_column(col_name)

def get_field_description(col_name):
    """获取字段描述"""
    descriptions = {
        'id': '自增主键',
        'stock_code': '股票代码（5位数字）',
        'stock_name': '股票名称',
        'date': '交易日期（YYYY-MM-DD格式）',
        'close': '月收盘价',
        'open': '月开盘价',
        'high': '月最高价',
        'low': '月最低价',
        'volume': '月成交量',
        'amount': '月成交金额',
        'turnover': '月换手率',
        'amplitude': '月振幅',
        'change': '月涨跌幅',
        'pct_chg': '月涨跌幅百分比',
        'close_chg': '月收盘价变化',
        'close_chgpct': '月收盘价变化百分比',
        'rsi': '相对强弱指标 (RSI) - 月线',
        'macd': 'MACD指标 - 月线',
        'macd_signal': 'MACD信号线 - 月线',
        'macd_hist': 'MACD柱状图 - 月线',
        'kdj_k': 'KDJ指标K值 - 月线',
        'kdj_d': 'KDJ指标D值 - 月线',
        'kdj_j': 'KDJ指标J值 - 月线',
        'boll_upper': '布林带上轨 - 月线',
        'boll_mid': '布林带中轨 - 月线',
        'boll_lower': '布林带下轨 - 月线',
        'ma5': '5月移动平均线',
        'ma10': '10月移动平均线',
        'ma20': '20月移动平均线',
        'ma30': '30月移动平均线',
        'ma60': '60月移动平均线',
        'ma120': '120月移动平均线',
        'ma250': '250月移动平均线'
    }
    
    # 检查是否为布尔列
    if is_boolean_column(col_name):
        return get_boolean_description(col_name)
    
    # 查找匹配的描述
    for key, desc in descriptions.items():
        if key in col_name.lower() or col_name.lower() in key:
            return desc
    
    # 尝试从列名推断
    col_lower = col_name.lower()
    if 'pct' in col_lower:
        return f'{col_name} (百分比)'
    elif 'ma' in col_lower:
        return f'{col_name} 移动平均线'
    elif 'std' in col_lower:
        return f'{col_name} 标准差'
    else:
        return f'技术指标: {col_name}'

def get_sample_value(conn, col_name):
    """获取列示例值"""
    try:
        cursor = conn.cursor()
        query = f'SELECT "{col_name}" FROM hk_monthly_kline_analysis WHERE "{col_name}" IS NOT NULL LIMIT 1'
        cursor.execute(query)
        result = cursor.fetchone()
        return str(result[0]) if result and result[0] is not None else ''
    except Exception as e:
        print(f"   ⚠️ 获取示例值失败 ({col_name}): {e}")
        return ''

def get_null_count(conn, col_name):
    """获取列空值数量"""
    try:
        cursor = conn.cursor()
        query = f'SELECT COUNT(*) FROM hk_monthly_kline_analysis WHERE "{col_name}" IS NULL OR "{col_name}" = ""'
        cursor.execute(query)
        return cursor.fetchone()[0]
    except Exception as e:
        print(f"   ⚠️ 获取空值数量失败 ({col_name}): {e}")
        return 0

def create_data_dictionary(conn):
    """
    创建完整的数据字典 hk_monthly_kline_analysis.json
    如果数据字典文件已经存在，则添加新的数据字典
    包含表结构、字段说明、数据类型、约束、统计信息等
    自动检测布尔列并生成正确的类型信息
    """
    print("\n" + "-"*60)
    print("创建数据字典...")
    
    # 数据字典文件路径
    dict_path = project_dir / 'Config' / 'hk_monthly_kline_analysis.json'
    
    # 检查文件是否存在
    existing_dict = None
    if dict_path.exists():
        try:
            with open(dict_path, 'r', encoding='utf-8') as f:
                existing_dict = json.load(f)
            print(f"[INFO] 已存在数据字典文件: {dict_path}")
        except Exception as e:
            print(f"[WARN] 读取现有数据字典失败: {e}")
    
    # 验证表是否存在
    if not table_exists(conn, 'hk_monthly_kline_analysis'):
        print("[ERROR] 表 hk_monthly_kline_analysis 不存在")
        return
    
    # 获取表结构
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(hk_monthly_kline_analysis)")
    table_columns = cursor.fetchall()
    
    # 获取总记录数
    try:
        cursor.execute("SELECT COUNT(*) FROM hk_monthly_kline_analysis")
        total_records = cursor.fetchone()[0]
    except Exception as e:
        print(f"   ⚠️ 获取总记录数失败: {e}")
        total_records = 0
    
    # 获取CSV文件列表用于补充信息
    csv_files = list(DATA_DIR.glob("*_monthly_TA_indicators.csv"))
    file_info = []
    
    for csv_file in csv_files[:5]:  # 只读取前5个文件用于示例
        try:
            df = pd.read_csv(csv_file)
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
                'date_range': {
                    'start': df[date_col].iloc[0] if date_col else None,
                    'end': df[date_col].iloc[-1] if date_col else None
                }
            })
        except Exception as e:
            print(f"   ⚠️ 读取 {csv_file.name} 失败: {e}")
    
    # 获取股票信息
    stock_info_map = {}
    if table_exists(conn, 'hk_monthly_kline_analysis'):
        try:
            cursor.execute("SELECT DISTINCT stock_code FROM hk_monthly_kline_analysis")
            codes = [row[0] for row in cursor.fetchall()]
            for code in codes:
                stock_info = STOCK_MAP.get(code, {})
                stock_info_map[code] = {
                    'code': code,
                    'name': stock_info.get('name', f'股票_{code}'),
                    'sector': stock_info.get('sector', 'N/A'),
                    'market': stock_info.get('market', 'HKEX')
                }
        except Exception as e:
            print(f"   ⚠️ 获取股票信息失败: {e}")
    
    # 构建数据字典
    data_dict = {
        'metadata': {
            'table_name': 'hk_monthly_kline_analysis',
            'description': '港股月K线技术分析数据表',
            'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '2.1',  # 版本升级以正确处理布尔类型
            'database': str(DB_PATH.name),
            'data_source': 'CSV files from Data directory',
            'total_files': len(csv_files),
            'total_stocks': len(stock_info_map),
        },
        'table_schema': {
            'primary_key': 'id',
            'columns': [],
            'indexes': [
                {
                    'name': 'idx_monthly_kline_analysis',
                    'fields': ['stock_code', 'date'],
                    'type': '复合索引',
                    'description': '用于快速查询特定股票的月K线技术分析数据'
                }
            ],
            'constraints': [
                'PRIMARY KEY (id)',
                'UNIQUE (stock_code, date)'
            ]
        },
        'stock_list': stock_info_map,
        'data_statistics': {
            'total_records': total_records,
            'stocks_loaded': [],
            'date_range': {
                'earliest': None,
                'latest': None
            },
            'boolean_columns': {
                'count': 0,
                'columns': [],
                'storage_info': '布尔值存储为INTEGER类型 (0=False, 1=True)'
            }
        },
        'field_definitions': [],
        'usage_examples': {
            'query_all': "SELECT * FROM hk_monthly_kline_analysis LIMIT 10;",
            'query_by_stock': "SELECT * FROM hk_monthly_kline_analysis WHERE stock_code = '01951' ORDER BY date;",
            'query_date_range': "SELECT * FROM hk_monthly_kline_analysis WHERE date BETWEEN '2024-01-01' AND '2024-12-31';",
            'query_ta_indicators': "SELECT stock_code, stock_name, date, Close, RSI, MACD FROM hk_monthly_kline_analysis WHERE stock_code = '01951';",
            'query_boolean_signal': "SELECT stock_code, stock_name, date, Golden_Triangle, Death_Triangle FROM hk_monthly_kline_analysis WHERE Golden_Triangle = 1;",
            'query_with_index': "SELECT * FROM hk_monthly_kline_analysis WHERE stock_code = '01951' AND date = '2024-01-01';"
        },
        'data_dictionary': {
            'column_definitions': [],
            'relationships': [],
            'business_rules': [],
            'boolean_column_mapping': {},
            'type_mapping_notes': {
                'boolean': '布尔列在SQLite中存储为INTEGER类型 (0=False, 1=True)',
                'numeric': '数值列存储为REAL类型，保留4位小数',
                'text': '文本列存储为TEXT类型'
            }
        }
    }
    
    # 构建字段定义
    field_definitions = []
    boolean_cols = []
    
    for col in table_columns:
        col_id, col_name, col_type, notnull, default_val, is_pk = col
        
        # 检测是否为布尔列
        is_boolean = detect_boolean_column(conn, col_name)
        
        # 获取描述
        description = get_field_description(col_name)
        
        # 获取统计信息
        null_count = get_null_count(conn, col_name)
        sample_value = get_sample_value(conn, col_name)
        
        # ===== 关键修复：确保布尔列使用 INTEGER 类型 =====
        # 如果是布尔列，强制使用 INTEGER 作为实际类型
        if is_boolean:
            # 布尔列在SQLite中存储为INTEGER
            # 使用 'INTEGER' 作为实际类型，'BOOLEAN' 作为逻辑类型
            actual_type = 'INTEGER'
            logical_type = 'BOOLEAN'
        else:
            actual_type = col_type
            logical_type = col_type
        # ================================================
        
        # 构建字段定义
        field_def = {
            'name': col_name,
            'type': actual_type,  # 使用实际数据库类型 (INTEGER)
            'logical_type': logical_type,  # 逻辑类型 (BOOLEAN)
            'sqlite_type': col_type,  # 数据库中的原始类型
            'description': description,
            'is_boolean': is_boolean,
            'is_key': (col_id == 0),
            'is_required': bool(notnull),
            'null_count': null_count,
            'sample_value': sample_value,
            'default_value': default_val,
            'constraints': [],
            'storage_hint': '存储为0/1（False/True）' if is_boolean else None,
            'notes': '布尔列使用INTEGER类型存储' if is_boolean else None
        }
        
        if is_boolean:
            # 获取布尔列的值分布
            try:
                cursor.execute(f"""
                    SELECT 
                        COUNT(CASE WHEN "{col_name}" = 1 THEN 1 END) as true_count,
                        COUNT(CASE WHEN "{col_name}" = 0 THEN 1 END) as false_count,
                        COUNT(CASE WHEN "{col_name}" IS NULL THEN 1 END) as null_count
                    FROM hk_monthly_kline_analysis
                """)
                true_count, false_count, null_count_stats = cursor.fetchone()
                
                # 确保值不为None
                true_count = true_count or 0
                false_count = false_count or 0
                null_count_stats = null_count_stats or 0
                total_valid = true_count + false_count
                
                field_def['boolean_stats'] = {
                    'true_count': true_count,
                    'false_count': false_count,
                    'null_count': null_count_stats,
                    'true_percentage': f"{(true_count / total_records * 100):.2f}%" if total_records > 0 else "0%",
                    'false_percentage': f"{(false_count / total_records * 100):.2f}%" if total_records > 0 else "0%",
                    'null_percentage': f"{(null_count_stats / total_records * 100):.2f}%" if total_records > 0 else "0%",
                    'true_ratio': f"{true_count}/{total_valid}" if total_valid > 0 else "0/0"
                }
                boolean_cols.append(col_name)
            except Exception as e:
                print(f"   ⚠️ 获取布尔列统计失败 ({col_name}): {e}")
                field_def['boolean_stats'] = {
                    'true_count': 0,
                    'false_count': 0,
                    'null_count': 0,
                    'true_percentage': '0%',
                    'false_percentage': '0%',
                    'null_percentage': '0%',
                    'true_ratio': '0/0'
                }
        
        field_definitions.append(field_def)
        
        # 更新table_schema中的columns - 使用实际类型
        data_dict['table_schema']['columns'].append({
            'name': col_name,
            'type': actual_type,  # 使用实际类型 (INTEGER)
            'logical_type': logical_type,  # 逻辑类型 (BOOLEAN)
            'description': description,
            'is_boolean': is_boolean,
            'is_key': (col_id == 0),
            'storage_hint': '存储为0/1' if is_boolean else None
        })
        
        # 更新data_statistics中的布尔列信息
        if is_boolean:
            data_dict['data_statistics']['boolean_columns']['count'] += 1
            data_dict['data_statistics']['boolean_columns']['columns'].append(col_name)
            data_dict['data_dictionary']['boolean_column_mapping'][col_name] = description
    
    # 获取数据库统计信息
    if table_exists(conn, 'hk_monthly_kline_analysis'):
        try:
            # 获取每个股票的记录数
            cursor.execute("""
                SELECT stock_code, stock_name, COUNT(*) as count
                FROM hk_monthly_kline_analysis
                GROUP BY stock_code, stock_name
                ORDER BY stock_code
            """)
            stocks_loaded = []
            for code, name, count in cursor.fetchall():
                stock_info = {
                    'code': code,
                    'name': name,
                    'record_count': count,
                    'details': STOCK_MAP.get(code, {})
                }
                stocks_loaded.append(stock_info)
            data_dict['data_statistics']['stocks_loaded'] = stocks_loaded
            
            # 日期范围
            cursor.execute("""
                SELECT MIN(date), MAX(date)
                FROM hk_monthly_kline_analysis
                WHERE date IS NOT NULL AND date != ''
            """)
            min_date, max_date = cursor.fetchone()
            data_dict['data_statistics']['date_range'] = {
                'earliest': min_date if min_date else None,
                'latest': max_date if max_date else None
            }
            
        except Exception as e:
            print(f"   ⚠️ 获取统计信息失败: {e}")
    
    # 添加字段定义到数据字典
    data_dict['data_dictionary']['column_definitions'] = field_definitions
    
    # 添加业务规则
    data_dict['data_dictionary']['business_rules'] = [
        {
            'rule': '数据唯一性',
            'description': '每个股票每月只有一条记录，通过 (stock_code, date) 唯一标识'
        },
        {
            'rule': '数据精度',
            'description': '所有数值数据保留4位小数'
        },
        {
            'rule': '技术指标完整性',
            'description': '包含月K线的基本技术指标：RSI, MACD, KDJ, 布林带, 移动平均线等'
        },
        {
            'rule': '索引优化',
            'description': '使用复合索引 (stock_code, date) 优化查询性能'
        },
        {
            'rule': '数据来源',
            'description': '数据从月K线技术分析CSV文件导入，文件命名格式：{stock_code}_monthly_TA_indicators.csv'
        },
        {
            'rule': '时间粒度',
            'description': '月线数据反映的是整月的交易情况，适合长期趋势分析'
        },
        {
            'rule': '布尔信号存储',
            'description': f'布尔信号列使用INTEGER类型存储 (0=False, 1=True)，共 {len(boolean_cols)} 个布尔信号列',
            'storage_details': 'SQLite没有原生BOOLEAN类型，因此使用INTEGER存储布尔值'
        }
    ]
    
    # 如果有布尔列，添加专门的布尔列业务规则
    if boolean_cols:
        data_dict['data_dictionary']['business_rules'].append({
            'rule': '布尔信号列列表',
            'description': f"以下列存储布尔信号值: {', '.join(boolean_cols)}",
            'values': '0表示False/无信号，1表示True/有信号，NULL表示缺失',
            'query_example': f"SELECT * FROM hk_monthly_kline_analysis WHERE {boolean_cols[0]} = 1;"
        })
        
        # 添加每个布尔列的详细说明
        for col in boolean_cols:
            data_dict['data_dictionary']['business_rules'].append({
                'rule': f'布尔列 - {col}',
                'description': data_dict['data_dictionary']['boolean_column_mapping'].get(col, col),
                'type': 'INTEGER (逻辑布尔)',
                'values': '0=False, 1=True, NULL=缺失',
                'storage': 'SQLite INTEGER类型'
            })
    
    # 添加关系说明
    data_dict['data_dictionary']['relationships'] = [
        {
            'type': '外键关联',
            'table': 'hk_hist_monthly_kline',
            'field': 'stock_code, date',
            'description': '可通过股票代码和日期与月K线历史数据关联'
        },
        {
            'type': '外键关联',
            'table': 'hk_hist_weekly_kline',
            'field': 'stock_code, date',
            'description': '可通过股票代码和日期与周K线历史数据关联'
        },
        {
            'type': '外键关联',
            'table': 'hk_hist_daily_kline',
            'field': 'stock_code, date',
            'description': '可通过股票代码和日期与日K线历史数据关联'
        },
        {
            'type': '外键关联',
            'table': 'macro_data_hist',
            'field': 'date',
            'description': '可通过日期字段与宏观数据关联'
        }
    ]
    
    # 如果有现有数据字典，合并更新
    if existing_dict:
        print("[INFO] 合并现有数据字典...")
        if 'metadata' in existing_dict and 'version' in existing_dict['metadata']:
            data_dict['metadata']['previous_version'] = existing_dict['metadata'].get('version', '1.0')
            data_dict['metadata']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 保存数据字典
    try:
        with open(dict_path, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 数据字典已创建: {dict_path}")
        print(f"[INFO] 数据字典大小: {len(json.dumps(data_dict))} 字节")
        
        # 显示数据字典摘要
        print("\n数据字典摘要:")
        print(f"   - 表名: {data_dict['metadata']['table_name']}")
        print(f"   - 版本: {data_dict['metadata']['version']}")
        print(f"   - 字段数: {len(data_dict['data_dictionary']['column_definitions'])}")
        print(f"   - 股票数: {len(data_dict['data_statistics']['stocks_loaded'])}")
        print(f"   - 总记录数: {data_dict['data_statistics']['total_records']:,}")
        if data_dict['data_statistics']['date_range']['earliest']:
            print(f"   - 数据范围: {data_dict['data_statistics']['date_range']['earliest']} 至 {data_dict['data_statistics']['date_range']['latest']}")
        print(f"   - 布尔列数: {data_dict['data_statistics']['boolean_columns']['count']}")
        print(f"   - 布尔列存储方式: INTEGER (0=False, 1=True)")
        
        if boolean_cols:
            print(f"\n   布尔信号列详细信息:")
            for col in boolean_cols:
                desc = get_boolean_description(col)
                # 查找对应的统计信息
                for field_def in field_definitions:
                    if field_def['name'] == col and 'boolean_stats' in field_def:
                        stats = field_def['boolean_stats']
                        print(f"      - {col} ({desc}):")
                        print(f"          True: {stats['true_count']:,} ({stats['true_percentage']})")
                        print(f"          False: {stats['false_count']:,} ({stats['false_percentage']})")
                        print(f"          Null: {stats['null_count']:,} ({stats['null_percentage']})")
                        print(f"          True/False 比例: {stats['true_ratio']}")
                        break
                else:
                    print(f"      - {col} ({desc})")
        
        print(f"\n   索引: {[idx['name'] for idx in data_dict['table_schema']['indexes']]}")
        
        # 显示技术指标字段
        tech_fields = [f for f in data_dict['data_dictionary']['column_definitions'] 
                      if f['name'] not in ['id', 'stock_code', 'stock_name', 'date'] and not f['is_boolean']]
        if tech_fields:
            print(f"\n   技术指标字段 (前10个):")
            for f in tech_fields[:10]:
                print(f"      - {f['name']} ({f['type']}): {f['description']}")
            if len(tech_fields) > 10:
                print(f"      ... 还有 {len(tech_fields) - 10} 个字段")
        
        # 显示类型映射说明
        print(f"\n   类型映射说明:")
        print(f"      - 布尔列: {data_dict['data_dictionary']['type_mapping_notes']['boolean']}")
        print(f"      - 数值列: {data_dict['data_dictionary']['type_mapping_notes']['numeric']}")
        print(f"      - 文本列: {data_dict['data_dictionary']['type_mapping_notes']['text']}")
        
    except Exception as e:
        print(f"[ERROR] 保存数据字典失败: {e}")
        import traceback
        traceback.print_exc()

# =====================================================
# 6. 主函数
# =====================================================

def main():
    print("\n" + "="*60)
    print("导入月K线技术分析数据到 SQLite 数据库")
    print("="*60 + "\n")
    
    # 获取所有CSV文件
    csv_files = list(DATA_DIR.glob("*_monthly_TA_indicators.csv"))
    
    if not csv_files:
        print(f"[ERROR] 在 {DATA_DIR} 中未找到 *_monthly_TA_indicators.csv 文件")
        print(f"[INFO] 请确认数据文件路径是否正确")
        return
    
    print(f"[INFO] 找到 {len(csv_files)} 个CSV文件:")
    for f in csv_files:
        print(f"   - {f.name}")
    
    # 连接数据库
    conn = get_db_connection()
    
    try:
        # 检查表是否存在
        if table_exists(conn, 'hk_monthly_kline_analysis'):
            existing_count = conn.execute("SELECT COUNT(*) FROM hk_monthly_kline_analysis").fetchone()[0]
            if existing_count > 0:
                print(f"\n[WARN] 表 hk_monthly_kline_analysis 中已有 {existing_count} 条记录")
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
                    clear_table(conn, 'hk_monthly_kline_analysis')
                    print("[INFO] 已清空旧数据")
                else:
                    print("[INFO] 保留现有数据，将追加新数据")
            else:
                # 表存在但没有数据，检查表结构是否正确
                print("[INFO] 表存在但没有数据，检查表结构...")
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(hk_monthly_kline_analysis)")
                columns = cursor.fetchall()
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
        if table_exists(conn, 'hk_monthly_kline_analysis'):
            count = conn.execute("SELECT COUNT(*) FROM hk_monthly_kline_analysis").fetchone()[0]
            print(f"\n📋 表 hk_monthly_kline_analysis 当前共有 {count} 条记录")
            
            # 显示表结构
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(hk_monthly_kline_analysis)")
            columns = cursor.fetchall()
            print(f"📋 表结构（字段顺序）:")
            for i, col in enumerate(columns, 1):
                col_name = col[1]
                col_type = col[2]
                is_boolean = is_boolean_column(col_name)
                type_display = 'BOOLEAN' if is_boolean else col_type
                print(f"   {i}. {col_name} ({type_display}) {'NOT NULL' if col[3] else ''}")
            
            # 显示索引
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='hk_monthly_kline_analysis'")
            indexes = cursor.fetchall()
            if indexes:
                print(f"\n📋 索引:")
                for idx_name, idx_sql in indexes:
                    print(f"   - {idx_name}")
            
            # 显示股票统计
            stocks = conn.execute(
                "SELECT DISTINCT stock_code, stock_name FROM hk_monthly_kline_analysis ORDER BY stock_code"
            ).fetchall()
            print(f"\n📈 包含 {len(stocks)} 只股票的月K线技术分析数据:")
            for code, name in stocks:
                cnt = conn.execute(
                    f"SELECT COUNT(*) FROM hk_monthly_kline_analysis WHERE stock_code='{code}'"
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