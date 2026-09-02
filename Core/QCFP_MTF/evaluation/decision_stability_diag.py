# coding: utf-8
"""Decision Stability Diagnostics（QCFP-MTF 2.8：25 号诊断只读）

先证明"系统存在决策抖动"，再决定是否治理（不先发明平滑算法）：
    DecisionFlipRate / TargetTurnover / StatePersistence /
    MedianHoldingPeriod / UnnecessaryReversalRate

Research Metric，不直接进入 Canonical。
"""


def decision_stability_diag(decisions) -> dict:
    """decisions：按时间排序的 [{action, target_position, fsm_state,
    holding_days}]"""
    n = len(decisions)
    if n < 2:
        return {"n": n}
    flips = 0
    target_turnover = 0.0
    state_changes = 0
    unnecessary_reversals = 0
    holding_days = []
    for i in range(1, n):
        prev, cur = decisions[i - 1], decisions[i]
        if prev.get("action") != cur.get("action"):
            flips += 1
        if cur.get("fsm_state") != prev.get("fsm_state"):
            state_changes += 1
        pt = float(prev.get("target_position") or 0.0)
        ct = float(cur.get("target_position") or 0.0)
        target_turnover += abs(ct - pt)
        # 无实质状态变化但 action 反转 → unnecessary reversal
        if prev.get("fsm_state") == cur.get("fsm_state") \
                and prev.get("action") != cur.get("action") \
                and abs(ct - pt) <= 0.011:
            unnecessary_reversals += 1
        if cur.get("holding_days") is not None:
            holding_days.append(int(cur["holding_days"]))
    holding_days.sort()
    median_holding = holding_days[len(holding_days) // 2] \
        if holding_days else None
    return {
        "n": n,
        "decision_flip_rate": round(flips / (n - 1), 4),
        "target_turnover": round(target_turnover, 4),
        "state_persistence": round(1 - state_changes / (n - 1), 4),
        "median_holding_period": median_holding,
        "unnecessary_reversal_rate": round(
            unnecessary_reversals / (n - 1), 4),
        # 抖动 = 无意义反转（同状态反向）或极端高频翻转+低状态持续性；
        # 正常生命周期翻转（BUY→HOLD→REDUCE）不算抖动
        "flapping_suspect": (unnecessary_reversals / (n - 1)) > 0.2
        or ((flips / (n - 1)) > 0.75
            and (1 - state_changes / (n - 1)) > 0.75)   # 同状态高频反转
        or ((flips / (n - 1)) > 0.75
            and (1 - state_changes / (n - 1)) < 0.25),  # 混沌翻转
        "diagnostic_only": True,   # Research Metric，不直接进 Canonical
    }
