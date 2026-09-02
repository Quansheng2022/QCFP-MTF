#!/usr/bin/env python
# coding: utf-8

"""
Name: Quarterly_TA4D_Analyze_chip.py
Function:
季度筹码结构联合分析（Chip × Flow × Price）。
结合 hk_quarterly_institutional_holdings_analysis（筹码）、
hk_quarterly_kline_analysis（价格）与 hk_quarterly_moneyflow_analysis（资金流），
生成三维联合筹码分析结果，保存到 hk_quarterly_chip_analysis。

输入数据表：
- hk_quarterly_institutional_holdings_analysis
- hk_quarterly_kline_analysis
- hk_quarterly_moneyflow_analysis
输出数据表：hk_quarterly_chip_analysis

说明：
- 以筹码分析表为主表，通过 quarter_end_date = date 与季线/季度资金流对齐；
- chip/flow/price 三方方向（+1/-1/0）用于判断共振/背离及 QCFP 状态；
- 若某张输入表暂无数据，相应字段为 NULL、方向为 0，不影响整体流程。
"""

# ==================== 标准库导入 ====================
import os
import sys
import io
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
import traceback

# ==================== 第三方库导入 ====================
import numpy as np
import pandas as pd


def setup_logging(log_dir: Path) -> logging.Logger:
    """设置日志记录器（覆盖模式）"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'Quarterly_TA4D_Analyze_chip.log'

    logger = logging.getLogger('Quarterly_TA4D_Analyze_chip')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def check_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """检查表是否存在"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def _clip(value, lo=0.0, hi=100.0):
    if value is None or pd.isna(value):
        return None
    return float(min(hi, max(lo, value)))


def _direction_from_score(score, up=60.0, down=40.0):
    """根据 0-100 评分编码方向：>=60 -> +1，<=40 -> -1，否则 0"""
    if score is None or pd.isna(score):
        return 0
    if score >= up:
        return 1
    if score <= down:
        return -1
    return 0


def _direction_from_fbi(fbi, up=0.1, down=-0.1):
    """根据 FBI 编码资金流方向：机构净流入 -> +1，净流出 -> -1"""
    if fbi is None or pd.isna(fbi):
        return 0
    if fbi > up:
        return 1
    if fbi < down:
        return -1
    return 0


def _direction_from_price(change_percent, macd_status):
    """根据季度涨跌幅（辅以 MACD 状态）编码价格方向"""
    if change_percent is not None and pd.notna(change_percent):
        if change_percent >= 5.0:
            return 1
        if change_percent <= -5.0:
            return -1
    if macd_status and isinstance(macd_status, str):
        if '金叉' in macd_status:
            return 1
        if '死叉' in macd_status:
            return -1
    return 0


def _align(a, b):
    """两个方向的对齐关系：同向非零 -> 共振；异向非零 -> 背离；否则中性"""
    if a != 0 and b != 0:
        if a == b:
            return '共振'
        return '背离'
    return '中性'


def _flow_bias(fbi):
    if fbi is None or pd.isna(fbi):
        return 'N/A'
    if fbi > 0.1:
        return '机构净流入'
    if fbi < -0.1:
        return '机构净流出'
    return '均衡'


def _price_trend_label(direction):
    if direction == 1:
        return '上行'
    if direction == -1:
        return '下行'
    return '震荡'


