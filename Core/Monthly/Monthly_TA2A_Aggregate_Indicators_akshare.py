#!/usr/bin/env python
# coding: utf-8

"""
Name: Monthly_TA2A_Aggregate_Indicators_akshare.py
Function: 
月线数据聚合处理。
输入数据表：hk_hist_daily_kline
输出数据表：hk_hist_monthly_kline
"""

# ==================== 标准库导入 ====================
import io
import os
import sys
import time
import traceback
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

# ==================== 第三方库导入 ====================
import numpy as np
import pandas as pd

# ==================== 配置类 ====================
class GlobalConfig:
    full_data_dir = None
    full_report_dir = None
    full_log_dir = None
    full_temp_dir = None
    full_sqlite_dir = None
    db_name = None
    full_db_path = None

    @classmethod
    def update_paths(cls, config, project_dir):
        """更新全局路径配置"""
        cls.full_data_dir = Path(project_dir) / config.get('data_dir', 'Data')
        cls.full_report_dir = Path(project_dir) / config.get('report_dir', 'Report')
        cls.full_log_dir = Path(project_dir) / config.get('log_dir', 'Log')
        cls.full_temp_dir = Path(project_dir) / config.get('temp_dir', 'Temp')
        cls.full_sqlite_dir = Path(project_dir) / config.get('sqlite_dir', 'SQLiteDB')
        cls.db_name = config.get('db_name', 'HK_Stock.db')
        cls.full_db_path = cls.full_sqlite_dir / cls.db_name


def setup_logging(log_dir):
    """设置日志配置 - 覆盖模式，时间戳精确到秒"""
    log_file = Path(log_dir) / 'Monthly_TA2A_Aggregate_Indicators_akshare.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 清除现有的日志处理器
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # 配置日志 - 使用 'w' 模式覆盖原有日志文件
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def get_db_connection(db_path):
    """获取SQLite数据库连接"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def check_table_exists(conn, table_name):
    """检查表是否存在"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def get_table_columns(conn, table_name):
    """获取表的列名列表"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def load_config_json(config_path):
    """加载JSON格式的配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logging.error(f"加载配置文件失败: {e}")
        return {}


def load_tickers_from_config(config, config_key='tickers'):
    """
    从配置中加载股票代码列表
    参考 Weekly_TA2A_Aggregate_Indicators_akshare.py 的处理方式
    """
    tickers = config.get(config_key, [])
    if not tickers:
        logging.warning(f"配置文件中未找到 {config_key} 配置")
        return []
    
    # 如果 tickers 是字符串，按逗号分割
    if isinstance(tickers, str):
        tickers = [t.strip().zfill(5) for t in tickers.split(',') if t.strip()]
    elif isinstance(tickers, list):
        tickers = [str(t).strip().zfill(5) for t in tickers if str(t).strip()]
    else:
        logging.warning(f"不支持的 tickers 类型: {type(tickers)}")
        return []
    
    logging.info(f"从配置加载了 {len(tickers)} 个股票代码: {tickers[:5]}...")
    return tickers


