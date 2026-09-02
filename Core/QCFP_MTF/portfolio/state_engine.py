# coding: utf-8
"""Portfolio State Engine（QCFP-MTF 2.7：从单股票正确 → 组合正确）

输入：总暴露 / 现金比 / 行业集中 / 相关性 / Permission 分布 / Wave 分布 /
      组合 MFE-MAE / 市场波动
输出：NORMAL / DEFENSIVE / RISK_OFF / CONCENTRATED / OVERHEATED / RECOVERY
状态反向限制新增交易（如 RISK_OFF 禁 ADD、降 Entry Cap、优先 REDUCE）。
"""


def portfolio_state(metrics: dict) -> str:
    """由组合指标判定状态"""
    exposure = float(metrics.get("total_exposure", 0.0))
    cash = float(metrics.get("cash_ratio", 0.0))
    conc = float(metrics.get("sector_concentration", 0.0))
    corr = float(metrics.get("correlation", 0.3))
    risk_share = float(metrics.get("permission_risk_share", 0.0))
    bullish_share = float(metrics.get("wave_bullish_share", 0.0))
    vol = float(metrics.get("market_vol", 0.2))
    mdd_recent = abs(float(metrics.get("mdd_recent", 0.0)))
    # RISK_OFF：高比例 BLOCK/WATCH 权限
    if risk_share >= 0.6:
        return "RISK_OFF"
    # CONCENTRATED：行业集中度高 或 相关性高
    if conc >= 0.5 or corr >= 0.7:
        return "CONCENTRATED"
    # OVERHEATED：高暴露 + 高波动 + 低现金
    if exposure >= 0.8 and vol >= 0.3 and cash <= 0.1:
        return "OVERHEATED"
    # DEFENSIVE：近期回撤大或波动高
    if mdd_recent >= 0.10 or vol >= 0.35:
        return "DEFENSIVE"
    # RECOVERY：高现金 + 看多波比例回升
    if cash >= 0.4 and bullish_share >= 0.4:
        return "RECOVERY"
    return "NORMAL"


def state_constraints(state: str) -> dict:
    """状态反向约束：add_allowed / entry_cap_scale / require_confirmation / prioritize_reduce"""
    base = {"add_allowed": True, "entry_cap_scale": 1.0,
            "require_confirmation": False, "prioritize_reduce": False}
    if state == "RISK_OFF":
        return {**base, "add_allowed": False, "entry_cap_scale": 0.5,
                "require_confirmation": True, "prioritize_reduce": True}
    if state == "CONCENTRATED":
        return {**base, "entry_cap_scale": 0.7, "prioritize_reduce": True}
    if state == "OVERHEATED":
        return {**base, "add_allowed": False, "entry_cap_scale": 0.5,
                "require_confirmation": True}
    if state == "DEFENSIVE":
        return {**base, "entry_cap_scale": 0.7, "require_confirmation": True}
    if state == "RECOVERY":
        return {**base, "entry_cap_scale": 1.0}
    return base


def apply_state_to_new_entries(signals, state, entry_cap_scale=None,
                               add_allowed=None):
    """对新建仓（previous 为 0 的行）应用组合状态约束"""
    import pandas as pd
    out = signals.copy()
    c = state_constraints(state)
    scale = float(entry_cap_scale if entry_cap_scale is not None
                  else c["entry_cap_scale"])
    allowed = bool(add_allowed if add_allowed is not None
                   else c["add_allowed"])
    if "target" not in out.columns:
        return out
    prev = out.groupby("stock_code")["target"].shift(1).fillna(0.0)
    new_entry = (prev <= 0) & (out["target"] > 0)
    if not allowed:
        out.loc[new_entry, "target"] = 0.0
    else:
        out.loc[new_entry, "target"] = out.loc[new_entry, "target"] * scale
    return out
