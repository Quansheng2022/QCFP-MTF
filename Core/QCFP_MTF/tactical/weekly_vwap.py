# coding: utf-8
"""周 VWAP 偏离：close / VWAP_W - 1"""

import numpy as np
import pandas as pd


def build_vwap_factors(w_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    df = w_df[["stock_code", "date", "close", "amount", "volume"]].copy()
    df["week_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    vwap = df["amount"] / df["volume"].where(df["volume"] > 0)
    vwap = vwap.where(vwap > 0)
    df["w_vwap"] = vwap
    df["w_vwap_deviation"] = (df["close"] / df["w_vwap"] - 1.0).where(df["w_vwap"].notna())
    return df[["stock_code", "week_end", "w_vwap_deviation"]].reset_index(drop=True)