def load_stock_names_from_json(json_path):
    """从stock_list.json加载股票名称映射"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        stock_name_map = {}
        
        if 'stocks' in data:
            for stock in data['stocks']:
                code = stock.get('stock_code', '').strip()
                name = stock.get('stock_name', '').strip()
                if code and name:
                    code = code.zfill(5)
                    stock_name_map[code] = name
        
        logging.info(f"从 {json_path} 加载了 {len(stock_name_map)} 个股票名称映射")
        return stock_name_map
    except Exception as e:
        logging.warning(f"加载股票名称映射时出错: {e}")
        return {}


def get_existing_monthly_dates(conn, stock_code):
    """获取已存在的月线日期"""
    cursor = conn.cursor()
    try:
        if not check_table_exists(conn, 'hk_hist_monthly_kline'):
            return set()
        
        cursor.execute("SELECT DISTINCT date FROM hk_hist_monthly_kline WHERE stock_code = ?", (stock_code,))
        results = cursor.fetchall()
        return {row[0] for row in results if row[0]}
    except sqlite3.OperationalError as e:
        logging.warning(f"查询hk_hist_monthly_kline表时出错: {e}")
        return set()


def get_daily_data_from_db(conn, stock_code, logger):
    """从hk_hist_daily_kline表读取日线数据"""
    cursor = conn.cursor()
    
    if not check_table_exists(conn, 'hk_hist_daily_kline'):
        logger.error(f"hk_hist_daily_kline 表不存在")
        return None
    
    # 先获取表的实际列名
    table_columns = get_table_columns(conn, 'hk_hist_daily_kline')
    logger.debug(f"hk_hist_daily_kline 表的列: {table_columns}")
    
    # 构建查询语句，使用实际的列名
    col_map = {col.lower(): col for col in table_columns}
    
    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover_rate']
    available_cols = []
    for col in required_cols:
        if col in col_map:
            available_cols.append(col_map[col])
        else:
            logger.warning(f"表中缺少列 '{col}'")
    
    if not available_cols:
        logger.error(f"表中没有必要的列")
        return None
    
    # 构建SELECT语句
    select_clause = ', '.join(available_cols)
    query = f"""
        SELECT {select_clause}
        FROM hk_hist_daily_kline 
        WHERE stock_code = ?
        ORDER BY date ASC
    """
    
    try:
        df = pd.read_sql_query(query, conn, params=(stock_code,))
        if df.empty:
            logger.warning(f"股票 {stock_code} 在hk_hist_daily_kline表中没有数据")
            return None
        
        # 将所有列名转换为小写
        df.columns = df.columns.str.lower()
        
        # 检查必要的列是否存在
        for col in required_cols:
            if col not in df.columns:
                logger.error(f"转换后仍然缺少列 '{col}'")
                logger.debug(f"DataFrame列: {df.columns.tolist()}")
                return None
        
        df['date'] = pd.to_datetime(df['date'])
        logger.info(f"从数据库读取到 {len(df)} 条日线数据")
        logger.info(f"日期范围: {df['date'].min()} 至 {df['date'].max()}")
        return df
    except Exception as e:
        logger.error(f"读取日线数据时出错: {e}")
        logger.error(traceback.format_exc())
        return None


def get_dynamic_cutoff_date(today, daily_dates, logger):
    """
    根据运行日期和实际交易日期列表，确定聚合截止日期（最后一个交易日）

    规则：
        - 如果 today.day < 25：返回上个月的最后一个交易日
        - 如果 today.day >= 25：返回当前已有的最新交易日（即 daily_dates 的最大值）

    参数:
        today: datetime.date 对象
        daily_dates: pandas.DatetimeIndex 或 Series，包含所有历史交易日期
        logger: 日志记录器

    返回:
        pandas.Timestamp: 截止日期
    """
    daily_dates = pd.to_datetime(daily_dates).sort_values()
    if today.day < 25:
        # 目标月份 = 上个月
        target_year = today.year
        target_month = today.month - 1
        if target_month == 0:
            target_month = 12
            target_year -= 1
        # 筛选上个月的所有交易日
        mask = (daily_dates.dt.year == target_year) & (daily_dates.dt.month == target_month)
        last_trading_day = daily_dates[mask].max()
        if pd.isna(last_trading_day):
            raise ValueError(f"上个月 ({target_year}-{target_month}) 没有交易日数据，无法确定截止日期")
        logger.info(f"运行日 {today} 小于25日，截止日期设为上月的最后一个交易日: {last_trading_day.date()}")
    else:
        # 当月，取最新交易日（日线数据中最大日期）
        last_trading_day = daily_dates.max()
        logger.info(f"运行日 {today} 大于等于25日，截止日期设为当前最后一个交易日: {last_trading_day.date()}")
    return last_trading_day


def create_monthly_table_if_not_exists(conn, logger):
    """创建hk_hist_monthly_kline表"""
    if check_table_exists(conn, 'hk_hist_monthly_kline'):
        return True
    
    cursor = conn.cursor()
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS hk_hist_monthly_kline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        stock_name TEXT,
        date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        amount REAL,
        turnover_rate REAL,
        amplitude REAL,
        change_percent REAL,
        change_amount REAL,
        ema5 REAL,
        ema10 REAL,
        ema20 REAL,
        ema50 REAL,
        ema100 REAL,
        ema200 REAL,
        macd_dif REAL,
        macd_signal REAL,
        macd_histogram REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(stock_code, date)
    )
    """
    cursor.execute(create_table_sql)
    conn.commit()
    logger.info("创建 hk_hist_monthly_kline 表")
    return True


