# coding: utf-8
"""As-of 数据对齐工具（生产与回测共用同一时间可用性规则）

核心规则：任何输入数据只能使用 effective_date <= 决策日 且
available_date <= 决策日 的记录（available_date 默认 = effective_date，
有披露滞后的数据（机构持股/筹码）需显式传入 available_date）。
"""

from pathlib import Path

import pandas as pd

from .paths import get_config_dir


def add_disclosure_lag(df: pd.DataFrame, date_col: str, lag_days: int,
                       out_col: str = "available_date_dt") -> pd.DataFrame:
    """为 period_end 类字段补推算披露日期（period_end + lag_days）"""
    out = df.copy()
    dt = pd.to_datetime(out[date_col], errors="coerce")
    out[out_col] = dt + pd.Timedelta(days=int(lag_days))
    return out


def asof_join_latest(left: pd.DataFrame, right: pd.DataFrame,
                     left_time: str, right_time: str,
                     by: str = "stock_code",
                     right_cols=None, suffixes=("", "_r")) -> pd.DataFrame:
    """按时间键做 as-of 对齐（direction=backward），左右表需按时间键全局有序。

    Args:
        left: 决策网格（每行一个决策点）
        right: 待对齐的历史数据（需含 by 与 right_time 列）
        left_time: 左表时间列（决策日）
        right_time: 右表时间列（可用日期，如 available_date_dt）
        by: 分组键
        right_cols: 右表需要保留的列（不含 by / right_time 之外的自动合并）
    """
    cols = [by, right_time] + (right_cols or [])
    cols = [c for c in dict.fromkeys(cols) if c in right.columns]
    r = right[cols].copy()
    r = r.sort_values(right_time)
    left = left.sort_values(left_time)
    return pd.merge_asof(
        left, r, left_on=left_time, right_on=right_time,
        by=by, direction="backward", suffixes=suffixes)


def decision_time(col: str = "week_end") -> str:
    """决策时间列标准名"""
    return col


def load_disclosure_overrides(path=None) -> dict:
    """加载真实披露日覆盖表（Config/qcfp_disclosure_dates.csv）

    CSV 列：stock_code, period_end, available_date
    存在时优先使用真实披露日，否则用 period_end + 固定滞后。
    """
    if path is None:
        path = get_config_dir() / "qcfp_disclosure_dates.csv"
    path = Path(path)
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype={"stock_code": str})
    out = {}
    for _, r in df.iterrows():
        code = str(r["stock_code"]).strip().zfill(5)
        out[(code, str(r["period_end"]).strip())] = str(r["available_date"]).strip()
    return out


def apply_disclosure_overrides(df: pd.DataFrame, overrides: dict,
                               period_col: str = "period_end",
                               avail_col: str = "available_date_dt") -> pd.DataFrame:
    """用真实披露日覆盖推算日期（仅覆盖表中匹配的 (stock, period_end)）"""
    if not overrides:
        return df
    out = df.copy()
    keys = set(overrides)
    for (code, period), avail in overrides.items():
        if (code, period) not in keys:
            continue
        mask = (out["stock_code"] == code) & (out[period_col] == period)
        if mask.any():
            out.loc[mask, avail_col] = pd.to_datetime(avail)
    return out


def pit_latest(df: pd.DataFrame, decision_date,
               period_col: str = "period_end",
               available_col: str = "available_date"):
    """PIT 规则：返回截至决策日**最近可得**的行

    只允许 available_date <= decision_date 的记录参与；
    在可得记录中按 period_end 取最新（等价于"决策日最近可获得的信息"）。
    无可得记录返回 None（调用方置为数据不足）。
    """
    d = pd.Timestamp(decision_date)
    avail = pd.to_datetime(df[available_col], errors="coerce")
    sub = df[avail <= d]
    if sub.empty:
        return None
    return sub.sort_values(period_col).iloc[-1]
