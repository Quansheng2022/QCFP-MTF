#!/usr/bin/env python
# coding: utf-8

"""
Name: Weekly_TA4A_Aggregate_MoneyFlow.py
Function:
周线资金流数据聚合处理
输入数据表：hk_hist_daily_moneyflow
输出数据表：hk_hist_weekly_moneyflow
"""

# ==================== 标准库导入 ====================
import os
import sys
import io
from io import StringIO
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import traceback
import contextlib

# ==================== 第三方库导入 ====================
import numpy as np
import pandas as pd

def setup_logging(log_dir: Path) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        log_dir: 日志目录路径
        
    Returns:
        配置好的日志记录器
    """
    # 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / 'Weekly_TA4A_Aggregate_MoneyFlow.log'
    
    # 创建日志记录器
    logger = logging.getLogger('Weekly_TA4A_Aggregate_MoneyFlow')
    logger.setLevel(logging.INFO)
    
    # 清除已有的处理器
    logger.handlers.clear()
    
    # 文件处理器 - 使用覆盖模式（'w' 表示覆盖写入）
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                  datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """
    获取数据库连接
    
    Args:
        db_path: 数据库文件路径
        
    Returns:
        SQLite连接对象
    """
    # 确保数据库目录存在
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    return conn

def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list:
    """
    获取表的列名列表
    
    Args:
        conn: 数据库连接
        table_name: 表名
        
    Returns:
        列名列表
    """
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return columns

def extract_stock_code(ticker: str) -> str:
    """
    从ticker中提取纯数字股票代码
    
    处理格式如：
    - "00700" -> "00700"
    - "00700.HK" -> "00700"
    - "0700" -> "00700" (补齐到5位)
    
    Args:
        ticker: 原始股票代码
        
    Returns:
        提取并格式化后的股票代码
    """
    # 移除 .HK 后缀
    if '.HK' in ticker:
        ticker = ticker.replace('.HK', '')
    
    # 如果是纯数字，补齐到5位
    if ticker.isdigit():
        ticker = ticker.zfill(5)
    
    return ticker

def get_stock_name(conn: sqlite3.Connection, stock_code: str) -> str:
    """
    从数据库获取股票名称
    
    Args:
        conn: 数据库连接
        stock_code: 股票代码
        
    Returns:
        股票名称，如果查询不到则返回股票代码
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT stock_name 
            FROM hk_hist_daily_moneyflow 
            WHERE stock_code = ? 
            LIMIT 1
        """, (stock_code,))
        result = cursor.fetchone()
        return result['stock_name'] if result else stock_code
    except Exception as e:
        # 如果查询失败，返回股票代码作为备选
        return stock_code

def check_and_process_stock(conn: sqlite3.Connection, stock_code: str, stock_name: str, 
                           logger: logging.Logger) -> None:
    """
    检查并处理单个股票的资金流整合数据
    
    Args:
        conn: 数据库连接
        stock_code: 股票代码
        stock_name: 股票名称
        logger: 日志记录器
    """
    try:
        cursor = conn.cursor()
        
        # 1. 检查原始数据表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='hk_hist_daily_moneyflow'
        """)
        if not cursor.fetchone():
            logger.error(f"原始数据表 hk_hist_daily_moneyflow 不存在")
            return
        
        # 2. 获取原始数据的最新日期
        cursor.execute("""
            SELECT MAX(date) as latest_date 
            FROM hk_hist_daily_moneyflow 
            WHERE stock_code = ?
        """, (stock_code,))
        result = cursor.fetchone()
        
        if not result or result['latest_date'] is None:
            logger.warning(f"[{stock_code} {stock_name}] 原始资金流数据表中无该股票数据")
            return
        
        daily_latest_date = pd.to_datetime(result['latest_date'])
        logger.info(f"[{stock_code} {stock_name}] 原始数据最新日期: {daily_latest_date.date()}")
        
        # 3. 检查整合数据表是否存在，如果不存在则创建
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='hk_hist_weekly_moneyflow'
        """)
        if not cursor.fetchone():
            # 创建周线资金流数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hk_hist_weekly_moneyflow (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    date DATE NOT NULL,
                    price_chgpct REAL,
                    capital_trend REAL,
                    extra_large REAL,
                    large REAL,
                    medium REAL,
                    small REAL
                )
            """)
            conn.commit()
            logger.info(f"创建周线资金流数据表 hk_hist_weekly_moneyflow")
        
        # 4. 获取整合数据的最新日期
        cursor.execute("""
            SELECT MAX(date) as latest_date 
            FROM hk_hist_weekly_moneyflow 
            WHERE stock_code = ?
        """, (stock_code,))
        result = cursor.fetchone()
        
        if result and result['latest_date'] is not None:
            weekly_latest_date = pd.to_datetime(result['latest_date'])
            logger.info(f"[{stock_code} {stock_name}] 整合数据最新日期: {weekly_latest_date.date()}")
        else:
            weekly_latest_date = None
            logger.info(f"[{stock_code} {stock_name}] 整合数据表中无该股票数据")
        
        # 5. 比较日期并决定是否计算
        if weekly_latest_date is None or weekly_latest_date < daily_latest_date:
            # 需要计算
            logger.info(f"[{stock_code} {stock_name}] 开始整合周线资金流数据...")
            aggregate_weekly_money_flow(conn, stock_code, stock_name, daily_latest_date, 
                                       weekly_latest_date, logger)
        elif weekly_latest_date == daily_latest_date:
            logger.info(f"[{stock_code} {stock_name}] 资金流整合数据已存在，无需重复计算")
        elif weekly_latest_date > daily_latest_date:
            logger.warning(f"[{stock_code} {stock_name}] 资金流原始数据缺失或K线分析数据有误，需进行核查")
            
    except Exception as e:
        logger.error(f"[{stock_code} {stock_name}] 处理失败: {str(e)}")
        logger.error(traceback.format_exc())