QCFP_REGIME_MAP = {
    (1, 1, 1): '多头共振',
    (1, 1, 0): '吸筹蓄势',
    (1, 1, -1): '吸筹回调',
    (1, 0, 1): '筹码走强',
    (1, 0, 0): '筹码偏多',
    (1, 0, -1): '筹码顶背离',
    (1, -1, 1): '价量背离',
    (1, -1, 0): '资金流出吸筹',
    (1, -1, -1): '派发确认',
    (0, 1, 1): '资金推动',
    (0, 1, 0): '资金流入',
    (0, 1, -1): '资金流入回落',
    (0, 0, 1): '价涨筹码平稳',
    (0, 0, 0): '中性观察',
    (0, 0, -1): '价跌筹码平稳',
    (0, -1, 1): '资金流出反弹',
    (0, -1, 0): '资金流出',
    (0, -1, -1): '资金流出下跌',
    (-1, 1, 1): '筹码分散上涨',
    (-1, 1, 0): '筹码分散',
    (-1, 1, -1): '多空分歧',
    (-1, 0, 1): '价格独立走强',
    (-1, 0, 0): '筹码偏空',
    (-1, 0, -1): '筹码底背离',
    (-1, -1, 1): '派发反弹',
    (-1, -1, 0): '派发蓄势',
    (-1, -1, -1): '空头共振',
}


def _qcfp_regime(c, f, p):
    return QCFP_REGIME_MAP.get((c, f, p), '中性观察')


def compute_integrated_chip_analysis(df_chip: pd.DataFrame, df_kline: pd.DataFrame,
                                     df_flow: pd.DataFrame) -> pd.DataFrame:
    """
    以筹码分析表为主表，左连接季线与季度资金流，计算三维联合分析字段。

    输入：
    - df_chip: hk_quarterly_institutional_holdings_analysis 全量数据
    - df_kline: hk_quarterly_kline_analysis 的 (stock_code, date, close, change_percent,
               macd_status, ema5_10_status, rsi14)
    - df_flow: hk_quarterly_moneyflow_analysis 的 (stock_code, date, institutional_flow,
              individual_flow, idr, fbi)
    """
    df = df_chip.copy()
    if df.empty:
        return df

    # 与季线对齐
    kline = df_kline.copy()
    if not kline.empty:
        kline = kline.drop_duplicates(subset=['stock_code', 'date']).rename(columns={'date': 'quarter_end_date'})
        df = df.merge(
            kline[['stock_code', 'quarter_end_date', 'close', 'change_percent',
                   'macd_status', 'ema5_10_status', 'rsi14']],
            on=['stock_code', 'quarter_end_date'], how='left'
        )
    else:
        for col in ['close', 'change_percent', 'macd_status', 'ema5_10_status', 'rsi14']:
            df[col] = None

    # 与季度资金流对齐
    flow = df_flow.copy()
    if not flow.empty:
        flow = flow.drop_duplicates(subset=['stock_code', 'date']).rename(columns={'date': 'quarter_end_date'})
        df = df.merge(
            flow[['stock_code', 'quarter_end_date', 'institutional_flow',
                  'individual_flow', 'idr', 'fbi']],
            on=['stock_code', 'quarter_end_date'], how='left'
        )
    else:
        for col in ['institutional_flow', 'individual_flow', 'idr', 'fbi']:
            df[col] = None

    # 三维方向
    df['chip_direction'] = df['chip_structure_score'].apply(
        lambda v: _direction_from_score(v))
    df['flow_direction'] = df['fbi'].apply(lambda v: _direction_from_fbi(v))
    df['price_direction'] = [
        _direction_from_price(c, m) for c, m in zip(df['change_percent'], df['macd_status'])
    ]

    # 对齐关系
    df['chip_flow_alignment'] = [
        _align(c, f) for c, f in zip(df['chip_direction'], df['flow_direction'])
    ]
    df['chip_price_alignment'] = [
        _align(c, p) for c, p in zip(df['chip_direction'], df['price_direction'])
    ]
    df['flow_price_alignment'] = [
        _align(f, p) for f, p in zip(df['flow_direction'], df['price_direction'])
    ]

    # QCFP 状态与综合评分
    df['chip_flow_price_regime'] = [
        _qcfp_regime(c, f, p)
        for c, f, p in zip(df['chip_direction'], df['flow_direction'], df['price_direction'])
    ]

    integrated = []
    summaries = []
    for _, row in df.iterrows():
        chip_score = float(row['chip_structure_score']) if pd.notna(row['chip_structure_score']) else 50.0
        fbi_v = float(row['fbi']) if pd.notna(row['fbi']) else None
        chg_v = float(row['change_percent']) if pd.notna(row['change_percent']) else None

        flow_score = 50.0 + 50.0 * np.tanh(fbi_v / 0.3) if fbi_v is not None else 50.0
        price_score = 50.0 + 50.0 * np.tanh(chg_v / 15.0) if chg_v is not None else 50.0
        score = 0.4 * chip_score + 0.3 * flow_score + 0.3 * price_score
        integrated.append(_clip(score))

        fbi_str = f"{fbi_v:.2f}" if fbi_v is not None else "N/A"
        chg_str = f"{chg_v:.1f}%" if chg_v is not None else "N/A"
        summaries.append(
            f"{row['chip_flow_price_regime']}；筹码评分 {chip_score:.0f}；"
            f"FBI {fbi_str}；季度涨跌 {chg_str}"
        )
    df['integrated_score'] = integrated
    df['signal_summary'] = summaries

    # 标签字段
    df['flow_bias'] = df['fbi'].apply(lambda v: _flow_bias(v))
    df['price_trend'] = df['price_direction'].apply(lambda v: _price_trend_label(v))
    df['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return df


def create_chip_table_if_not_exists(conn: sqlite3.Connection) -> None:
    """确保 hk_quarterly_chip_analysis 表存在"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hk_quarterly_chip_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            quarter TEXT NOT NULL,
            quarter_end_date TEXT,
            chip_structure_score REAL,
            chip_regime TEXT,
            chip_migration_status TEXT,
            chip_migration_score REAL,
            institution_participation_score REAL,
            institutional_concentration_score REAL,
            holder_pct REAL,
            holder_pct_qoq_pp REAL,
            institution_quantity_qoq INTEGER,
            institutional_flow REAL,
            individual_flow REAL,
            idr REAL,
            fbi REAL,
            flow_bias TEXT,
            close REAL,
            change_percent REAL,
            macd_status TEXT,
            ema5_10_status TEXT,
            rsi14 REAL,
            price_trend TEXT,
            chip_direction INTEGER,
            flow_direction INTEGER,
            price_direction INTEGER,
            chip_flow_alignment TEXT,
            chip_price_alignment TEXT,
            flow_price_alignment TEXT,
            chip_flow_price_regime TEXT,
            integrated_score REAL,
            signal_summary TEXT,
            update_time TEXT,
            UNIQUE(stock_code, quarter)
        )
    """)
    conn.commit()


