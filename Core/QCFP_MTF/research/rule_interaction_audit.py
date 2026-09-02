# coding: utf-8
"""Rule Interaction Audit（QCFP-MTF 2.8：64 号规则交互审计）

找出互相重复或互相抵消的规则：比较
    Rule A only / Rule B only / A+B / neither
的 OOS 差异，把规则分类为：
    COMPLEMENTARY / REDUNDANT / CONFLICTING / DOMINATED

验收标准：若两条规则长期产生几乎相同的拦截结果、
第二条无独立增量价值 → 优先删除其中一条。
"""


def _value(m: dict) -> float:
    sharpe = float((m or {}).get("sharpe") or 0.0)
    mdd = abs(float((m or {}).get("mdd") or 0.0))
    return sharpe - mdd * 0.2


def rule_interaction_audit(results: dict,
                           min_delta: float = 0.02) -> dict:
    """results：{"NEITHER", "A_ONLY", "B_ONLY", "A_AND_B"} 指标。"""
    a = _value(results.get("A_ONLY"))
    b = _value(results.get("B_ONLY"))
    ab = _value(results.get("A_AND_B"))
    n = _value(results.get("NEITHER"))
    best_single = max(a, b)
    if ab >= best_single + min_delta:
        relation = "COMPLEMENTARY"
        reason = "A+B 显著优于任一单独规则"
    elif abs(ab - best_single) <= min_delta:
        if best_single > n + min_delta:
            relation = "REDUNDANT"
            reason = "合并结果 ≈ 单独最好规则，另一条无独立增量"
        else:
            relation = "NEITHER_NECESSARY"
            reason = "两条规则单独与合并都无明显增量"
    elif ab < min(a, b) - min_delta:
        relation = "CONFLICTING"
        reason = "A+B 明显差于任一单独规则（互相抵消）"
    elif a >= b + min_delta:
        relation = "DOMINATED"
        reason = "A 全面优于 B，B 被支配"
    elif b >= a + min_delta:
        relation = "DOMINATED"
        reason = "B 全面优于 A，A 被支配"
    else:
        relation = "AMBIGUOUS"
        reason = "差异不显著，需要更多证据"
    return {"relation": relation, "reason": reason,
            "values": {"NEITHER": round(n, 4), "A_ONLY": round(a, 4),
                       "B_ONLY": round(b, 4), "A_AND_B": round(ab, 4)}}


def interception_overlap(rule_a_interceptions, rule_b_interceptions) -> dict:
    """两条规则在历史决策中拦截（拒绝）行为的重叠度。"""
    a = set(rule_a_interceptions or [])
    b = set(rule_b_interceptions or [])
    union = a | b
    overlap = round(len(a & b) / len(union), 4) if union else None
    return {"overlap_ratio": overlap,
            "redundancy_candidate": bool(
                overlap is not None and overlap > 0.9),
            "rule": "拦截高度重叠且无独立增量 → 删除其中一条"}


def rule_action_candidates(audit_results: dict) -> dict:
    """新 64 号：Rule Interaction Audit 的最终产物不是漂亮矩阵，
    而是 KEEP / MERGE / DROP 候选。"""
    relation = audit_results.get("relation")
    if relation == "COMPLEMENTARY":
        action, reason = "KEEP", "A+B 有稳定增量"
    elif relation == "REDUNDANT":
        action, reason = "MERGE", "合并 ≈ 单独最好，另一条无独立增量"
    elif relation == "DOMINATED":
        action, reason = "DROP", "被支配规则无独立价值"
    elif relation == "CONFLICTING":
        action, reason = "RESOLVE_AUTHORITY", "明确 Authority 或删除其一"
    elif relation == "NEITHER_NECESSARY":
        action, reason = "DROP_BOTH", "两条规则都无明显增量"
    else:
        action, reason = "REVIEW", "证据不足"
    return {"relation": relation, "action": action, "reason": reason,
            "values": audit_results.get("values")}
