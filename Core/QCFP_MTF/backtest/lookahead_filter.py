# coding: utf-8
"""防 Look-ahead 过滤器

机构持股数据滞后披露（available_date = period_end + 45 天）。
回测中季度结构只能使用 available_date <= 决策日的记录。
"""


def validate_timeline(df, decision_col="decision_date",
                      available_col="structural_available_date"):
    """返回布尔序列：True = 可用；False = Look-ahead 违规

    规则：available_date 为空（无季度结构数据，DATA_INSUFFICIENT）不算违规；
    只有"有数据但 available_date > 决策日"才是 Look-ahead。
    """
    avail = df[available_col]
    return avail.isna() | (avail <= df[decision_col])


def filter_available(df, decision_col="decision_date",
                     available_col="structural_available_date"):
    return df[validate_timeline(df, decision_col, available_col)].copy()


def assert_no_lookahead(df, decision_col="decision_date",
                        available_col="structural_available_date"):
    """违规即抛错（回测前置断言）"""
    bad = (~validate_timeline(df, decision_col, available_col)).sum()
    if bad:
        raise ValueError(f"Look-ahead 违规 {int(bad)} 行："
                         f"{available_col} > {decision_col}")
    return True
