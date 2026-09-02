# coding: utf-8
"""数据加载器：从现有 SQLite 表读取并标准化为 DataFrame

只读现有表，不写入；写库统一由各引擎步骤负责。
"""

import calendar as _cal
import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from ..common.db import connect
from ..common.paths import get_config_dir, get_db_path

PERIODS = ("daily", "weekly", "monthly", "quarterly")

# K 线表可能含有的指标列（按表实际存在性读取）
INDICATOR_COLS = ["ema5", "ema10", "ema20", "ema50", "ema100", "ema200",
                  "macd_dif", "macd_signal", "macd_histogram"]

KLINE_TABLE = {p: f"hk_hist_{p}_kline" for p in PERIODS}
MONEYFLOW_TABLE = {p: f"hk_hist_{p}_moneyflow" for p in PERIODS}
ANALYSIS_KLINE_TABLE = {p: f"hk_{p}_kline_analysis" for p in PERIODS}
ANALYSIS_MONEYFLOW_TABLE = {p: f"hk_{p}_moneyflow_analysis" for p in PERIODS}
DERIVED_TABLE = {
    "quarterly_institutional_holdings_analysis": "hk_quarterly_institutional_holdings_analysis",
    "quarterly_chip_analysis": "hk_quarterly_chip_analysis",
}

# 覆盖度审计使用的全部数据表（逻辑名 -> 表名）
SOURCE_TABLE = {
    **{f"{p}_kline": KLINE_TABLE[p] for p in PERIODS},
    **{f"{p}_moneyflow": MONEYFLOW_TABLE[p] for p in PERIODS},
    "idx_hist": "hk_idx_hist",
    "institutional_holdings": "hk_hist_institutional_holdings",
}


def _normalize_stock_code(code) -> Optional[str]:
    """统一为 5 位数字字符串（如 00700）"""
    if code is None:
        return None
    s = str(code).strip()
    if s.isdigit():
        return s.zfill(5)
    return s


def _to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _order_clause(columns: List[str]) -> str:
    if columns and "stock_code" in columns and "date" in columns:
        return " ORDER BY stock_code, date"
    if columns and "date" in columns:
        return " ORDER BY date"
    return ""


def read_table(table: str,
               columns: Optional[List[str]] = None,
               where: str = None,
               params: Iterable = (),
               db_path=None) -> pd.DataFrame:
    """读取任意表（可选列、可选过滤），按稳定顺序返回"""
    cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
    sql = f"SELECT {cols} FROM {table}"
    if where:
        sql += f" WHERE {where}"
    sql += _order_clause(columns)
    conn = connect(db_path)
    try:
        df = pd.read_sql_query(sql, conn, params=tuple(params))
    finally:
        conn.close()
    return df


def _table_columns(table: str, db_path=None) -> List[str]:
    conn = connect(db_path)
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return [r["name"] for r in cur.fetchall()]
    finally:
        conn.close()


def load_stock_list() -> pd.DataFrame:
    """股票列表：优先 Config/stock_list.json，其次数据库实际股票"""
    path = get_config_dir() / "stock_list.json"
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows = raw.get("stocks", raw) if isinstance(raw, dict) else raw
            df = pd.DataFrame(rows)
        except (json.JSONDecodeError, ValueError):
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    required = ["stock_code", "stock_name", "sector", "market"]
    for col in required:
        if col not in df.columns:
            df[col] = None
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].map(_normalize_stock_code)
        df = df[df["stock_code"].notna()].reset_index(drop=True)
    else:
        # 兜底：从日线表取实际股票
        df = get_available_stocks("daily")
    return df


def load_kline(period: str,
               stocks: Optional[Iterable[str]] = None,
               start: str = None,
               end: str = None,
               db_path=None) -> pd.DataFrame:
    """加载 {period}_kline，输出标准化列"""
    if period not in PERIODS:
        raise ValueError(f"未知周期: {period}，可选 {PERIODS}")
    cols = ["stock_code", "stock_name", "date", "open", "high", "low", "close",
            "volume", "amount", "turnover_rate", "amplitude", "change_percent"]
    if period == "daily":
        cols += ["change_amount", "previous_close"]
    # 按表实际存在性附加指标列（周/月/季 K 线含 ema/macd，日线不含）
    available = set(_table_columns(KLINE_TABLE[period], db_path))
    cols = [c for c in cols if c in available]
    cols += [c for c in INDICATOR_COLS if c in available]
    df = read_table(KLINE_TABLE[period], columns=cols, db_path=db_path)
    df["stock_code"] = df["stock_code"].map(_normalize_stock_code)
    df["date"] = _to_datetime(df["date"])
    if stocks:
        wanted = {_normalize_stock_code(s) for s in stocks}
        df = df[df["stock_code"].isin(wanted)]
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["date"] <= pd.Timestamp(end)]
    return df.reset_index(drop=True)