def aggregate_weekly_money_flow(conn: sqlite3.Connection, stock_code: str, stock_name: str,
                               daily_latest_date: pd.Timestamp, weekly_latest_date: pd.Timestamp,
                               logger: logging.Logger) -> None:
    """
    将每日资金流数据按交易周聚合，周数据日期表示为该周最后一个交易日
    
    Args:
        conn: 数据库连接
        stock_code: 股票代码
        stock_name: 股票名称
        daily_latest_date: 原始数据最新日期
        weekly_latest_date: 整合数据最新日期（可能为None）
        logger: 日志记录器
    """
    try:
        # 1. 读取该股票的每日资金流数据
        if weekly_latest_date is not None:
            query = """
                SELECT stock_code, stock_name, date, price_chgpct, capital_trend, 
                       extra_large, large, medium, small
                FROM hk_hist_daily_moneyflow
                WHERE stock_code = ? AND date > ?
                ORDER BY date ASC
            """
            df = pd.read_sql_query(query, conn, params=(stock_code, weekly_latest_date.strftime('%Y-%m-%d')))
        else:
            query = """
                SELECT stock_code, stock_name, date, price_chgpct, capital_trend, 
                       extra_large, large, medium, small
                FROM hk_hist_daily_moneyflow
                WHERE stock_code = ?
                ORDER BY date ASC
            """
            df = pd.read_sql_query(query, conn, params=(stock_code,))
        
        if df.empty:
            logger.info(f"[{stock_code} {stock_name}] 没有新的每日资金流数据需要整合")
            return
        
        logger.info(f"[{stock_code} {stock_name}] 读取到 {len(df)} 条每日资金流数据")
        
        # 2. 数据预处理
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # 数值列转换
        numeric_cols = ['price_chgpct', 'capital_trend', 'extra_large', 'large', 'medium', 'small']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 3. 创建周起始日（周一）
        df['week_start'] = df['date'] - pd.to_timedelta(df['date'].dt.weekday, unit='D')
        
        # 4. 定义聚合函数 - 使用该周最后一个交易日作为日期
        def aggregate_week(group):
            """
            聚合一周的数据，日期使用该周最后一个交易日
            """
            # 按日期排序，确保最后一个交易日是最大的日期
            group_sorted = group.sort_values('date')
            
            result = {
                'date': group_sorted['date'].iloc[-1],  # 使用该周最后一个交易日
                'price_chgpct': (1 + group['price_chgpct']).prod() - 1,
                'capital_trend': group['capital_trend'].sum(),
                'extra_large': group['extra_large'].sum(),
                'large': group['large'].sum(),
                'medium': group['medium'].sum(),
                'small': group['small'].sum()
            }
            return pd.Series(result)
        
        # 5. 执行聚合
        weekly = df.groupby('week_start', group_keys=False).apply(aggregate_week, include_groups=False).reset_index(drop=True)
        weekly = weekly.sort_values('date')
        
        logger.info(f"[{stock_code} {stock_name}] 聚合后得到 {len(weekly)} 条周线数据")
        
        # 6. 过滤出需要插入的新数据
        if weekly_latest_date is not None:
            # 只插入日期大于 weekly_latest_date 的数据
            new_weekly = weekly[weekly['date'] > weekly_latest_date]
            logger.info(f"[{stock_code} {stock_name}] 其中新增 {len(new_weekly)} 条周线数据需要插入")
        else:
            new_weekly = weekly
            logger.info(f"[{stock_code} {stock_name}] 首次处理，需要插入全部 {len(new_weekly)} 条周线数据")
        
        if new_weekly.empty:
            logger.info(f"[{stock_code} {stock_name}] 没有新的周线数据需要插入")
            return
        
        # 7. 插入新的整合数据
        cursor = conn.cursor()
        inserted_count = 0
        for _, row in new_weekly.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO hk_hist_weekly_moneyflow 
                    (stock_code, stock_name, date, price_chgpct, capital_trend, extra_large, large, medium, small)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stock_code,
                    stock_name,
                    row['date'].strftime('%Y-%m-%d'),
                    float(row['price_chgpct']) if pd.notna(row['price_chgpct']) else None,
                    float(row['capital_trend']) if pd.notna(row['capital_trend']) else None,
                    float(row['extra_large']) if pd.notna(row['extra_large']) else None,
                    float(row['large']) if pd.notna(row['large']) else None,
                    float(row['medium']) if pd.notna(row['medium']) else None,
                    float(row['small']) if pd.notna(row['small']) else None
                ))
                inserted_count += 1
            except sqlite3.IntegrityError:
                # 如果记录已存在（唯一索引冲突），跳过
                logger.debug(f"[{stock_code} {stock_name}] 记录已存在，跳过: {row['date'].strftime('%Y-%m-%d')}")
            except Exception as e:
                logger.warning(f"[{stock_code} {stock_name}] 插入数据失败: {row['date']}, 错误: {e}")
        
        conn.commit()
        logger.info(f"[{stock_code} {stock_name}] 周线资金流数据整合完成，成功插入 {inserted_count} 条记录")
        
    except Exception as e:
        logger.error(f"[{stock_code} {stock_name}] 数据聚合失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise

# === 添加UTL路径到系统路径 ===
script_dir = Path(__file__).resolve().parent
core_dir = script_dir.parent

if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

try:
    from utl.stock_analysis_utl import (
        load_config,
        setup_windows_encoding,
        GlobalConfig
    )
except ImportError as e:
    print("=" * 60)
    print("❌ 严重错误：无法导入 utl.stock_analysis_utl 模块")
    print(f"   期望路径: {core_dir / 'utl' / 'stock_analysis_utl.py'}")
    print(f"   请确认该文件存在，且 utl 包中有 __init__.py")
    print(f"   详细错误: {e}")
    print("=" * 60)
    sys.exit(1)

def main():
    """主函数，程序的入口点"""
    # 初始化日志记录器（提前初始化以便记录错误）
    logger = None
    
    try:
        # ========== 主程序路径配置 ==========
        project_dir = core_dir.parent
        config_path = project_dir / 'config' / 'stock_data_analysis.par'
        
        # ========== 加载配置 ==========
        CONFIG = load_config(str(config_path), project_dir)
        print(f"配置文件加载成功: {config_path}")
        
        # 更新全局路径配置
        GlobalConfig.update_paths(CONFIG, project_dir)
        
        # ========== 设置日志 ==========
        log_dir = Path(GlobalConfig.full_log_dir)
        logger = setup_logging(log_dir)
        
        # ========== 打印配置信息 ==========
        logger.info("=" * 60)
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件位置: {config_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"报告目录: {GlobalConfig.full_report_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        logger.info(f"数据库目录: {GlobalConfig.full_sqlite_dir}")
        logger.info(f"数据库路径: {GlobalConfig.full_db_path}")
        logger.info("=" * 60)
        
        # ========== 从配置文件获取股票代码列表 ==========
        tickers = CONFIG.get('tickers', [])
        
        if not tickers:
            logger.error("配置文件中未找到tickers设置，程序终止")
            return
        
        logger.info(f"从配置文件加载股票代码数量: {len(tickers)}")
        if len(tickers) > 5:
            logger.info(f"前5个股票代码: {tickers[:5]}... 等")
        else:
            logger.info(f"股票代码: {tickers}")
        
        # ========== 连接数据库 ==========
        db_path = Path(GlobalConfig.full_db_path)
        conn = get_db_connection(db_path)
        
        try:
            logger.info(f"数据库连接成功: {db_path}")
            
            # ========== 检查数据库表结构 ==========
            cursor = conn.cursor()
            
            # 检查原始数据表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hk_hist_daily_moneyflow'")
            if not cursor.fetchone():
                logger.error("原始数据表 hk_hist_daily_moneyflow 不存在，程序终止")
                return
            
            # 输出表结构信息
            daily_columns = get_table_columns(conn, 'hk_hist_daily_moneyflow')
            logger.info(f"hk_hist_daily_moneyflow 表列名: {daily_columns}")
            
            # ========== 处理每只股票 ==========
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"{current_time} 开始整合资金流数据...")
            
            processed_count = 0
            success_count = 0
            fail_count = 0
            
            for ticker in tickers:
                # 提取纯数字股票代码
                stock_code = extract_stock_code(ticker)
                
                logger.info("-" * 50)
                logger.info(f"处理股票: {ticker} -> 代码: {stock_code}")
                
                try:
                    # 从数据库获取股票名称
                    stock_name = get_stock_name(conn, stock_code)
                    logger.info(f"股票名称: {stock_name}")
                    
                    check_and_process_stock(conn, stock_code, stock_name, logger)
                    success_count += 1
                except Exception as e:
                    logger.error(f"处理股票 {ticker} 失败: {str(e)}")
                    fail_count += 1
                
                processed_count += 1
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"{current_time} ✅ 全部资金流数据整合完成！")
            logger.info(f"成功: {success_count}, 失败: {fail_count}, 总计: {len(tickers)}")
            
        finally:
            conn.close()
            logger.info("数据库连接已关闭")
        
    except Exception as e:
        error_msg = f"发生未知错误: {type(e).__name__}: {e}"
        if logger:
            logger.error(error_msg)
            logger.error(traceback.format_exc())
        else:
            print(error_msg)
            traceback.print_exc()
        
        if 'get_ipython' not in globals():
            sys.exit(1)
        else:
            print("在Jupyter环境中运行，程序继续但可能无法正常工作")

if __name__ == "__main__":
    main()