def save_chip_analysis_to_db(conn: sqlite3.Connection, df: pd.DataFrame,
                             logger: logging.Logger) -> int:
    """保存联合分析结果（先清空旧数据再全量插入）"""
    if df is None or df.empty:
        return 0

    cursor = conn.cursor()
    cursor.execute("DELETE FROM hk_quarterly_chip_analysis")

    columns = [
        'stock_code', 'stock_name', 'quarter', 'quarter_end_date',
        'chip_structure_score', 'chip_regime', 'chip_migration_status',
        'chip_migration_score', 'institution_participation_score',
        'institutional_concentration_score', 'holder_pct', 'holder_pct_qoq_pp',
        'institution_quantity_qoq',
        'institutional_flow', 'individual_flow', 'idr', 'fbi', 'flow_bias',
        'close', 'change_percent', 'macd_status', 'ema5_10_status', 'rsi14',
        'price_trend',
        'chip_direction', 'flow_direction', 'price_direction',
        'chip_flow_alignment', 'chip_price_alignment', 'flow_price_alignment',
        'chip_flow_price_regime', 'integrated_score', 'signal_summary',
        'update_time',
    ]

    records = []
    for _, row in df.iterrows():
        def _val(key):
            v = row.get(key)
            return None if v is None or pd.isna(v) else v
        records.append(tuple(_val(col) for col in columns))

    if not records:
        conn.commit()
        return 0

    placeholders = ', '.join(['?'] * len(columns))
    columns_str = ', '.join(columns)
    sql = f"INSERT INTO hk_quarterly_chip_analysis ({columns_str}) VALUES ({placeholders})"
    cursor.executemany(sql, records)
    conn.commit()
    return len(records)


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
    print(f"   详细错误: {e}")
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


