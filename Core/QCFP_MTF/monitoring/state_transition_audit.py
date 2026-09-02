# coding: utf-8
"""State Transition Audit（QCFP-MTF 2.8：86 号状态转换审计）

审查状态转换是否合理（Permission / Wave lifecycle / FSM / Safety）：
    from_state / to_state / transition_reason /
    duration_in_previous_state / decision_impact

找出：不可能 transition / 从未使用 transition / 高频来回 transition /
没有决策意义的 transition；再决定是否简化 FSM，而不是新增状态。
"""

from collections import Counter


def state_transition_audit(transitions, allowed=None) -> dict:
    """transitions：[{"from", "to", "reason", "duration",
    "decision_impact"}]；allowed：[("from","to")]"""
    counts = Counter((str(t.get("from")), str(t.get("to")))
                     for t in transitions or [])
    impossible, never_used = [], []
    if allowed is not None:
        allowed_set = set(allowed)
        impossible = sorted([list(k) for k in counts
                             if k not in allowed_set])
        never_used = sorted([list(k) for k in allowed_set
                             if k not in counts])
    # 高频来回：A→B 与 B→A 都出现且往返总次数 ≥3
    oscillations = []
    for (a, b), n in counts.items():
        rev = counts.get((b, a), 0)
        if a < b and rev >= 1 and (n + rev) >= 3:
            oscillations.append({"pair": [a, b],
                                 "a_to_b": n, "b_to_a": rev})
    no_meaning = sum(
        1 for t in transitions or []
        if abs(float(t.get("decision_impact") or 0.0)) < 1e-9)
    issues = bool(impossible or oscillations or no_meaning) \
        or (allowed is not None and bool(never_used))
    return {
        "counts": {f"{a}->{b}": n for (a, b), n in counts.items()},
        "impossible_transitions": impossible,
        "never_used_transitions": never_used,
        "oscillations": oscillations,
        "no_decision_meaning_count": no_meaning,
        "verdict": "SIMPLIFY_FSM" if issues else "HEALTHY",
        "rule": "先审查转换，再决定简化 FSM，而不是新增状态",
    }


def state_value_audit(states, target_impact=None) -> dict:
    """新 86 号：每个 Production State 必须至少证明一种独立生命周期
    含义或决策价值。target_impact：{state: 该状态产生非零 target 的比例}"""
    target_impact = target_impact or {}
    results = {}
    for state in states or []:
        impact = float(target_impact.get(state, 0.0) or 0.0)
        results[state] = {
            "independent_decision_value": impact > 0.0,
            "target_impact_ratio": round(impact, 4),
            "verdict": "HAS_VALUE" if impact > 0.0 else "NO_INDEPENDENT_VALUE",
        }
    no_value = [s for s, r in results.items()
                if r["verdict"] == "NO_INDEPENDENT_VALUE"]
    return {"states": results,
            "no_independent_value": no_value,
            "compression_candidates": no_value,
            "rule": "进入后从不改变 FinalTarget 的状态 → 进入压缩审查"}
