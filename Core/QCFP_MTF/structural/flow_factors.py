# coding: utf-8
"""F 因子（季度资金流）

输入：hk_quarterly_chip_analysis.institutional_flow（IDR/FBI 派生）
输出：q_inst_flow_raw / q_inst_flow_z（个股滚动 8 季）
      / q_ifa_zscore（同期横截面） + f_state（F↑/F→/F↓/F_UNKNOWN）

注意：institutional_flow 仅 2021+ 可用，更早季度输出 F_UNKNOWN（证据等级 A-）。
"""

import pandas as pd

from ..common.normalization import rolling_zscore
import numpy as np


def _cross_sectional_z(s: pd.Series) -> pd.Series:
    """同期横截面 Z-Score；样本 <5 或 std=0 时返回 0"""
    valid = s.dropna()
    if len(valid) < 5 or valid.std(ddof=0) == 0:
        return pd.Series(0.0, index=s.index)
    return (s - valid.mean()) / valid.std(ddof=0)


def build_f_factors(chip_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """从季度筹码联合分析表计算 F 因子

    Args:
        chip_df: hk_quarterly_chip_analysis（经 loader 标准化）
        settings: QCFP 配置 dict
    """
    thr = settings.get("structural", {}).get("direction_thresholds", {})
    f_z_thr = float(thr.get("f_z_threshold", 0.5))

    df = chip_df.copy()
    df["period_end"] = pd.to_datetime(df["quarter_end_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["q_inst_flow_raw"] = df["institutional_flow"]

    # 个股时间序列 Z-Score（滚动 8 季度，需至少 3 个历史季度）
    df["q_inst_flow_z"] = (
        df.groupby("stock_code")["q_inst_flow_raw"]
        .transform(lambda s: rolling_zscore(s, window=8, min_history=3))
    )
    # 同期横截面 IFA Z-Score
    df["q_ifa_zscore"] = df.groupby("quarter")["q_inst_flow_raw"].transform(_cross_sectional_z)

    def _f_state(row):
        if pd.isna(row["q_inst_flow_raw"]):
            return "F_UNKNOWN"
        if pd.isna(row["q_inst_flow_z"]):
            return "F→"
        if row["q_inst_flow_z"] > f_z_thr:
            return "F↑"
        if row["q_inst_flow_z"] < -f_z_thr:
            return "F↓"
        return "F→"

    df["f_state"] = df.apply(_f_state, axis=1)
    df["f_reason"] = np.where(df["q_inst_flow_raw"].isna(),
                              "资金流缺失（2021前）", "")

    cols = ["stock_code", "stock_name", "quarter", "period_end",
            "q_inst_flow_raw", "q_inst_flow_z", "q_ifa_zscore",
            "f_state", "f_reason"]
    return df[cols].reset_index(drop=True)
