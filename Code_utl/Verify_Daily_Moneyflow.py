#!/usr/bin/env python
# coding: utf-8

"""
Verify_Daily_Moneyflow.py
数据验证程序 - 验证 hk_hist_daily_moneyflow 表的日资金流数据
功能:
  1. 检查表是否存在，显示表结构、记录数、日期范围等
  2. 显示每只股票的资金流统计
  3. 显示最新的5条记录（按日期升序）
  4. 检查数据完整性（空值、重复值等）
  5. 检查数据字典 hk_stock_daily_moneyflow_dictionary.json 是否存在及与表结构一致性
  6. 生成验证报告（文本和JSON）
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
        env_dir = os.environ.get('PROJECT_ROOT')
        if env_dir and Path(env_dir).exists():
            return Path(env_dir)

        script_path = Path(__file__).resolve()
        project_dir = script_path.parent

        if (project_dir / 'Config').exists():
            return project_dir

        if script_path.parent.name == 'Code_utl':
            return script_path.parent.parent

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

project_dir = get_project_dir()
print(f"[INFO] 项目目录: {project_dir}")

# 验证项目目录结构
if not (project_dir / 'Config').exists():
    print(f"[WARN] 项目目录中未找到 Config 目录: {project_dir}")
    parent_dir = project_dir.parent
    if (parent_dir / 'Config').exists():
        project_dir = parent_dir
        print(f"[INFO] 找到项目目录: {project_dir}")

# 添加路径
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

setup_windows_encoding()

# 使用 GlobalConfig 中的路径
DB_DIR = Path(GlobalConfig.full_sqlite_dir)
DB_PATH = Path(GlobalConfig.full_db_path)
REPORT_DIR = Path(GlobalConfig.full_report_dir)
CONFIG_DIR = project_dir / 'Config'

print(f"[INFO] 数据库目录: {DB_DIR}")
print(f"[INFO] 数据库路径: {DB_PATH}")
print(f"[INFO] 报告目录: {REPORT_DIR}")
print(f"[INFO] 配置目录: {CONFIG_DIR}")

# 显示股票列表摘要
print(f"\n[INFO] 股票列表摘要:")
print(f"  总股票数: {len(STOCK_LIST)}")
if STOCK_LIST:
    print(f"  股票代码范围: {STOCK_LIST[0]['code']} ~ {STOCK_LIST[-1]['code']}")
    sectors = set(s.get('sector', 'N/A') for s in STOCK_LIST)
    print(f"  涉及行业: {', '.join(sectors)}")
print()

# =====================================================
# 3. 数据库连接
# =====================================================

def get_db_connection():
    """获取数据库连接"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.text_factory = str
    return conn

# =====================================================
# 4. 数据验证函数
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
    """获取每只股票的资金流统计数据"""
    # 尝试获取资金流相关字段（净流入、成交额等），若不存在则使用基础统计
    # 先获取列名，判断有哪些数值列
    col_info = get_table_info(conn, table_name)
    cols = col_info['name'].tolist()
    
    # 构建聚合字段
    agg_fields = [
        "COUNT(*) as record_count",
        "MIN(date) as first_date",
        "MAX(date) as last_date",
        "COUNT(DISTINCT date) as trading_days"
    ]
    
    # 尝试添加资金流特定统计
    if 'net_inflow' in cols or 'net_flow' in cols:
        net_col = 'net_inflow' if 'net_inflow' in cols else 'net_flow'
        agg_fields.append(f"SUM({net_col}) as total_net_inflow")
        agg_fields.append(f"AVG({net_col}) as avg_net_inflow")
    if 'amount' in cols:
        agg_fields.append(f"SUM(amount) as total_amount")
        agg_fields.append(f"AVG(amount) as avg_amount")
    if 'turnover' in cols:
        agg_fields.append(f"AVG(turnover) as avg_turnover")
    
    query = f"""
        SELECT 
            stock_code,
            stock_name,
            {', '.join(agg_fields)}
        FROM {table_name}
        GROUP BY stock_code, stock_name
        ORDER BY stock_code
    """
    df = pd.read_sql_query(query, conn)
    return df

def get_table_sample(conn, table_name, limit=10):
    """获取表的最新记录（按日期升序）"""
    try:
        query = f"""
            SELECT * FROM {table_name} 
            ORDER BY date DESC 
            LIMIT {limit}
        """
        df = pd.read_sql_query(query, conn)
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
            if col != 'id':
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

def check_missing_stocks(conn, table_name):
    """检查是否有缺失的股票"""
    query = f"SELECT DISTINCT stock_code FROM {table_name}"
    df = pd.read_sql_query(query, conn)
    existing_codes = set(df['stock_code'].astype(str).tolist())
    expected_codes = set(STOCK_MAP.keys())
    missing_codes = expected_codes - existing_codes
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

