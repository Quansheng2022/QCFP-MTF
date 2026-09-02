# coding: utf-8
"""C 因子（季度真实筹码）

输入：hk_quarterly_institutional_holdings_analysis
输出：inst_ownership_pct_chg / holder_quantity_chg_pct / inst_participation_chg
      + c_state（C↑/C→/C↓，公司行为季度屏蔽为 None）+ c_confidence
"""

import pandas as pd


def _direction(value, threshold: float):
    if pd.isna(value):
        return None
    if value > threshold:
        return "C↑"
    if value < -threshold:
        return "C↓"
    return "C→"


def _aux_confidence(main, aux1, aux2):
    """辅助字段与主字段方向一致的个数（0~2）"""
    if pd.isna(main):
        return 0
    score = 0
    for aux in (aux1, aux2):
        if pd.isna(aux):
            continue
        if (main > 0 and aux > 0) or (main < 0 and aux < 0):
            score += 1
    return score


def build_c_factors(ih_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """从机构持股分析表计算 C 因子

    Args:
        ih_df: hk_quarterly_institutional_holdings_analysis（经 loader 标准化）
        settings: QCFP 配置 dict
    """
    thr = settings.get("structural", {}).get("direction_thresholds", {})
    c_pp_thr = float(thr.get("c_pp_threshold", 0.5))

    df = ih_df.copy()
    df["period_end"] = pd.to_datetime(df["quarter_end_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["inst_ownership_pct_chg"] = df["holder_pct_qoq_pp"]
    df["holder_quantity_chg_pct"] = df["holder_quantity_qoq_pct"]
    df["inst_participation_chg"] = df["institution_quantity_qoq_pct"]

    ca_flag = df.get("corporate_action_flag", pd.Series(0, index=df.index))
    ca_mask = ca_flag.fillna(0).astype(int) == 1

    df["c_state_raw"] = df["inst_ownership_pct_chg"].map(lambda v: _direction(v, c_pp_thr))
    df["c_state"] = df["c_state_raw"].where(~ca_mask)
    df["c_reason"] = ""
    df.loc[ca_mask, "c_reason"] = "corporate_action_flag=1 屏蔽"
    df.loc[df["c_state_raw"].isna() & ~ca_mask, "c_reason"] = "首季无QoQ或缺失"
    df["c_confidence"] = [
        _aux_confidence(m, a1, a2)
        for m, a1, a2 in zip(df["inst_ownership_pct_chg"], df["holder_quantity_chg_pct"],
                             df["inst_participation_chg"])
    ]

    cols = ["stock_code", "stock_name", "quarter", "period_end", "source_period",
            "inst_ownership_pct_chg", "holder_quantity_chg_pct", "inst_participation_chg",
            "c_state", "c_confidence", "c_reason"]
    return df[cols].reset_index(drop=True)