def load_moneyflow(period: str,
                   stocks: Optional[Iterable[str]] = None,
                   start: str = None,
                   end: str = None,
                   db_path=None) -> pd.DataFrame:
    """加载 {period}_moneyflow"""
    if period not in PERIODS:
        raise ValueError(f"未知周期: {period}，可选 {PERIODS}")
    cols = ["stock_code", "stock_name", "date", "price_chgpct", "capital_trend",
            "extra_large", "large", "medium", "small"]
    if period == "daily":
        cols += ["capital_in_super", "capital_in_big", "capital_in_mid", "capital_in_small",
                 "capital_out_super", "capital_out_big", "capital_out_mid", "capital_out_small"]
    df = read_table(MONEYFLOW_TABLE[period], columns=cols, db_path=db_path)
    df["stock_code"] = df["stock_code"].map(_normalize_stock_code)
    df["date"] = _to_datetime(df["date"])
    if stocks:
        wanted = {_normalize_stock_code(s) for s in stocks}
        df = df[df["stock_code"].isin(wanted)]
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["date"] <= pd.Timestamp(end)]
    return df.reset_index(drop=True)


def load_idx_hist(db_path=None) -> pd.DataFrame:
    """大盘指数日线（hk_idx_hist）"""
    df = read_table("hk_idx_hist", db_path=db_path)
    if "date" in df.columns:
        df["date"] = _to_datetime(df["date"])
    return df


def parse_quarter_period(period_text: str):
    """解析 '2026/Q2' -> (year, quarter)"""
    m = re.match(r"(\d{4})\s*[/-]?\s*[Qq](\d)", str(period_text).strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def quarter_end_date(period_text: str) -> Optional[str]:
    """'2026/Q2' -> '2026-06-30'（自然季末日）"""
    parsed = parse_quarter_period(period_text)
    if not parsed:
        return None
    year, q = parsed
    end_month = q * 3
    return f"{year:04d}-{end_month:02d}-{_cal.monthrange(year, end_month)[1]:02d}"


def load_institutional_holdings(stocks: Optional[Iterable[str]] = None,
                                db_path=None) -> pd.DataFrame:
    """机构持股原始表（季度频），补充 quarter_end_date / quarter 字段"""
    cols = ["stock_code", "stock_name", "period_text", "institution_quantity",
            "holder_quantity", "holder_pct", "quarter_end_price", "update_time", "data_source"]
    df = read_table("hk_hist_institutional_holdings", columns=cols, db_path=db_path)
    df["stock_code"] = df["stock_code"].map(_normalize_stock_code)
    df["quarter"] = df["period_text"].map(parse_quarter_period)
    df["quarter_end_date"] = _to_datetime(df["period_text"].map(quarter_end_date))
    if stocks:
        wanted = {_normalize_stock_code(s) for s in stocks}
        df = df[df["stock_code"].isin(wanted)]
    return df.reset_index(drop=True)


def load_derived(name: str, db_path=None) -> pd.DataFrame:
    """加载已有分析表（季度筹码相关）"""
    if name not in DERIVED_TABLE:
        raise ValueError(f"未知派生表: {name}，可选 {list(DERIVED_TABLE)}")
    df = read_table(DERIVED_TABLE[name], db_path=db_path)
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].map(_normalize_stock_code)
    return df


def load_analysis(period: str, kind: str = "kline", db_path=None) -> pd.DataFrame:
    """加载 hk_{period}_{kind}_analysis"""
    if period not in PERIODS:
        raise ValueError(f"未知周期: {period}")
    if kind == "kline":
        table = ANALYSIS_KLINE_TABLE[period]
    elif kind == "moneyflow":
        table = ANALYSIS_MONEYFLOW_TABLE[period]
    else:
        raise ValueError(f"未知分析类型: {kind}")
    df = read_table(table, db_path=db_path)
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].map(_normalize_stock_code)
    if "date" in df.columns:
        df["date"] = _to_datetime(df["date"])
    return df


def load_catalog(db_path=None) -> Dict[str, pd.DataFrame]:
    """加载全部源数据表（供覆盖度审计 / 数据质量使用）"""
    catalog = {}
    for period in PERIODS:
        catalog[f"{period}_kline"] = load_kline(period, db_path=db_path)
        catalog[f"{period}_moneyflow"] = load_moneyflow(period, db_path=db_path)
    catalog["idx_hist"] = load_idx_hist(db_path=db_path)
    catalog["institutional_holdings"] = load_institutional_holdings(db_path=db_path)
    return catalog


def get_available_stocks(period: str = "daily", db_path=None) -> pd.DataFrame:
    """该周期有数据的股票列表（stock_code/stock_name）"""
    df = load_kline(period, db_path=db_path)
    if df.empty:
        return pd.DataFrame(columns=["stock_code", "stock_name"])
    sub = df[["stock_code", "stock_name"]].drop_duplicates("stock_code")
    return sub.reset_index(drop=True)


def get_table_date_range(table: str, db_path=None) -> tuple:
    """返回 (min_date, max_date)，无 date 列返回 (None, None)"""
    conn = connect(db_path)
    try:
        cur = conn.execute("PRAGMA table_info(" + table + ")")
        cols = [r["name"] for r in cur.fetchall()]
        if "date" not in cols:
            return None, None
        row = conn.execute(f"SELECT MIN(date), MAX(date) FROM {table}").fetchone()
        return row[0], row[1]
    finally:
        conn.close()
