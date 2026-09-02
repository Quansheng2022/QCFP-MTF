# coding: utf-8
"""Decision Policy Optimizer（QCFP-MTF 2.8：44 号决策策略优化器）

优化的是"状态 → 行动"映射，而不是把某个指标调到最佳：
    State（Permission+Regime+Wave+Risk+Portfolio）→ Action
    （BUY/HOLD/TRIM/EXIT/WAIT）

硬治理边界：Policy 不能修改 Permission；Governance > Risk > Policy。
"""


def optimize_policy(state_action_candidates, governance_boundaries=None) \
        -> dict:
    """策略优化。

    state_action_candidates：[{state, action, expected_value, permission,
                              risk}]
    governance_boundaries：{max_position, forbidden_actions}
    返回推荐策略 + 越权守卫。
    """
    boundaries = governance_boundaries or {"max_position": 0.10,
                                           "forbidden_actions": ()}
    forbidden = set(boundaries.get("forbidden_actions") or ())
    valid = [c for c in state_action_candidates
             if c.get("action") not in forbidden]
    ranked = sorted(valid, key=lambda c: -float(c.get("expected_value")
                                                or 0.0))
    best = ranked[0] if ranked else None
    violations = []
    for c in valid:
        if c.get("action") in ("BUY", "ADD") \
                and float(c.get("position") or 0.0) \
                > float(boundaries.get("max_position") or 1.0):
            violations.append(
                f"{c['state']}: position 超治理上限")
    return {
        "recommended": best,
        "candidates_evaluated": len(valid),
        "governance_violations": violations,
        "optimization_guarded": bool(violations),
        "note": "Policy 优化不修改 Permission；"
                "Governance > Risk > Policy",
    }