def save_monthly_data_to_db(conn, df, stock_code, stock_name, logger):
    """保存月线数据到数据库"""
    cursor = conn.cursor()
    
    # 确保表存在
    create_monthly_table_if_not_exists(conn, logger)
    
    # 获取表的列名
    table_columns = get_table_columns(conn, 'hk_hist_monthly_kline')
    logger.debug(f"表 hk_hist_monthly_kline 的列: {table_columns}")
    
    # 准备要保存的数据
    df_to_save = df.copy()
    
    # 确保日期格式为字符串
    if 'date' in df_to_save.columns:
        df_to_save['date'] = pd.to_datetime(df_to_save['date']).dt.strftime('%Y-%m-%d')
    
    # 强制添加 stock_code 和 stock_name
    df_to_save['stock_code'] = stock_code
    df_to_save['stock_name'] = stock_name if stock_name else ''
    
    # 过滤：只保留表中存在的列
    df_to_save = df_to_save[[col for col in df_to_save.columns if col in table_columns]]
    
    logger.debug(f"过滤后列: {df_to_save.columns.tolist()}")
    logger.info(f"准备保存 {len(df_to_save)} 条记录")
    
    if df_to_save.empty:
        logger.info("没有数据需要保存")
        return 0
    
    # 获取已存在的日期
    existing_dates = get_existing_monthly_dates(conn, stock_code)
    if existing_dates:
        original_count = len(df_to_save)
        df_to_save = df_to_save[~df_to_save['date'].isin(existing_dates)]
        if len(df_to_save) < original_count:
            logger.info(f"跳过 {original_count - len(df_to_save)} 条已存在的月线记录")
        if df_to_save.empty:
            logger.info("没有新的月线数据需要保存")
            return 0
    
    # 填充NULL值
    for col in df_to_save.columns:
        if col in ['stock_name', 'stock_code']:
            df_to_save[col] = df_to_save[col].fillna('')
        elif col in ['open', 'high', 'low', 'close', 'volume', 'amount', 
                     'turnover_rate', 'amplitude', 'change_percent', 'change_amount']:
            df_to_save[col] = df_to_save[col].fillna(0)
        elif col.startswith('ema') or col.startswith('macd'):
            df_to_save[col] = df_to_save[col].fillna(0)
    
    logger.info(f"将插入 {len(df_to_save)} 条记录 (stock_name: '{stock_name}')")
    
    # 构建INSERT语句
    columns_to_insert = [col for col in df_to_save.columns if col != 'id']
    placeholders = ','.join(['?' for _ in columns_to_insert])
    columns_str = ','.join([f'"{col}"' for col in columns_to_insert])
    sql = f'INSERT OR REPLACE INTO hk_hist_monthly_kline ({columns_str}) VALUES ({placeholders})'
    
    # 批量插入
    records = df_to_save[columns_to_insert].to_records(index=False).tolist()
    
    try:
        cursor.executemany(sql, records)
        conn.commit()
        logger.info("批量插入完成")
    except Exception as e:
        logger.error(f"批量插入失败: {e}")
        # 如果批量失败，尝试逐条插入
        logger.info("尝试逐条插入...")
        success_count = 0
        for i, record in enumerate(records):
            try:
                cursor.execute(sql, record)
                success_count += 1
            except Exception as e2:
                if i < 3:
                    logger.warning(f"记录 {i} 失败: {e2}")
        conn.commit()
        logger.info(f"逐条插入成功 {success_count} 条")
    
    # 验证插入
    cursor.execute("SELECT COUNT(*) FROM hk_hist_monthly_kline WHERE stock_code = ?", (stock_code,))
    count = cursor.fetchone()[0]
    logger.info(f"验证: 表中现在有 {count} 条 {stock_code} 的记录")
    
    return len(records)


