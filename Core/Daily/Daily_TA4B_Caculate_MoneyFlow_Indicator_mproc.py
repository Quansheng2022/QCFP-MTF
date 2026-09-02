#!/usr/bin/env python
# coding: utf-8

"""
Step 8: Analyze daily money flow indicators.
Name： Daily_TA4B_Caculate_MoneyFlow_Indicator_mproc.py
Input data:     hk_hist_daily_moneyflow
Output data:    hk_daily_moneyflow_analysis
Function:
1. 采用多任务并行处理方式，将资金流分析指标数据保存在SQLite数据库中。
2. 只更新 hk_daily_moneyflow_analysis 表，不生成合并表。
"""

# 核心库
import os
import sys
import io
import time
import warnings
import logging
import traceback
import datetime
from datetime import datetime, timedelta
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import sqlite3

# 数据处理
import pandas as pd
import numpy as np

# 其他
from pathlib import Path
from scipy import stats

# === 添加UTL路径到系统路径 ===
script_dir = Path(__file__).resolve().parent
core_dir = script_dir.parent
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

project_dir = core_dir.parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

# 从 utl.stock_analysis_utl 导入
try:
    from utl.stock_analysis_utl import get_project_root
except ImportError as e:
    sys.path.insert(0, str(core_dir / 'utl'))
    try:
        from stock_analysis_utl import get_project_root
    except ImportError:
        print("=" * 60)
        print("❌ 严重错误：无法导入 utl.stock_analysis_utl 模块")
        print("=" * 60)
        sys.exit(1)

# 从 utl.stock_analysis_utl 导入
try:
    from utl.stock_analysis_utl import (
        load_config,
        setup_windows_encoding,
        GlobalConfig,
        get_validated_dates
    )
except ImportError as e:
    sys.path.insert(0, str(core_dir / 'utl'))
    try:
        from stock_analysis_utl import (
            load_config,
            setup_windows_encoding,
            GlobalConfig,
            get_validated_dates
        )
    except ImportError as e2:
        print("=" * 60)
        print("❌ 严重错误：无法导入 utl.stock_analysis_utl 模块")
        print("=" * 60)
        sys.exit(1)

# === 强制UTF-8编码输出 ===
if 'get_ipython' not in globals():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
else:
    import ipykernel
    if ipykernel:
        sys.stdout.encoding = 'utf-8'
        sys.stderr.encoding = 'utf-8'

setup_windows_encoding()

