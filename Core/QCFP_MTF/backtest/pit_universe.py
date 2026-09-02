# coding: utf-8
"""Point-in-Time Historical Universe

可选的 `Config/qcfp_universe.csv`（stock_code, valid_from, valid_to）定义
每个历史时点可投资的股票池，缓解 Survivorship Bias。
文件不存在时退化为"信号表中全部股票"。
"""

import pandas as pd

from ..common.paths import get_config_dir


def load_universe(path=None) -> pd.DataFrame:
    if path is None:
        path = get_config_dir() / "qcfp_universe.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"stock_code": str})
    df["stock_code"] = df["stock_code"].str.strip().str.zfill(5)
    return df


def filter_by_universe(signals: pd.DataFrame, universe: pd.DataFrame,
                       date_col: str = "decision_date",
                       strict: bool = False) -> pd.DataFrame:
    """按 PIT 股票池过滤信号：仅保留 valid_from <= 决策日 <= valid_to 的股票

    strict=True（research_validation / production）：
    记录不完整（valid_from/valid_to 缺失）或不在 Universe 内的股票一律剔除，
    不再退化为 valid forever（PIT_INVALID）。
    """
    if universe is None or universe.empty:
        return signals
    s = signals.copy()
    u = universe.copy()
    s["_dt"] = pd.to_datetime(s[date_col], errors="coerce")
    u["valid_from"] = pd.to_datetime(u["valid_from"], errors="coerce")
    u["valid_to"] = pd.to_datetime(u["valid_to"], errors="coerce")
    merged = s.merge(u[["stock_code", "valid_from", "valid_to"]],
                     on="stock_code", how="left")
    if strict:
        merged = merged.dropna(subset=["valid_from", "valid_to"])
        ok = merged["_dt"].between(merged["valid_from"], merged["valid_to"])
    else:
        lo = merged["valid_from"].fillna(pd.Timestamp.min)
        hi = merged["valid_to"].fillna(pd.Timestamp.max)
        ok = merged["_dt"].between(lo, hi)
    return merged[ok].drop(columns=["_dt", "valid_from", "valid_to"]).reset_index(drop=True)


def validate_universe(universe: pd.DataFrame) -> int:
    """检查 PIT Universe 的 (stock_code, valid_from, valid_to) 区间是否存在重叠。

    返回重叠区间对数；>0 时应判 FAIL（many-to-many 会让 filter_by_universe 重复股票）。
    """
    if universe is None or universe.empty:
        return 0
    u = universe.copy()
    u["valid_from"] = pd.to_datetime(u["valid_from"], errors="coerce")
    u["valid_to"] = pd.to_datetime(u["valid_to"], errors="coerce")
    overlaps = 0
    for code, g in u.groupby("stock_code"):
        g = g.sort_values("valid_from").reset_index(drop=True)
        for i in range(1, len(g)):
            prev_to = g.loc[i - 1, "valid_to"]
            cur_from = g.loc[i, "valid_from"]
            if pd.notna(prev_to) and pd.notna(cur_from) and cur_from < prev_to:
                overlaps += 1
    return int(overlaps)


def filter_price_universe(weekly_df: pd.DataFrame, universe: pd.DataFrame,
                          date_col: str = "date",
                          strict: bool = False) -> pd.DataFrame:
    """按 PIT Universe 过滤价格面板（用于 Buy&Hold / Momentum 等基准，确保与策略同口径）"""
    if universe is None or universe.empty:
        return weekly_df
    w = weekly_df.copy()
    u = universe.copy()
    w["_dt"] = pd.to_datetime(w[date_col], errors="coerce")
    u["valid_from"] = pd.to_datetime(u["valid_from"], errors="coerce")
    u["valid_to"] = pd.to_datetime(u["valid_to"], errors="coerce")
    merged = w.merge(u[["stock_code", "valid_from", "valid_to"]],
                     on="stock_code", how="left")
    if strict:
        merged = merged.dropna(subset=["valid_from", "valid_to"])
        ok = merged["_dt"].between(merged["valid_from"], merged["valid_to"])
    else:
        lo = merged["valid_from"].fillna(pd.Timestamp.min)
        hi = merged["valid_to"].fillna(pd.Timestamp.max)
        ok = merged["_dt"].between(lo, hi)
    return merged[ok].drop(
        columns=["_dt", "valid_from", "valid_to"]).reset_index(drop=True)


def universe_incomplete(universe: pd.DataFrame) -> list:
    """返回 valid_from/valid_to 缺失（记录不完整）的股票代码列表

    2.3：正式 Research Validation 中，记录不完整 = PIT_INVALID，
    禁止进入正式回测，而不是自动 valid forever。
    """
    if universe is None or universe.empty:
        return []
    u = universe.copy()
    u["valid_from"] = pd.to_datetime(u["valid_from"], errors="coerce")
    u["valid_to"] = pd.to_datetime(u["valid_to"], errors="coerce")
    bad = u[u["valid_from"].isna() | u["valid_to"].isna()]
    return sorted(str(c) for c in bad["stock_code"].unique())