def check_data_dictionary(table_name):
    """检查数据字典文件是否存在并与表结构一致性"""
    dict_path = CONFIG_DIR / 'hk_stock_daily_moneyflow_dictionary.json'
    if not dict_path.exists():
        return None, f"数据字典文件不存在: {dict_path}"
    
    try:
        with open(dict_path, 'r', encoding='utf-8') as f:
            dict_data = json.load(f)
        
        # 检查元数据中的表名是否匹配
        if dict_data.get('metadata', {}).get('table_name') != table_name:
            return dict_data, f"数据字典中的表名 '{dict_data.get('metadata', {}).get('table_name')}' 与当前表名 '{table_name}' 不匹配"
        
        # 检查是否有字段定义
        if 'data_dictionary' not in dict_data or 'column_definitions' not in dict_data['data_dictionary']:
            return dict_data, "数据字典缺少 'data_dictionary.column_definitions'"
        
        return dict_data, None
    except Exception as e:
        return None, f"读取数据字典失败: {e}"

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

    count = get_table_count(conn, table_name)
    print(f"  总记录数: {count:,}")

    col_info = get_table_info(conn, table_name)
    print(f"  字段数: {len(col_info)}")

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

    stock_stats = get_stock_statistics(conn, table_name)
    if not stock_stats.empty:
        print(f"\n  📈 股票统计:")
        print(f"    股票数量: {len(stock_stats)} 只")
        print(f"    总交易天数: {stock_stats['trading_days'].sum():,}")
        print(f"    平均每只股票记录数: {stock_stats['record_count'].mean():.1f}")

    date_range = get_date_range_per_stock(conn, table_name)
    if not date_range.empty:
        min_date = date_range['first_date'].min()
        max_date = date_range['last_date'].max()
        print(f"\n  📅 全局日期范围:")
        print(f"    最早日期: {min_date}")
        print(f"    最晚日期: {max_date}")

def display_stock_statistics(conn, table_name):
    """显示每只股票的资金流统计信息"""
    print("\n" + "-" * 80)
    print(" 📈 每只股票资金流统计")
    print("-" * 80)

    stock_stats = get_stock_statistics(conn, table_name)
    if stock_stats.empty:
        print("  ⚠️ 无数据")
        return

    # 动态决定显示哪些列
    display_cols = ['状态', '代码', '名称', '记录数', '开始日期', '结束日期']
    additional_cols = []
    if 'total_net_inflow' in stock_stats.columns:
        additional_cols.append('总净流入')
    if 'avg_net_inflow' in stock_stats.columns:
        additional_cols.append('平均净流入')
    if 'total_amount' in stock_stats.columns:
        additional_cols.append('总成交额')
    if 'avg_amount' in stock_stats.columns:
        additional_cols.append('平均成交额')
    if 'avg_turnover' in stock_stats.columns:
        additional_cols.append('平均换手率')
    display_cols.extend(additional_cols)

    display_data = []
    for _, row in stock_stats.iterrows():
        in_config = "✓" if row['stock_code'] in STOCK_MAP else "⚠️"
        row_data = [
            in_config,
            row['stock_code'],
            row['stock_name'],
            f"{row['record_count']:,}",
            row['first_date'],
            row['last_date']
        ]
        if 'total_net_inflow' in stock_stats.columns:
            row_data.append(f"{row['total_net_inflow']:,.2f}" if pd.notna(row['total_net_inflow']) else '')
        if 'avg_net_inflow' in stock_stats.columns:
            row_data.append(f"{row['avg_net_inflow']:,.2f}" if pd.notna(row['avg_net_inflow']) else '')
        if 'total_amount' in stock_stats.columns:
            row_data.append(f"{row['total_amount']:,.2f}" if pd.notna(row['total_amount']) else '')
        if 'avg_amount' in stock_stats.columns:
            row_data.append(f"{row['avg_amount']:,.2f}" if pd.notna(row['avg_amount']) else '')
        if 'avg_turnover' in stock_stats.columns:
            row_data.append(f"{row['avg_turnover']:.2f}%" if pd.notna(row['avg_turnover']) else '')
        display_data.append(row_data)

    print(tabulate(display_data,
                   headers=display_cols,
                   tablefmt='grid',
                   stralign='left'))