def main():
    """主函数，程序的入口点"""
    logger = None
    try:
        # ========== 路径与配置 ==========
        project_dir = core_dir.parent
        config_path = project_dir / 'config' / 'stock_data_analysis.par'
        CONFIG = load_config(str(config_path), project_dir)
        print(f"配置文件加载成功: {config_path}")

        GlobalConfig.update_paths(CONFIG, project_dir)

        log_dir = Path(GlobalConfig.full_log_dir)
        logger = setup_logging(log_dir)

        logger.info("=" * 70)
        logger.info("Quarterly_TA4D_Analyze_chip 启动")
        logger.info("=" * 70)
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"数据库路径: {GlobalConfig.full_db_path}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")

        db_path = Path(GlobalConfig.full_db_path)
        if not db_path.exists():
            logger.error(f"数据库文件不存在: {db_path}")
            return

        conn = get_db_connection(db_path)
        try:
            required = ['hk_quarterly_institutional_holdings_analysis',
                        'hk_quarterly_kline_analysis',
                        'hk_quarterly_moneyflow_analysis']
            for t in required:
                if not check_table_exists(conn, t):
                    logger.warning(f"输入表 {t} 不存在，请先运行对应步骤")

            create_chip_table_if_not_exists(conn)

            # 筹码主表
            if check_table_exists(conn, 'hk_quarterly_institutional_holdings_analysis'):
                df_chip = pd.read_sql_query(
                    """
                    SELECT stock_code, stock_name, quarter, quarter_end_date,
                           chip_structure_score, chip_regime, chip_migration_status,
                           chip_migration_score, institution_participation_score,
                           institutional_concentration_score, holder_pct,
                           holder_pct_qoq_pp, institution_quantity_qoq
                    FROM hk_quarterly_institutional_holdings_analysis
                    """,
                    conn
                )
            else:
                df_chip = pd.DataFrame()

            logger.info(f"筹码分析数据: {len(df_chip)} 行")
            if df_chip.empty:
                logger.warning("⚠️ hk_quarterly_institutional_holdings_analysis 无数据，"
                               "请先运行 Quarterly_TA4C_Analyze_institutional_holdings.py")
                return

            # 季线（价格）
            if check_table_exists(conn, 'hk_quarterly_kline_analysis'):
                df_kline = pd.read_sql_query(
                    """
                    SELECT stock_code, date, close, change_percent,
                           macd_status, ema5_10_status, rsi14
                    FROM hk_quarterly_kline_analysis
                    """,
                    conn
                )
            else:
                df_kline = pd.DataFrame()
            logger.info(f"季线分析数据: {len(df_kline)} 行")

            # 季度资金流
            if check_table_exists(conn, 'hk_quarterly_moneyflow_analysis'):
                df_flow = pd.read_sql_query(
                    """
                    SELECT stock_code, date, institutional_flow, individual_flow, idr, fbi
                    FROM hk_quarterly_moneyflow_analysis
                    """,
                    conn
                )
            else:
                df_flow = pd.DataFrame()
            logger.info(f"季度资金流分析数据: {len(df_flow)} 行")

            df_result = compute_integrated_chip_analysis(df_chip, df_kline, df_flow)
            saved = save_chip_analysis_to_db(conn, df_result, logger)
            logger.info(f"✅ 联合筹码分析完成，保存 {saved} 条记录到 hk_quarterly_chip_analysis")

            # 简要输出最新状态分布
            if not df_result.empty:
                regime_counts = df_result['chip_flow_price_regime'].value_counts().head(8)
                for regime, cnt in regime_counts.items():
                    logger.info(f"    - {regime}: {cnt}")
        finally:
            conn.close()
    except Exception as e:
        if logger:
            logger.error(f"发生未知错误: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
        else:
            print(f"发生未知错误: {type(e).__name__}: {e}")
            print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