def aggregate_monthly_data(daily_df, logger, cutoff_date=None):
    """聚合日线数据为月线数据并计算技术指标"""
    if daily_df is None or daily_df.empty:
        logger.error("日线数据为空")
        return None
    
    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover_rate']
    for col in required_cols:
        if col not in daily_df.columns:
            logger.error(f"日线数据缺少列: {col}")
            return None

    daily_df = daily_df.copy()
    
    # 根据截止日期过滤数据
    if cutoff_date is not None:
        if not isinstance(cutoff_date, pd.Timestamp):
            cutoff_date = pd.Timestamp(cutoff_date)
        daily_df = daily_df[daily_df['date'] <= cutoff_date]
        logger.info(f"应用截止日期: {cutoff_date.strftime('%Y-%m-%d')}，剩余数据行数: {len(daily_df)}")
    
    daily_df.set_index('date', inplace=True)
    
    aggregation = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'amount': 'sum',
        'turnover_rate': 'sum'
    }

    monthly_df = daily_df.resample('ME').agg(aggregation)
    monthly_df.reset_index(inplace=True)
    monthly_df = monthly_df.dropna(subset=['open', 'high', 'low', 'close'])
    
    if monthly_df.empty:
        logger.warning("没有足够的月线数据")
        return None
    
    # 计算技术指标
    monthly_df['amplitude'] = (monthly_df['high'] - monthly_df['low']) / monthly_df['open'] * 100
    monthly_df['change_percent'] = monthly_df['close'].pct_change() * 100
    monthly_df['change_amount'] = monthly_df['close'].diff()

    periods = [5, 10, 20, 50, 100, 200]
    for period in periods:
        monthly_df[f'ema{period}'] = monthly_df['close'].ewm(span=period, adjust=False).mean()

    ema12 = monthly_df['close'].ewm(span=12, adjust=False).mean()
    ema26 = monthly_df['close'].ewm(span=26, adjust=False).mean()
    monthly_df['macd_dif'] = ema12 - ema26
    monthly_df['macd_signal'] = monthly_df['macd_dif'].ewm(span=9, adjust=False).mean()
    monthly_df['macd_histogram'] = 2 * (monthly_df['macd_dif'] - monthly_df['macd_signal'])

    all_columns = monthly_df.columns.tolist()
    new_columns = ['date'] + [col for col in all_columns if col != 'date']
    monthly_df = monthly_df[new_columns]

    logger.info(f"生成 {len(monthly_df)} 条月线数据 (含技术指标)")
    logger.info(f"月线日期范围: {monthly_df['date'].min()} 至 {monthly_df['date'].max()}")
    return monthly_df


def get_all_stocks_in_db(conn, logger):
    """获取数据库中所有有日线数据的股票代码"""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT stock_code FROM hk_hist_daily_kline ORDER BY stock_code")
        results = cursor.fetchall()
        stocks = [row[0] for row in results]
        logger.info(f"数据库中共有 {len(stocks)} 只股票有日线数据")
        if len(stocks) <= 20:
            logger.info(f"数据库中的股票: {stocks}")
        else:
            logger.info(f"数据库中的股票(前20个): {stocks[:20]}... 等")
        return stocks
    except Exception as e:
        logger.error(f"获取数据库股票列表失败: {e}")
        return []


def check_stock_data_availability(conn, tickers, logger):
    """
    检查哪些股票在数据库中有日线数据
    
    Args:
        conn: 数据库连接
        tickers: 股票代码列表
        logger: 日志记录器
        
    Returns:
        tuple: (有数据的股票列表, 无数据的股票列表)
    """
    cursor = conn.cursor()
    available_stocks = []
    missing_stocks = []
    
    for ticker in tickers:
        cursor.execute(
            "SELECT COUNT(*) FROM hk_hist_daily_kline WHERE stock_code = ?", 
            (ticker,)
        )
        count = cursor.fetchone()[0]
        if count > 0:
            available_stocks.append(ticker)
        else:
            missing_stocks.append(ticker)
    
    if missing_stocks:
        logger.warning(f"以下股票在数据库中没有日线数据: {missing_stocks}")
    
    logger.info(f"有日线数据的股票: {len(available_stocks)} 只")
    return available_stocks, missing_stocks


