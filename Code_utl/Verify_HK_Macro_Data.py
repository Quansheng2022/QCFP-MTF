#!/usr/bin/env python
# coding: utf-8

"""
HK_Macro_Verify_Data.py
数据验证程序 - 验证 HK_Stock.db 数据库中的所有表
功能:
  1. 显示所有表的列表和基本信息
  2. 显示每个表的字段名称和数据类型
  3. 显示每个表的最新5条记录（日期升序）
  4. 统计每个表的记录数
  5. 检查数据完整性（空值、重复值等）
  6. 生成验证报告（包含最新5条记录）
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
# 1. 统一路径设置（参照 HK_Macro_History.py）
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
        # 脚本路径: .../$PROJECT_DIR/Code_utl/HK_Macro_Verify_Data.py
        # 项目根目录: .../$PROJECT_DIR
        script_path = Path(__file__).resolve()

        # 向上一级到达项目根目录
        # Code_utl 目录的父目录就是项目根目录
        project_dir = script_path.parent

        # 验证是否真的是项目根目录（检查是否存在 Config 目录）
        if (project_dir / 'Config').exists():
            return project_dir

        # 如果找不到 Config，尝试其他方式
        # 检查是否在 Code_utl 目录中
        if script_path.parent.name == 'Code_utl':
            return script_path.parent.parent

        # 尝试从当前工作目录向上查找
        cwd = Path(os.getcwd()).resolve()
        for parent in [cwd] + list(cwd.parents):
            if (parent / 'Config').exists() and (parent / 'Core').exists():
                return parent

        # 最后返回当前目录的父目录
        return cwd.parent if cwd.name == 'Code_utl' else cwd

    except Exception as e:
        print(f"获取项目目录错误: {str(e)}")
        # 备用方案：使用当前文件位置推断
        return Path(__file__).resolve().parent.parent

def setup_windows_encoding():
    """解决Windows环境的中文编码问题"""
    if sys.platform == "win32":
        try:
            os.system("chcp 65001 > nul")
        except Exception as e:
            print(f"设置控制台代码页失败: {e}")

# =====================================================
# 2. 配置加载和路径初始化（参照 HK_Macro_History.py）
# =====================================================

# 获取项目根目录
project_dir = get_project_dir()
print(f"[INFO] 项目目录: {project_dir}")

# 验证项目目录结构
if not (project_dir / 'Config').exists():
    print(f"[WARN] 项目目录中未找到 Config 目录: {project_dir}")
    print(f"[WARN] 尝试在父目录中查找...")
    # 尝试在父目录中查找
    parent_dir = project_dir.parent
    if (parent_dir / 'Config').exists():
        project_dir = parent_dir
        print(f"[INFO] 找到项目目录: {project_dir}")

# 确保 Core 目录在 sys.path 中
core_dir = project_dir / 'Core'
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))
    print(f"[INFO] 已添加 Core 目录到 sys.path: {core_dir}")

# 也添加项目根目录到 sys.path
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

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
        print(f"[ERROR] 请确认项目目录结构: {project_dir}")
        sys.exit(1)

# 加载配置（优先使用 utl.stock_analysis_utl）
try:
    # 尝试从 utl 导入
    from Utl.stock_analysis_utl import load_config, GlobalConfig
    print("[INFO] 成功导入 Utl.stock_analysis_utl")
except ImportError as e:
    print(f"[WARN] 无法导入 Utl.stock_analysis_utl: {e}")
    print("[INFO] 使用本地简化配置加载")

    # 本地简化版 GlobalConfig（与 HK_Macro_History.py 保持一致）
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

        # 确保目录存在
        for path_key in ['full_data_dir', 'full_report_dir', 'full_log_dir',
                         'full_temp_dir', 'full_sqlite_dir']:
            path = config.get(path_key)
            if path and not os.path.exists(path):
                os.makedirs(path, exist_ok=True)

        return config

# 加载配置
print("[INFO] 加载配置文件...")
CONFIG = load_config(str(config_path), str(project_dir))

# 更新 GlobalConfig（与 HK_Macro_History.py 保持一致）
if hasattr(GlobalConfig, 'update_paths'):
    # 使用 stock_analysis_utl 的 update_paths 方法
    GlobalConfig.update_paths(CONFIG, project_dir)
else:
    # 手动设置 GlobalConfig
    GlobalConfig.full_data_dir = CONFIG.get('full_data_dir')
    GlobalConfig.full_report_dir = CONFIG.get('full_report_dir')
    GlobalConfig.full_log_dir = CONFIG.get('full_log_dir')
    GlobalConfig.full_temp_dir = CONFIG.get('full_temp_dir')
    GlobalConfig.full_sqlite_dir = CONFIG.get('full_sqlite_dir')
    GlobalConfig.db_name = CONFIG.get('db_name', 'HK_Stock.db')
    GlobalConfig.full_db_path = CONFIG.get('full_db_path')

# 强制 UTF-8 输出（控制台）
setup_windows_encoding()

# 使用 GlobalConfig 中的路径（与 HK_Macro_History.py 保持一致）
DB_DIR = Path(GlobalConfig.full_sqlite_dir)
DB_PATH = Path(GlobalConfig.full_db_path)
print(f"[INFO] 数据库目录: {DB_DIR}")
print(f"[INFO] 数据库路径: {DB_PATH}")

# ---------- 加载数据字典（与 HK_Macro_History.py 保持一致）----------
DATA_DICT_PATH = project_dir / "Config" / "hk_macro_data_dictionary.json"
data_dictionary = {}
if DATA_DICT_PATH.exists():
    try:
        with open(DATA_DICT_PATH, 'r', encoding='utf-8') as f:
            data_dictionary = json.load(f)
        print(f"[INFO] 数据字典已加载: {DATA_DICT_PATH}")
        print(f"[INFO] 数据字典内容: {list(data_dictionary.keys()) if data_dictionary else '空'}")
    except Exception as e:
        print(f"[WARN] 加载数据字典失败: {e}")
else:
    print(f"[WARN] 数据字典文件不存在: {DATA_DICT_PATH}")

# =====================================================
# 3. 打印汇总信息
# =====================================================
print("=" * 80)
print("HK 宏观数据验证工具")
print("=" * 80)
print(f"项目目录: {project_dir}")
print(f"数据库路径: {DB_PATH}")
print(f"数据字典: {DATA_DICT_PATH}")
print(f"报告目录: {Path(GlobalConfig.full_report_dir)}")
print("=" * 80)
print()

# =====================================================
# 4. 数据库连接（与 HK_Macro_History.py 保持一致）
# =====================================================
def get_db_connection():
    """获取数据库连接"""
    # 确保数据库目录存在（使用 GlobalConfig）
    DB_DIR = Path(GlobalConfig.full_sqlite_dir)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.text_factory = str  # 确保文本以字符串形式返回
    return conn

# =====================================================
# 5. 表信息获取
# =====================================================
def get_all_tables(conn):
    """获取所有表名"""
    query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    df = pd.read_sql_query(query, conn)
    return df['name'].tolist()

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

def get_table_sample(conn, table_name, limit=5):
    """获取表的最新记录（按日期降序获取，然后升序显示）"""
    try:
        # 首先尝试使用 date 列（降序获取最新的N条）
        query = f"SELECT * FROM {table_name} ORDER BY date DESC LIMIT {limit};"
        df = pd.read_sql_query(query, conn)

        # 如果有 date 列但没有数据，尝试使用 time_key
        if df.empty and 'time_key' in df.columns:
            query = f"SELECT * FROM {table_name} ORDER BY time_key DESC LIMIT {limit};"
            df = pd.read_sql_query(query, conn)

        # 如果仍然没有数据，尝试使用任何包含 'date' 或 'time' 的列
        if df.empty:
            columns = get_table_info(conn, table_name)['name'].tolist()
            date_columns = [col for col in columns if 'date' in col.lower() or 'time' in col.lower()]

            if date_columns:
                query = f"SELECT * FROM {table_name} ORDER BY {date_columns[0]} DESC LIMIT {limit};"
                df = pd.read_sql_query(query, conn)

        # 如果还是没有数据，直接取前5条
        if df.empty:
            query = f"SELECT * FROM {table_name} LIMIT {limit};"
            df = pd.read_sql_query(query, conn)

        return df
    except Exception as e:
        print(f"  ⚠️ 获取样本数据失败: {e}")
        return pd.DataFrame()

def get_table_date_range(conn, table_name):
    """获取表的日期范围"""
    try:
        columns = get_table_info(conn, table_name)['name'].tolist()
        date_columns = [col for col in columns if 'date' in col.lower() or 'time' in col.lower()]

        if date_columns:
            date_col = date_columns[0]
            query = f"""
                SELECT 
                    MIN({date_col}) as min_date,
                    MAX({date_col}) as max_date,
                    COUNT(DISTINCT {date_col}) as unique_days
                FROM {table_name}
                WHERE {date_col} IS NOT NULL;
            """
            df = pd.read_sql_query(query, conn)
            return df
    except Exception:
        pass
    return pd.DataFrame()

def get_date_column(conn, table_name):
    """获取表的日期列名"""
    columns = get_table_info(conn, table_name)['name'].tolist()
    for col in columns:
        if col in ['date', 'time_key']:
            return col
        if 'date' in col.lower() or 'time' in col.lower():
            return col
    return None

# =====================================================
# 6. 数据质量检查
# =====================================================
def check_null_values(conn, table_name):
    """检查空值"""
    try:
        columns = get_table_info(conn, table_name)['name'].tolist()
        null_counts = {}

        for col in columns:
            query = f"SELECT COUNT(*) as null_count FROM {table_name} WHERE {col} IS NULL OR {col} = '';"
            df = pd.read_sql_query(query, conn)
            null_counts[col] = df['null_count'].iloc[0]

        return null_counts
    except Exception:
        return {}

def check_duplicates(conn, table_name, date_col='date'):
    """检查重复记录"""
    try:
        columns = get_table_info(conn, table_name)['name'].tolist()

        if date_col in columns:
            query = f"""
                SELECT {date_col}, COUNT(*) as count 
                FROM {table_name} 
                GROUP BY {date_col} 
                HAVING COUNT(*) > 1
                ORDER BY count DESC;
            """
            df = pd.read_sql_query(query, conn)
            return df
    except Exception:
        pass
    return pd.DataFrame()

# =====================================================
# 7. 显示函数（使用表格形式）
# =====================================================
def display_header(text, char='='):
    """显示标题"""
    print()
    print(char * 80)
    print(f" {text}")
    print(char * 80)

def display_table_summary(conn, table_name, index):
    """显示表的摘要信息"""
    print()
    print(f"[{index}] 表名: {table_name}")
    print("-" * 80)

    # 获取记录数
    count = get_table_count(conn, table_name)
    print(f"  总记录数: {count:,}")

    # 获取列信息
    col_info = get_table_info(conn, table_name)
    print(f"  字段数: {len(col_info)}")

    # 显示字段信息（表格形式）
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

    # 日期范围
    date_range = get_table_date_range(conn, table_name)
    if not date_range.empty and not date_range['min_date'].isna().all():
        min_date = date_range['min_date'].iloc[0]
        max_date = date_range['max_date'].iloc[0]
        unique_days = date_range['unique_days'].iloc[0]
        print(f"\n  日期范围: {min_date} 至 {max_date}")
        print(f"  交易日天数: {unique_days:,}")

    # 空值检查
    null_counts = check_null_values(conn, table_name)
    if null_counts:
        total_nulls = sum(null_counts.values())
        if total_nulls > 0:
            print(f"\n  ⚠️ 空值总数: {total_nulls:,}")
            # 显示空值最多的前5个字段（表格形式）
            sorted_nulls = sorted(null_counts.items(), key=lambda x: x[1], reverse=True)
            top_nulls = [item for item in sorted_nulls if item[1] > 0][:5]
            if top_nulls:
                print("  空值最多的字段:")
                null_data = []
                for col, null_count in top_nulls:
                    percentage = (null_count / count * 100) if count > 0 else 0
                    null_data.append([col, f"{null_count:,}", f"{percentage:.1f}%"])
                print(tabulate(null_data,
                               headers=['字段名', '空值数', '空值率'],
                               tablefmt='simple',
                               stralign='left'))

    # 重复记录检查
    date_col = get_date_column(conn, table_name)
    if date_col:
        duplicates = check_duplicates(conn, table_name, date_col)
        if not duplicates.empty:
            print(f"\n  ⚠️ 发现 {len(duplicates)} 个重复日期")
            print("  重复日期示例 (前5个):")
            dup_data = []
            for _, row in duplicates.head(5).iterrows():
                dup_data.append([row.iloc[0], row.iloc[1]])
            print(tabulate(dup_data,
                           headers=['日期', '重复次数'],
                           tablefmt='simple',
                           stralign='left'))

def display_sample_data(conn, table_name, limit=5):
    """显示样本数据（表格形式）- 日期升序，最早的在前"""
    print(f"\n  最新 {limit} 条记录 (日期升序):")

    df = get_table_sample(conn, table_name, limit)

    if df.empty:
        print("  ⚠️ 无数据")
        return

    # 获取日期列
    date_col = get_date_column(conn, table_name)

    # 按日期升序排列（最早的在前）
    if date_col and date_col in df.columns:
        try:
            df = df.sort_values(date_col, ascending=True)
        except:
            # 如果排序失败，保持原顺序
            pass

    # 处理数据：截断长文本和格式化数值
    for col in df.columns:
        try:
            # 处理字符串类型的列
            if df[col].dtype == 'object':
                # 先转换为字符串，处理NaN值
                df[col] = df[col].fillna('').astype(str)
                # 截断长文本
                df[col] = df[col].apply(lambda x: x[:30] + '...' if len(x) > 30 else x)
                # 将'nan'替换为空字符串
                df[col] = df[col].replace('nan', '')

            # 处理浮点数类型
            elif pd.api.types.is_float_dtype(df[col]):
                df[col] = df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else '')

            # 处理整数类型
            elif pd.api.types.is_integer_dtype(df[col]):
                df[col] = df[col].apply(lambda x: f"{x:,}" if pd.notna(x) else '')

            # 处理日期时间类型
            elif pd.api.types.is_datetime64_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                df[col] = df[col].replace('NaT', '')
        except Exception as e:
            # 如果处理某列失败，保持原样
            pass

    # 使用表格显示
    try:
        print(tabulate(df, headers='keys', tablefmt='grid', stralign='right', showindex=False))
    except Exception as e:
        # 如果表格显示失败，使用简单格式
        print(tabulate(df, headers='keys', tablefmt='simple', stralign='right', showindex=False))

    # 显示数据统计信息
    print(f"\n  显示记录数: {len(df)} 条")
    if date_col and date_col in df.columns:
        try:
            # 过滤掉空值后再计算日期范围
            valid_dates = df[date_col][df[date_col] != '']
            if not valid_dates.empty:
                # 尝试转换为日期类型
                try:
                    min_date = pd.to_datetime(valid_dates).min()
                    max_date = pd.to_datetime(valid_dates).max()
                    print(f"  记录日期范围: {min_date.strftime('%Y-%m-%d')} 至 {max_date.strftime('%Y-%m-%d')}")
                except:
                    # 如果转换失败，直接显示字符串值
                    min_date = valid_dates.min()
                    max_date = valid_dates.max()
                    print(f"  记录日期范围: {min_date} 至 {max_date}")
        except Exception as e:
            # 如果日期计算失败，静默忽略
            pass

def display_dictionary_info(table_name):
    """显示数据字典中的表信息"""
    if data_dictionary and 'tables' in data_dictionary:
        tables = data_dictionary['tables']
        if table_name in tables:
            table_info = tables[table_name]
            print(f"\n  数据字典信息:")
            dict_data = [
                ['描述', table_info.get('description', 'N/A')],
                ['类型', table_info.get('table_type', 'N/A')],
                ['更新频率', table_info.get('update_frequency', 'N/A')],
                ['数据源', table_info.get('data_source', 'N/A')]
            ]
            print(tabulate(dict_data,
                           headers=['属性', '值'],
                           tablefmt='simple',
                           stralign='left'))

# =====================================================
# 8. 生成验证报告
# =====================================================
def generate_report(conn, tables):
    """生成验证报告"""
    report_dir = Path(GlobalConfig.full_report_dir)
    report_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"HK_Macro_Data_Verify_{timestamp}.txt"
    report_path = report_dir / report_filename

    # 重定向输出到文件
    original_stdout = sys.stdout

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            sys.stdout = f

            print("=" * 80)
            print("HK 宏观数据验证报告")
            print("=" * 80)
            print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"数据库路径: {DB_PATH}")
            print(f"项目目录: {project_dir}")
            print(f"总表数: {len(tables)}")
            print()

            # 表概览
            print("-" * 80)
            print("表概览:")
            print("-" * 80)
            overview_data = []
            for i, table_name in enumerate(tables, 1):
                count = get_table_count(conn, table_name)
                date_range = get_table_date_range(conn, table_name)
                if not date_range.empty and not date_range['min_date'].isna().all():
                    min_date = date_range['min_date'].iloc[0]
                    max_date = date_range['max_date'].iloc[0]
                    date_info = f"{min_date} ~ {max_date}"
                else:
                    date_info = "N/A"
                overview_data.append([i, table_name, f"{count:,}", date_info])

            print(tabulate(overview_data,
                           headers=['序号', '表名', '记录数', '日期范围'],
                           tablefmt='grid',
                           stralign='left'))

            # 每个表的详细信息
            for i, table_name in enumerate(tables, 1):
                display_table_summary(conn, table_name, i)
                display_sample_data(conn, table_name, limit=5)
                display_dictionary_info(table_name)

            print()
            print("=" * 80)
            print("报告结束")
            print("=" * 80)

    finally:
        sys.stdout = original_stdout

    print(f"\n✅ 验证报告已生成: {report_path}")
    return report_path

# =====================================================
# 9. 主函数
# =====================================================
def main():
    print(f"\n数据库路径: {DB_PATH.resolve()}")
    print(f"项目根目录: {project_dir}")
    print()

    # 检查数据库是否存在
    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("请先运行数据导入脚本创建数据库")
        sys.exit(1)

    # 获取数据库连接
    conn = get_db_connection()

    try:
        # 获取所有表
        tables = get_all_tables(conn)

        if not tables:
            print("⚠️ 数据库中没有表")
            return

        print(f"📊 数据库中共有 {len(tables)} 个表")
        print()

        # 显示每个表的详细信息
        for i, table_name in enumerate(tables, 1):
            display_table_summary(conn, table_name, i)
            display_sample_data(conn, table_name, limit=5)
            display_dictionary_info(table_name)

        # 生成报告
        print()
        display_header("生成验证报告")
        report_path = generate_report(conn, tables)

        # 汇总统计
        print()
        display_header("汇总统计")
        summary_data = []
        total_records = 0
        for table_name in tables:
            count = get_table_count(conn, table_name)
            total_records += count
            summary_data.append([table_name, f"{count:,}"])
        summary_data.append(['总计', f"{total_records:,}"])

        print(tabulate(summary_data,
                       headers=['表名', '记录数'],
                       tablefmt='grid',
                       stralign='left'))

        print()
        print("✅ 验证完成")

    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