# ============================================
# 日志配置 - 覆盖模式（参考 Daily_TA3B_Chip_Signal_Analysis.py）
# ============================================
def setup_logger(log_dir, log_name='Daily_TA4B_Caculate_MoneyFlow_Indicator_mproc.log'):
    """
    设置日志记录器 - 覆盖模式
    
    参数:
        log_dir (str): 日志目录路径
        log_name (str): 日志文件名
    
    返回:
        logging.Logger: 配置好的logger对象
    """
    global logger
    
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, log_name)
    
    # 创建logger
    logger = logging.getLogger('Daily_TA4B_Caculate_MoneyFlow_Indicator_mproc')
    logger.setLevel(logging.DEBUG)
    
    # 如果已经有handler，先清除
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建文件handler - 使用 'w' 模式直接覆盖原有文件
    file_handler = logging.FileHandler(
        log_file, 
        mode='w',  # 'w' 模式会覆盖原有文件
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 创建控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加handler到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 记录启动信息
    logger.info("=" * 80)
    logger.info(f"日志系统初始化完成（覆盖模式）")
    logger.info(f"日志文件: {log_file}")
    logger.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    return logger

# 全局logger变量 - 仅主进程使用
logger = None

def get_db_path():
    """获取数据库文件路径"""
    db_path = project_dir / 'SQLiteDB' / 'HK_Stock.db'
    return str(db_path)


def get_db_connection():
    """获取数据库连接"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_analysis_table_columns(conn, table_name='hk_daily_moneyflow_analysis'):
    """
    确保分析表包含所有必要的列（所有列名小写）
    
    注意：此函数可能在子进程中被调用，使用print输出
    """
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    if not cursor.fetchone():
        create_sql = f"""
        CREATE TABLE {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            date TEXT,
            price_chgpct REAL,
            capital_trend REAL,
            extra_large REAL,
            large REAL,
            medium REAL,
            small REAL,
            institutional_flow REAL,
            individual_flow REAL,
            inst_5ma REAL,
            ind_5ma REAL,
            idr REAL,
            fbi REAL,
            capital_in_super REAL DEFAULT 0,
            capital_in_big REAL DEFAULT 0,
            capital_in_mid REAL DEFAULT 0,
            capital_in_small REAL DEFAULT 0,
            capital_out_super REAL DEFAULT 0,
            capital_out_big REAL DEFAULT 0,
            capital_out_mid REAL DEFAULT 0,
            capital_out_small REAL DEFAULT 0,
            UNIQUE(stock_code, date)
        )
        """
        cursor.execute(create_sql)
        conn.commit()
        print(f"✓ 创建表 {table_name}")
        return
    
    # 获取现有列
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    # 需要添加的列（小写）
    columns_to_add = {
        'capital_in_super': 'REAL DEFAULT 0',
        'capital_in_big': 'REAL DEFAULT 0',
        'capital_in_mid': 'REAL DEFAULT 0',
        'capital_in_small': 'REAL DEFAULT 0',
        'capital_out_super': 'REAL DEFAULT 0',
        'capital_out_big': 'REAL DEFAULT 0',
        'capital_out_mid': 'REAL DEFAULT 0',
        'capital_out_small': 'REAL DEFAULT 0'
    }
    
    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                print(f"✓ 添加列 {col_name} 到表 {table_name}")
            except Exception as e:
                print(f"⚠️ 添加列 {col_name} 失败: {e}")
    
    conn.commit()


def get_latest_analysis_date(conn, stock_code, table_name='hk_daily_moneyflow_analysis'):
    """获取分析表最新日期"""
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT MAX(date) as latest_date FROM {table_name} WHERE stock_code = ?",
        (stock_code,)
    )
    result = cursor.fetchone()
    if result and result['latest_date']:
        return datetime.strptime(result['latest_date'], '%Y-%m-%d').date()
    return None


def get_latest_raw_data_date(conn, stock_code, table_name='hk_hist_daily_moneyflow'):
    """获取原始资金流表最新日期"""
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT MAX(date) as latest_date FROM {table_name} WHERE stock_code = ?",
        (stock_code,)
    )
    result = cursor.fetchone()
    if result and result['latest_date']:
        return datetime.strptime(result['latest_date'], '%Y-%m-%d').date()
    return None


def save_to_database(df, conn, stock_code, table_name='hk_daily_moneyflow_analysis'):
    """
    保存数据到数据库
    
    所有列名使用小写
    """
    df_copy = df.copy()
    
    # 确保日期格式正确
    if 'date' in df_copy.columns:
        df_copy['date'] = pd.to_datetime(df_copy['date']).dt.strftime('%Y-%m-%d')
    
    # 添加 stock_code
    df_copy['stock_code'] = stock_code
    
    # 将所有列名转换为小写（与数据库匹配）
    df_copy.columns = [col.lower() for col in df_copy.columns]
    
    # 替换 NaN 为 None
    df_copy = df_copy.where(pd.notnull(df_copy), None)
    
    # 获取目标表的列名
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    table_columns = [row[1] for row in cursor.fetchall()]
    
    # 只保留表中存在的列
    columns_to_save = [col for col in df_copy.columns if col in table_columns]
    df_to_save = df_copy[columns_to_save]
    
    # 构建 INSERT OR REPLACE 语句
    placeholders = ','.join(['?' for _ in columns_to_save])
    columns_str = ','.join(columns_to_save)
    insert_sql = f"INSERT OR REPLACE INTO {table_name} ({columns_str}) VALUES ({placeholders})"
    
    # 批量插入
    records = df_to_save.to_records(index=False).tolist()
    cursor.executemany(insert_sql, records)
    conn.commit()
    
    print(f"✓ 保存 {len(records)} 条记录到数据库表 {table_name} (stock_code: {stock_code})")


def calculate_money_flow_indicator(stock_code, conn):
    """
    计算资金流指标
    
    所有列名使用小写
    """
    try:
        # 检查原始数据是否存在
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM hk_hist_daily_moneyflow WHERE stock_code = ?",
            (stock_code,)
        )
        result = cursor.fetchone()
        if result['count'] == 0:
            print(f"❌ {stock_code}: 原始资金流数据不存在")
            return False
        
        # 从数据库读取数据
        df = pd.read_sql_query(
            "SELECT * FROM hk_hist_daily_moneyflow WHERE stock_code = ? ORDER BY date",
            conn,
            params=(stock_code,)
        )
        
        if df.empty:
            print(f"❌ {stock_code}: 读取数据为空")
            return False
        
        # 统一列名为小写
        df.columns = [col.lower() for col in df.columns]
        
        # 验证必要列（小写）
        required_columns = ['date', 'extra_large', 'large', 'medium', 'small', 'price_chgpct']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"❌ {stock_code}: 缺少必要列: {missing_columns}")
            print(f"   现有列: {df.columns.tolist()}")
            return False
        
        # 转换日期格式
        df["date"] = pd.to_datetime(df["date"]).dt.date
        
        # 计算资金流入流出（小写列名）
        df['capital_in_super'] = df['extra_large'].apply(lambda x: x if x > 0 else 0)
        df['capital_in_big'] = df['large'].apply(lambda x: x if x > 0 else 0)
        df['capital_in_mid'] = df['medium'].apply(lambda x: x if x > 0 else 0)
        df['capital_in_small'] = df['small'].apply(lambda x: x if x > 0 else 0)
        
        df['capital_out_super'] = df['extra_large'].apply(lambda x: abs(x) if x < 0 else 0)
        df['capital_out_big'] = df['large'].apply(lambda x: abs(x) if x < 0 else 0)
        df['capital_out_mid'] = df['medium'].apply(lambda x: abs(x) if x < 0 else 0)
        df['capital_out_small'] = df['small'].apply(lambda x: abs(x) if x < 0 else 0)
        
        # 聚合机构和个人资金流（小写列名）
        df['institutional_flow'] = df['extra_large'] + df['large']
        df['individual_flow'] = df['medium'] + df['small']
        
        # 计算5日移动平均（小写列名）
        df['inst_5ma'] = df['institutional_flow'].rolling(5).mean()
        df['ind_5ma'] = df['individual_flow'].rolling(5).mean()
        
        # 计算IDR (Institutional Dominance Ratio)（小写列名）
        denominator = abs(df["institutional_flow"]) + abs(df["individual_flow"])
        df["idr"] = np.where(denominator > 0, 
                             abs(df["institutional_flow"]) / denominator, 
                             0)
        
        # 计算FBI (Flow Balance Indicator)（小写列名）
        df["fbi"] = np.where(denominator > 0,
                             (df["institutional_flow"] - df["individual_flow"]) / denominator,
                             0)
        
        # 保存到数据库
        ensure_analysis_table_columns(conn)
        save_to_database(df, conn, stock_code)
        
        return True
        
    except Exception as e:
        print(f"❌ {stock_code}: 计算资金流指标失败 - {str(e)}")
        traceback.print_exc()
        return False


def process_single_stock(stock_code):
    """
    处理单个股票（在子进程中运行）
    
    参数：stock_code - 股票代码字符串
    注意：子进程中使用print输出，不使用logger
    """
    try:
        conn = get_db_connection()
        ensure_analysis_table_columns(conn)
        
        # 检查数据状态
        latest_analysis = get_latest_analysis_date(conn, stock_code)
        latest_raw = get_latest_raw_data_date(conn, stock_code)
        
        print(f"  {stock_code}: 分析表最新日期={latest_analysis}, 原始表最新日期={latest_raw}")
        
        if latest_analysis is None:
            print(f"  {stock_code}: 没有分析数据，开始计算...")
        elif latest_raw is None:
            print(f"⚠️ {stock_code}: 原始资金流数据不存在，跳过")
            conn.close()
            return f"{stock_code}: Skipped - no raw data"
        elif latest_analysis < latest_raw:
            print(f"  {stock_code}: 分析数据过时，重新计算...")
        elif latest_analysis == latest_raw:
            print(f"  ✅ {stock_code}: 分析数据已存在且最新，无需重复计算")
            conn.close()
            return f"{stock_code}: Success - already up to date"
        else:
            print(f"⚠️ {stock_code}: 原始资金流数据缺失或分析数据有误，需核查")
            conn.close()
            return f"{stock_code}: Warning - data inconsistency"
        
        # 计算资金流指标
        if not calculate_money_flow_indicator(stock_code, conn):
            conn.close()
            return f"{stock_code}: Failed at money flow calculation"
        
        conn.close()
        return f"{stock_code}: Success"
        
    except Exception as e:
        print(f"❌ {stock_code}: 处理失败 - {str(e)}")
        traceback.print_exc()
        return f"{stock_code}: Failed with exception - {str(e)}"


def save_indicator_columns(conn, table_name='hk_daily_moneyflow_analysis'):
    """保存指标列名到文本文件"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        
        if not columns_info:
            logger.error(f"❌ 表 {table_name} 不存在或为空")
            return False
        
        columns = [col[1] for col in columns_info]
        
        output_file = os.path.join(GlobalConfig.full_data_dir, 'Daily_MF_Indicator_Cols.txt')
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# 资金流分析指标列名列表 [来源表: {table_name}]\n")
            f.write(f"# 提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 总列数: {len(columns)}\n\n")
            f.write("# 列名列表（全部小写）:\n")
            for col in columns:
                f.write(f"{col}\n")
        
        logger.info(f"✓ 成功保存 {len(columns)} 个指标列名到 {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 保存列名失败: {str(e)}")
        return False


def main():
    """主函数"""
    global logger
    
    try:
        config_path = os.path.join(project_dir, 'Config', 'stock_data_analysis.par')
        CONFIG = load_config(config_path, project_dir)
        
        GlobalConfig.update_paths(CONFIG, project_dir)
        
        # ========== 初始化日志系统（覆盖模式） ==========
        log_dir = GlobalConfig.full_log_dir
        log_name = 'Daily_TA4B_Caculate_MoneyFlow_Indicator_mproc.log'
        logger = setup_logger(log_dir, log_name)
        
        # 打印配置信息
        logger.info("=" * 60)
        logger.info(f"配置文件加载成功: {config_path}")
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        logger.info(f"日志文件: {os.path.join(log_dir, log_name)}")
        logger.info(f"数据库路径: {get_db_path()}")
        logger.info("=" * 60)
        
        if CONFIG.get('tickers'):
            tickers = CONFIG['tickers']
            logger.info(f"股票代码数量: {len(tickers)}")
            if len(tickers) > 5:
                logger.info(f"前5个股票代码: {tickers[:5]}... 等")
            else:
                logger.info(f"股票代码: {tickers}")
        else:
            logger.warning("配置文件中未找到tickers设置")
            return
        
        start_date, end_date = get_validated_dates(CONFIG, project_dir)
        logger.info(f"📅 验证通过的日期范围:")
        logger.info(f"开始日期: {start_date.strftime('%Y-%m-%d')}")
        logger.info(f"结束日期: {end_date.strftime('%Y-%m-%d')}")
        
        if not tickers:
            logger.error("没有配置股票代码")
            return
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"{current_time} 开始计算资金流指标...")
        
        # 使用进程池处理
        num_processes = min(mp.cpu_count(), len(tickers), 8)
        logger.info(f"使用 {num_processes} 个进程并行处理")
        
        results = []
        with ProcessPoolExecutor(max_workers=num_processes) as executor:
            # 直接提交任务，传递股票代码字符串
            future_to_stock = {
                executor.submit(process_single_stock, ticker): ticker 
                for ticker in tickers
            }
            
            for future in as_completed(future_to_stock):
                stock_code = future_to_stock[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"完成: {result}")
                except Exception as exc:
                    error_msg = f"{stock_code} generated an exception: {exc}"
                    results.append(error_msg)
                    logger.error(error_msg)
                    logger.error(traceback.format_exc())
        
        # 统计结果
        logger.info("=" * 60)
        logger.info("处理结果统计:")
        logger.info("=" * 60)
        
        success_count = sum(1 for r in results if "Success" in r)
        failed_count = sum(1 for r in results if "Failed" in r)
        skipped_count = sum(1 for r in results if "Skipped" in r)
        warning_count = sum(1 for r in results if "Warning" in r)
        
        logger.info(f"成功处理: {success_count}")
        logger.info(f"处理失败: {failed_count}")
        logger.info(f"跳过处理: {skipped_count}")
        logger.info(f"警告: {warning_count}")
        logger.info("=" * 60)
        
        # 保存指标列信息
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"{current_time} 保存指标列信息...")
        
        conn = get_db_connection()
        save_indicator_columns(conn)
        conn.close()
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"{current_time} ✅ 全部资金流指标计算完成！")
        logger.info("=" * 60)
        
    except Exception as e:
        error_msg = f"❌ 主程序错误: {str(e)}\n{traceback.format_exc()}"
        if logger:
            logger.error(error_msg)
        else:
            # 如果logger未初始化，直接打印
            print(error_msg)
            # 尝试写入文件
            try:
                log_dir = os.path.join(project_dir, 'log')
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.join(log_dir, 'Daily_TA4B_Caculate_MoneyFlow_Indicator_mproc.log')
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{datetime.now()} - ERROR - {error_msg}\n")
            except:
                pass


if __name__ == "__main__":
    main()