# ==================== 主程序 ====================
def main():
    """主函数，程序的入口点"""
    # ★★★ 在函数开始时就设置 logger，避免异常时 logging 未定义 ★★★
    logger = None
    
    try:
        # 获取项目根目录
        script_dir = Path(__file__).resolve().parent
        core_dir = script_dir.parent
        if str(core_dir) not in sys.path:
            sys.path.insert(0, str(core_dir))
        
        from utl.stock_analysis_utl import get_project_root
        core_dir_from_utils = get_project_root()
        project_dir = core_dir_from_utils.parent
        
        if str(project_dir) not in sys.path:
            sys.path.insert(0, str(project_dir))
        
        from utl.stock_analysis_utl import (
            load_config,
            setup_windows_encoding,
            GlobalConfig as UtlGlobalConfig
        )
        
        # 设置编码
        setup_windows_encoding()
        
        # ★★★ 先设置基本的日志，以便在配置加载过程中有日志记录 ★★★
        # 使用临时日志目录
        temp_log_dir = Path(project_dir) / 'Log'
        temp_log_dir.mkdir(parents=True, exist_ok=True)
        logger = setup_logging(temp_log_dir)
        
        # 加载 stock_data_analysis.par 配置
        par_config_path = os.path.join(project_dir, 'config', 'stock_data_analysis.par')
        CONFIG = load_config(par_config_path, project_dir)
        
        if not CONFIG:
            logger.error(f"配置文件加载失败或为空: {par_config_path}")
            return
        
        # 更新全局配置
        GlobalConfig.full_data_dir = Path(project_dir) / CONFIG.get('data_dir', 'Data')
        GlobalConfig.full_report_dir = Path(project_dir) / CONFIG.get('report_dir', 'Report')
        GlobalConfig.full_log_dir = Path(project_dir) / CONFIG.get('log_dir', 'Log')
        GlobalConfig.full_temp_dir = Path(project_dir) / CONFIG.get('temp_dir', 'Temp')
        GlobalConfig.full_sqlite_dir = Path(project_dir) / CONFIG.get('sqlite_dir', 'SQLiteDB')
        GlobalConfig.db_name = CONFIG.get('db_name', 'HK_Stock.db')
        GlobalConfig.full_db_path = GlobalConfig.full_sqlite_dir / GlobalConfig.db_name
        
        # ★★★ 重新设置日志，使用正确的日志目录 ★★★
        logger = setup_logging(GlobalConfig.full_log_dir)
        
        logger.info("=" * 70)
        logger.info("✅ 运行版本: v3.2 - 从stock_data_analysis.par读取股票列表")
        logger.info("=" * 70)
        logger.info("=" * 50)
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件位置: {par_config_path}")
        logger.info(f"日志文件位置: {GlobalConfig.full_log_dir / 'Monthly_TA2A_Aggregate_Indicators_akshare.log'}")
        logger.info(f"数据库路径: {GlobalConfig.full_db_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")

        # 从配置中加载股票代码列表
        tickers = load_tickers_from_config(CONFIG, 'tickers')

        if not tickers:
            logger.error("无法从stock_data_analysis.par加载股票代码列表")
            # 尝试从stock_list.json加载作为备选
            logger.info("尝试从stock_list.json加载股票代码...")
            stock_list_path = os.path.join(project_dir, 'config', 'stock_list.json')
            stock_name_map = load_stock_names_from_json(stock_list_path)
            # 从 stock_name_map 的 keys 获取股票代码
            tickers = list(stock_name_map.keys())
            if tickers:
                logger.info(f"从stock_list.json加载了 {len(tickers)} 个股票代码")
            else:
                logger.error("所有来源都无法加载股票代码列表")
                return

        logger.info(f"股票代码列表 (前5个): {tickers[:5] if len(tickers) > 5 else tickers}")
        logger.info(f"共 {len(tickers)} 个股票")
        
        # 加载股票名称映射（从stock_list.json获取名称）
        stock_list_path = os.path.join(project_dir, 'config', 'stock_list.json')
        stock_name_map = load_stock_names_from_json(stock_list_path)

        # 使用配置中的数据库路径
        db_path = GlobalConfig.full_db_path
        if not os.path.exists(db_path):
            logger.error(f"数据库文件不存在: {db_path}")
            return
            
        db_connection = get_db_connection(db_path)
        logger.info(f"成功连接到数据库: {db_path}")
        
        if not check_table_exists(db_connection, 'hk_hist_daily_kline'):
            logger.error("hk_hist_daily_kline 表不存在")
            db_connection.close()
            return
        
        # ===== 数据可用性检查 =====
        logger.info("=" * 70)
        logger.info("📊 数据可用性检查")
        logger.info("=" * 70)
        
        # 1. 显示配置中的股票
        logger.info(f"配置文件中的股票: {len(tickers)} 只")
        if len(tickers) <= 20:
            logger.info(f"股票列表: {tickers}")
        else:
            logger.info(f"股票列表(前20个): {tickers[:20]}... 等")
        
        # 2. 显示数据库中的股票
        db_stocks = get_all_stocks_in_db(db_connection, logger)
        
        # 3. 找出交集和差异
        config_set = set(tickers)
        db_set = set(db_stocks)
        common = config_set & db_set
        only_in_config = config_set - db_set
        only_in_db = db_set - config_set
        
        logger.info(f"在配置和数据库中都存在的股票: {len(common)} 只")
        if only_in_config:
            logger.warning(f"⚠️ 仅在配置中但数据库中没有的股票: {len(only_in_config)} 只")
            if len(only_in_config) <= 20:
                logger.warning(f"    {sorted(only_in_config)}")
            else:
                logger.warning(f"    (前20个) {sorted(only_in_config)[:20]}... 等")
        if only_in_db:
            logger.info(f"仅在数据库中的股票: {len(only_in_db)} 只")
            if len(only_in_db) <= 20:
                logger.info(f"    {sorted(only_in_db)}")
            else:
                logger.info(f"    (前20个) {sorted(only_in_db)[:20]}... 等")
        
        # 4. 使用交集进行后续处理
        tickers_to_process = list(common)
        if not tickers_to_process:
            logger.error("❌ 没有股票同时存在于配置和数据库中")
            db_connection.close()
            return
        
        logger.info(f"✅ 将处理 {len(tickers_to_process)} 只股票")
        logger.info("=" * 70)

        today = datetime.now().date()
        logger.info(f"运行日期: {today}")
        logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始整合交易数据...")
        
        # 处理每个股票
        total_inserted = 0
        for ticker in tickers_to_process:
            ticker = str(ticker).zfill(5)
            
            logger.info(f"\n{'='*60}")
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 处理股票: {ticker}")
            logger.info(f"{'='*60}")

            stock_name = stock_name_map.get(ticker, '')
            logger.info(f"股票名称: '{stock_name}'")

            daily_df = get_daily_data_from_db(db_connection, ticker, logger)
            if daily_df is None or daily_df.empty:
                logger.warning(f"股票 {ticker} 无日线数据，跳过")
                continue
            
            # 确定动态截止日期（实际交易日）
            try:
                cutoff_date = get_dynamic_cutoff_date(today, daily_df['date'], logger)
            except ValueError as e:
                logger.error(f"计算截止日期失败: {e}，跳过 {ticker}")
                continue
            
            monthly_df = aggregate_monthly_data(daily_df, logger, cutoff_date=cutoff_date)
            if monthly_df is None or monthly_df.empty:
                logger.warning(f"股票 {ticker} 月线数据聚合失败，跳过")
                continue
            
            saved_count = save_monthly_data_to_db(db_connection, monthly_df, ticker, stock_name, logger)
            if saved_count > 0:
                total_inserted += saved_count
                logger.info(f"成功保存 {saved_count} 条月线记录")
            else:
                logger.info("没有新的月线记录需要保存")
            
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 股票 {ticker} 处理完成")

        # 最终统计
        cursor = db_connection.cursor()
        if check_table_exists(db_connection, 'hk_hist_monthly_kline'):
            cursor.execute("SELECT COUNT(*) FROM hk_hist_monthly_kline")
            final_count = cursor.fetchone()[0]
            logger.info(f"\n📊 最终统计: hk_hist_monthly_kline 表共有 {final_count} 条记录")
            
            cursor.execute("""
                SELECT stock_code, stock_name, COUNT(*) as cnt 
                FROM hk_hist_monthly_kline 
                GROUP BY stock_code, stock_name
                ORDER BY stock_code
            """)
            for row in cursor.fetchall():
                logger.info(f"    - {row[0]} ({row[1]}): {row[2]} 条")
        
        db_connection.close()
        logger.info(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ✅ 全部完成！共插入 {total_inserted} 条月线记录")

    except Exception as e:
        # ★★★ 使用 logger 如果已初始化，否则使用 print ★★★
        if logger:
            logger.error(f"发生未知错误: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
        else:
            print(f"发生未知错误: {type(e).__name__}: {e}")
            print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()