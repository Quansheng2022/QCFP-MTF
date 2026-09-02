#!/usr/bin/env python
# coding: utf-8

"""
Name: Quarterly_TA4C_Analyze_institutional_holdings.py
Function:
季度机构持股数据分析（筹码基础因子表）。
在 hk_hist_institutional_holdings 原始季度持股数据基础上，计算
QoQ / YoY / 4Q 变化、趋势、筹码迁移、机构参与度、集中度代理、
筹码结构评分与筹码状态（Regime），结果保存到 hk_quarterly_institutional_holdings_analysis。

输入数据表：hk_hist_institutional_holdings
输出数据表：hk_quarterly_institutional_holdings_analysis

说明：
- 原始数据为季度聚合口径（institution_quantity / holder_quantity / holder_pct），
  不含机构明细，因此集中度等字段为代理变量，仅用于趋势判断；
- 采用 Raw → Change → Trend → Migration → Score → Regime 六层结构，
  原始值忠实保留，所有派生字段均可追溯。
"""

# ==================== 标准库导入 ====================
import os
import sys
import io
import re
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
    log_file = log_dir / 'Quarterly_TA4C_Analyze_institutional_holdings.log'

    logger = logging.getLogger('Quarterly_TA4C_Analyze_institutional_holdings')
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


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list:
    """获取表的列名列表"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def parse_quarter(period_text):
    """
    解析 period_text 为 (year, quarter)。
    支持 '2026/Q2'、'2026Q2'、'2026-Q2' 等格式。
    """
    if period_text is None:
        return None
    m = re.match(r'^\s*(\d{4})\s*[/\-]?\s*[Qq]([1-4])\s*$', str(period_text).strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def quarter_end_date(year, quarter):
    """季度结束日期（自然日），如 2026/Q2 -> 2026-06-30"""
    return pd.Period(f'{year}Q{quarter}').end_time.strftime('%Y-%m-%d')


def _pct_change(cur, prev):
    """百分比变化，prev 为 0/缺失时返回 None"""
    if cur is None or prev is None or prev == 0:
        return None
    try:
        return (float(cur) - float(prev)) / abs(float(prev)) * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _trend_from_pct(v, up_strong=20.0, up=5.0):
    """按百分比变化编码趋势：+2 强升 / +1 升 / 0 稳定 / -1 降 / -2 强降"""
    if v is None or pd.isna(v):
        return 0
    if v >= up_strong:
        return 2
    if v >= up:
        return 1
    if v <= -up_strong:
        return -2
    if v <= -up:
        return -1
    return 0


def _trend_from_pp(v, up_strong=1.0, up=0.25):
    """按百分点变化编码趋势"""
    return _trend_from_pct(v, up_strong, up)


def _clip(value, lo=0.0, hi=100.0):
    if value is None or pd.isna(value):
        return None
    return float(min(hi, max(lo, value)))


def compute_holdings_analysis(df_stock: pd.DataFrame) -> pd.DataFrame:
    """
    对单只股票的季度持股序列计算全部派生字段。

    输入列：quarter, quarter_end_date, institution_quantity, holder_quantity,
            holder_pct, quarter_end_price, data_source
    返回：按季度升序的完整分析 DataFrame。
    """
    df = df_stock.sort_values('quarter').reset_index(drop=True).copy()

    # ---- 原始字段（忠实保留）----
    df['institution_quantity'] = pd.to_numeric(df['institution_quantity'], errors='coerce')
    df['holder_quantity'] = pd.to_numeric(df['holder_quantity'], errors='coerce')
    df['holder_pct'] = pd.to_numeric(df['holder_pct'], errors='coerce')
    df['quarter_end_price'] = pd.to_numeric(df['quarter_end_price'], errors='coerce')

    # ---- QoQ（与上一季度比较）----
    prev_inst = df['institution_quantity'].shift(1)
    prev_hold = df['holder_quantity'].shift(1)
    prev_pct = df['holder_pct'].shift(1)

    df['institution_quantity_qoq'] = df['institution_quantity'] - prev_inst
    df['institution_quantity_qoq_pct'] = [
        _pct_change(c, p) for c, p in zip(df['institution_quantity'], prev_inst)
    ]
    df['holder_quantity_qoq'] = df['holder_quantity'] - prev_hold
    df['holder_quantity_qoq_pct'] = [
        _pct_change(c, p) for c, p in zip(df['holder_quantity'], prev_hold)
    ]
    df['holder_pct_qoq_pp'] = df['holder_pct'] - prev_pct

    # ---- YoY / 4Q（与 4 个季度前比较）----
    prev4_inst = df['institution_quantity'].shift(4)
    prev4_hold = df['holder_quantity'].shift(4)
    prev4_pct = df['holder_pct'].shift(4)

    df['institution_quantity_yoy_pct'] = [
        _pct_change(c, p) for c, p in zip(df['institution_quantity'], prev4_inst)
    ]
    df['holder_quantity_yoy_pct'] = [
        _pct_change(c, p) for c, p in zip(df['holder_quantity'], prev4_hold)
    ]
    df['holder_pct_yoy_pp'] = df['holder_pct'] - prev4_pct

    df['institution_quantity_4q_change'] = df['institution_quantity'] - prev4_inst
    df['holder_quantity_4q_change'] = df['holder_quantity'] - prev4_hold
    df['holder_pct_4q_change_pp'] = df['holder_pct'] - prev4_pct

    # ---- 趋势编码（-2..+2）----
    df['institution_trend'] = df['institution_quantity_qoq_pct'].apply(
        lambda v: _trend_from_pct(v, up_strong=20.0, up=5.0))
    df['holder_trend'] = df['holder_quantity_qoq_pct'].apply(
        lambda v: _trend_from_pct(v, up_strong=10.0, up=2.0))
    df['holder_pct_trend'] = df['holder_pct_qoq_pp'].apply(
        lambda v: _trend_from_pp(v, up_strong=1.0, up=0.25))

    # ---- 筹码迁移 ----
    migration_scores = []
    migration_statuses = []
    for _, row in df.iterrows():
        qoq_pct = row['institution_quantity_qoq_pct']
        qoq_pp = row['holder_pct_qoq_pp']
        inst_up = qoq_pct is not None and pd.notna(qoq_pct) and qoq_pct > 0.5
        inst_down = qoq_pct is not None and pd.notna(qoq_pct) and qoq_pct < -0.5
        pct_up = qoq_pp is not None and pd.notna(qoq_pp) and qoq_pp > 0.05
        pct_down = qoq_pp is not None and pd.notna(qoq_pp) and qoq_pp < -0.05

        if inst_up and pct_up:
            status = 'ACCUMULATION'      # 吸筹：机构参与上升 + 持股比例上升
        elif inst_down and pct_down:
            status = 'DISTRIBUTION'      # 派发：机构参与下降 + 持股比例下降
        elif inst_up and pct_down:
            status = 'DISPERSION'        # 分散/分歧：机构数量上升但持股比例下降
        elif inst_down and pct_up:
            status = 'CONCENTRATION'     # 集中：机构数量下降但持股比例上升
        else:
            status = 'NEUTRAL'

        qoq_pct_v = float(qoq_pct) if qoq_pct is not None and pd.notna(qoq_pct) else 0.0
        qoq_pp_v = float(qoq_pp) if qoq_pp is not None and pd.notna(qoq_pp) else 0.0
        score = 0.5 * np.tanh(qoq_pct_v / 25.0) + 0.5 * np.tanh(qoq_pp_v / 1.5)
        migration_scores.append(_clip(score, -1.0, 1.0))
        migration_statuses.append(status)

    df['chip_migration_score'] = migration_scores
    df['chip_migration_status'] = migration_statuses

    # ---- 机构参与度评分（0-100）----
    participation = []
    for _, row in df.iterrows():
        quantity = row['institution_quantity']
        quantity_v = float(quantity) if quantity is not None and pd.notna(quantity) else 0.0
        level_bonus = min(20.0, max(0.0, np.log10(max(quantity_v, 1.0)) * 5.0))
        qoq_pct_v = float(row['institution_quantity_qoq_pct']) \
            if pd.notna(row['institution_quantity_qoq_pct']) else 0.0
        yoy_pct_v = float(row['institution_quantity_yoy_pct']) \
            if pd.notna(row['institution_quantity_yoy_pct']) else 0.0
        pct_v = float(row['holder_pct']) if pd.notna(row['holder_pct']) else 0.0
        score = 50.0 + level_bonus + 15.0 * np.tanh(qoq_pct_v / 20.0) \
            + 15.0 * np.tanh(yoy_pct_v / 40.0) + 10.0 * pct_v / 100.0
        participation.append(_clip(score))
    df['institution_participation_score'] = participation

    # ---- 集中度代理（0-100，= holder_pct，真实集中度需机构明细）----
    df['institutional_concentration_score'] = df['holder_pct'].apply(
        lambda v: _clip(v) if v is not None and pd.notna(v) else None)

    # ---- 筹码结构评分（六层加权）----
    def _comp_from_trend(t):
        return 50.0 + float(t) * 20.0

    def _comp_from_pp(v):
        if v is None or pd.isna(v):
            return 50.0
        return 50.0 + 50.0 * np.tanh(float(v) / 4.0)

    chip_scores = []
    regimes = []
    for _, row in df.iterrows():
        part = float(row['institution_participation_score'])
        pct_trend_comp = _comp_from_trend(row['holder_pct_trend'])
        holder_trend_comp = _comp_from_trend(row['holder_trend'])
        trend4_comp = _comp_from_pp(row['holder_pct_4q_change_pp'])
        migration_comp = 50.0 + 50.0 * float(row['chip_migration_score'])
        score = (0.25 * part + 0.25 * pct_trend_comp + 0.20 * holder_trend_comp
                 + 0.15 * trend4_comp + 0.15 * migration_comp)
        score = _clip(score)
        if score >= 81:
            regime = '极强'
        elif score >= 61:
            regime = '强'
        elif score >= 41:
            regime = '中性'
        elif score >= 21:
            regime = '弱'
        else:
            regime = '极弱'
        chip_scores.append(score)
        regimes.append(regime)
    df['chip_structure_score'] = chip_scores
    df['chip_regime'] = regimes

    # ---- 数据质量与公司行为提示 ----
    quality_flags = []
    action_flags = []
    for _, row in df.iterrows():
        quality = 1 if (pd.notna(row['institution_quantity']) and pd.notna(row['holder_quantity'])
                        and pd.notna(row['holder_pct'])) else 0
        qoq_pct = row['holder_quantity_qoq_pct']
        action = 1 if qoq_pct is not None and pd.notna(qoq_pct) and abs(float(qoq_pct)) >= 25.0 else 0
        quality_flags.append(quality)
        action_flags.append(action)
    df['data_quality_flag'] = quality_flags
    df['corporate_action_flag'] = action_flags

    return df


def create_analysis_table_if_not_exists(conn: sqlite3.Connection) -> None:
    """确保 hk_quarterly_institutional_holdings_analysis 表存在"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hk_quarterly_institutional_holdings_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            quarter TEXT NOT NULL,
            quarter_end_date TEXT,
            institution_quantity INTEGER,
            holder_quantity INTEGER,
            holder_pct REAL,
            quarter_end_price REAL,
            institution_quantity_qoq INTEGER,
            institution_quantity_qoq_pct REAL,
            holder_quantity_qoq INTEGER,
            holder_quantity_qoq_pct REAL,
            holder_pct_qoq_pp REAL,
            institution_quantity_yoy_pct REAL,
            holder_quantity_yoy_pct REAL,
            holder_pct_yoy_pp REAL,
            institution_quantity_4q_change INTEGER,
            holder_quantity_4q_change INTEGER,
            holder_pct_4q_change_pp REAL,
            institution_trend INTEGER,
            holder_trend INTEGER,
            holder_pct_trend INTEGER,
            chip_migration_score REAL,
            chip_migration_status TEXT,
            institution_participation_score REAL,
            institutional_concentration_score REAL,
            chip_structure_score REAL,
            chip_regime TEXT,
            data_quality_flag INTEGER,
            corporate_action_flag INTEGER,
            source_period TEXT,
            data_source TEXT,
            update_time TEXT,
            UNIQUE(stock_code, quarter)
        )
    """)
    conn.commit()


def save_analysis_to_db(conn: sqlite3.Connection, df: pd.DataFrame, stock_code: str,
                        stock_name: str, logger: logging.Logger) -> int:
    """保存单只股票的分析结果（先删除旧记录再全量插入）"""
    if df is None or df.empty:
        return 0

    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM hk_quarterly_institutional_holdings_analysis WHERE stock_code = ?",
        (stock_code,)
    )

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    columns = [
        'stock_code', 'stock_name', 'quarter', 'quarter_end_date',
        'institution_quantity', 'holder_quantity', 'holder_pct', 'quarter_end_price',
        'institution_quantity_qoq', 'institution_quantity_qoq_pct',
        'holder_quantity_qoq', 'holder_quantity_qoq_pct', 'holder_pct_qoq_pp',
        'institution_quantity_yoy_pct', 'holder_quantity_yoy_pct', 'holder_pct_yoy_pp',
        'institution_quantity_4q_change', 'holder_quantity_4q_change',
        'holder_pct_4q_change_pp',
        'institution_trend', 'holder_trend', 'holder_pct_trend',
        'chip_migration_score', 'chip_migration_status',
        'institution_participation_score', 'institutional_concentration_score',
        'chip_structure_score', 'chip_regime',
        'data_quality_flag', 'corporate_action_flag',
        'source_period', 'data_source', 'update_time',
    ]

    records = []
    for _, row in df.iterrows():
        def _val(key):
            v = row.get(key)
            return None if v is None or pd.isna(v) else v
        records.append((
            stock_code, stock_name, row['quarter'], _val('quarter_end_date'),
            _val('institution_quantity'), _val('holder_quantity'), _val('holder_pct'),
            _val('quarter_end_price'),
            _val('institution_quantity_qoq'), _val('institution_quantity_qoq_pct'),
            _val('holder_quantity_qoq'), _val('holder_quantity_qoq_pct'),
            _val('holder_pct_qoq_pp'),
            _val('institution_quantity_yoy_pct'), _val('holder_quantity_yoy_pct'),
            _val('holder_pct_yoy_pp'),
            _val('institution_quantity_4q_change'), _val('holder_quantity_4q_change'),
            _val('holder_pct_4q_change_pp'),
            _val('institution_trend'), _val('holder_trend'), _val('holder_pct_trend'),
            _val('chip_migration_score'), _val('chip_migration_status'),
            _val('institution_participation_score'),
            _val('institutional_concentration_score'),
            _val('chip_structure_score'), _val('chip_regime'),
            _val('data_quality_flag'), _val('corporate_action_flag'),
            _val('source_period'), _val('data_source'), now_str,
        ))

    if not records:
        conn.commit()
        return 0

    placeholders = ', '.join(['?'] * len(columns))
    columns_str = ', '.join(columns)
    sql = f"INSERT INTO hk_quarterly_institutional_holdings_analysis ({columns_str}) VALUES ({placeholders})"
    cursor.executemany(sql, records)
    conn.commit()
    logger.info(f"{stock_code} ({stock_name}) 已保存 {len(records)} 条筹码分析记录")
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
        logger.info("Quarterly_TA4C_Analyze_institutional_holdings 启动")
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
            if not check_table_exists(conn, 'hk_hist_institutional_holdings'):
                logger.error("原始数据表 hk_hist_institutional_holdings 不存在，程序终止")
                return

            create_analysis_table_if_not_exists(conn)

            # 读取全部原始季度持股数据
            df_raw = pd.read_sql_query(
                """
                SELECT stock_code, stock_name, period_text, institution_quantity,
                       holder_quantity, holder_pct, quarter_end_price, data_source
                FROM hk_hist_institutional_holdings
                ORDER BY stock_code, period_text
                """,
                conn
            )
            logger.info(f"读取原始机构持股数据: {len(df_raw)} 行")

            if df_raw.empty:
                logger.warning("⚠️ hk_hist_institutional_holdings 无数据（当前无机构持股数据），"
                               "待数据入库后重新运行本脚本即可")
                return

            # 解析季度并标准化股票代码
            parsed = df_raw['period_text'].apply(parse_quarter)
            df_raw['quarter'] = [f"{y}/Q{q}" if y else None for y, q in parsed]
            df_raw['quarter_end_date'] = [
                quarter_end_date(y, q) if y else None for y, q in parsed
            ]
            df_raw['stock_code'] = df_raw['stock_code'].astype(str).str.zfill(5)
            df_raw = df_raw.dropna(subset=['quarter']).copy()
            logger.info(f"有效季度记录: {len(df_raw)} 行")

            total_saved = 0
            processed_stocks = 0
            for stock_code, group in df_raw.groupby('stock_code', sort=True):
                stock_name = group['stock_name'].dropna().iloc[0] if group['stock_name'].notna().any() else stock_code
                logger.info(f"\n处理股票: {stock_code} ({stock_name})，{len(group)} 条记录")
                analyzed = compute_holdings_analysis(group)
                saved = save_analysis_to_db(conn, analyzed, stock_code, stock_name, logger)
                total_saved += saved
                processed_stocks += 1

            # 最终统计
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM hk_quarterly_institutional_holdings_analysis")
            final_count = cursor.fetchone()[0]
            logger.info("=" * 70)
            logger.info(f"✅ 机构持股分析完成：处理 {processed_stocks} 只股票，"
                        f"保存 {total_saved} 条记录，表内总计 {final_count} 条")
            logger.info("=" * 70)
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