def display_sample_data(conn, table_name, limit=10):
    """显示样本数据（所有字段）"""
    print("\n" + "-" * 80)
    print(f" 📋 最新 {limit} 条记录 (按日期升序，所有字段)")
    print("-" * 80)

    df = get_table_sample(conn, table_name, limit)
    if df.empty:
        print("  ⚠️ 无数据")
        return

    # 复制全部数据
    df_display = df.copy()
    
    # 格式化数值列（基于数据类型和列名）
    for col in df_display.columns:
        # 保留 id, stock_code, stock_name, date 为原始格式
        if col in ['id', 'stock_code', 'stock_name', 'date']:
            continue
        # 检查是否为数值类型
        try:
            if pd.api.types.is_numeric_dtype(df_display[col]):
                # 根据列名决定显示格式
                col_lower = col.lower()
                if 'pct' in col_lower or 'turnover' in col_lower or 'change' in col_lower:
                    df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else '')
                elif 'amount' in col_lower or 'money' in col_lower or 'volume' in col_lower:
                    df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else '')
                else:
                    df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else '')
        except:
            pass  # 非数值列保持原样

    # 使用 tabulate 显示所有列
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

    # 4. 额外股票检查
    if extra_stocks:
        print(f"\n  4. 额外股票检查:")
        print(f"     ⚠️ 发现 {len(extra_stocks)} 只额外股票（在数据库中但不在配置文件中）:")
        for code in sorted(extra_stocks):
            query = f"SELECT stock_name FROM {table_name} WHERE stock_code='{code}' LIMIT 1"
            df = pd.read_sql_query(query, conn)
            name = df['stock_name'].iloc[0] if not df.empty else '未知'
            print(f"       - {code} {name}")
    else:
        print("\n  4. 额外股票检查: ✅ 无额外股票")

    # 5. 数据字典检查
    print(f"\n  5. 数据字典检查:")
    dict_data, error = check_data_dictionary(table_name)
    if error:
        print(f"     ❌ {error}")
    else:
        # 验证字段一致性
        db_cols = set(get_table_info(conn, table_name)['name'].tolist())
        dict_cols = set()
        for col_def in dict_data['data_dictionary']['column_definitions']:
            dict_cols.add(col_def['name'])
        # 忽略 id 字段（字典可能包含，也可能不包含）
        # 实际比较时，忽略 id
        db_cols_no_id = {c for c in db_cols if c != 'id'}
        dict_cols_no_id = {c for c in dict_cols if c != 'id'}
        if db_cols_no_id == dict_cols_no_id:
            print("     ✅ 数据字典与表结构一致")
        else:
            missing_in_dict = db_cols_no_id - dict_cols_no_id
            missing_in_db = dict_cols_no_id - db_cols_no_id
            print("     ⚠️ 数据字典与表结构不一致")
            if missing_in_dict:
                print(f"       数据字典缺失字段: {', '.join(missing_in_dict)}")
            if missing_in_db:
                print(f"       数据库中缺失字段: {', '.join(missing_in_db)}")

# =====================================================
# 6. 生成验证报告
# =====================================================

def generate_report(conn, table_name):
    """生成验证报告"""
    REPORT_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"Verify_Daily_Moneyflow_{timestamp}.txt"
    report_path = REPORT_DIR / report_filename
    json_report_path = REPORT_DIR / f"Verify_Daily_Moneyflow_{timestamp}.json"

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
            'extra_stocks': [],
            'data_dictionary': {}
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

    # 数据字典检查
    dict_data, dict_error = check_data_dictionary(table_name)
    validation_data['quality_checks']['data_dictionary'] = {
        'exists': dict_data is not None,
        'error': dict_error,
        'table_name_in_dict': dict_data.get('metadata', {}).get('table_name') if dict_data else None
    }

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
        f.write(f"股票数量: {len(stock_stats)}\n\n")

        # 股票统计
        f.write("-" * 80 + "\n")
        f.write("每只股票资金流统计\n")
        f.write("-" * 80 + "\n")
        for _, row in stock_stats.iterrows():
            in_config = "✓" if row['stock_code'] in STOCK_MAP else "⚠️"
            f.write(f"  {in_config} {row['stock_code']} {row['stock_name']}: ")
            f.write(f"{row['record_count']:,} 条记录, ")
            f.write(f"{row['first_date']} ~ {row['last_date']}")
            if 'total_net_inflow' in row and pd.notna(row['total_net_inflow']):
                f.write(f", 总净流入: {row['total_net_inflow']:,.2f}")
            if 'avg_net_inflow' in row and pd.notna(row['avg_net_inflow']):
                f.write(f", 平均净流入: {row['avg_net_inflow']:,.2f}")
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

        # 数据字典
        f.write("5. 数据字典检查:\n")
        if dict_error:
            f.write(f"     ❌ {dict_error}\n")
        else:
            # 检查一致性
            db_cols = set(get_table_info(conn, table_name)['name'].tolist())
            dict_cols = set()
            for col_def in dict_data['data_dictionary']['column_definitions']:
                dict_cols.add(col_def['name'])
            db_cols_no_id = {c for c in db_cols if c != 'id'}
            dict_cols_no_id = {c for c in dict_cols if c != 'id'}
            if db_cols_no_id == dict_cols_no_id:
                f.write("     ✅ 数据字典与表结构一致\n")
            else:
                missing_in_dict = db_cols_no_id - dict_cols_no_id
                missing_in_db = dict_cols_no_id - db_cols_no_id
                f.write("     ⚠️ 数据字典与表结构不一致\n")
                if missing_in_dict:
                    f.write(f"       数据字典缺失字段: {', '.join(missing_in_dict)}\n")
                if missing_in_db:
                    f.write(f"       数据库中缺失字段: {', '.join(missing_in_db)}\n")
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
# 7. 主函数
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
        print("请先运行 Import_Daily_Moneyflow.py 导入数据")
        sys.exit(1)

    TABLE_NAME = 'hk_hist_daily_moneyflow'

    # 获取数据库连接
    conn = get_db_connection()

    try:
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}'")
        if not cursor.fetchone():
            print(f"❌ 表 {TABLE_NAME} 不存在")
            print("请先运行 Import_Daily_Moneyflow.py 导入数据")
            return

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

    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    main()