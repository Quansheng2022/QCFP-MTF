# coding: utf-8
"""Decision Impact Changelog（QCFP-MTF 2.8：46 号决策影响变更日志）

每次 Release 必须回答"这次修改会让历史决策发生什么变化"：
    % 历史决策受影响 + 主要变化（HOLD→EXIT / ADD→HOLD / No change）
"""


def decision_changelog(old_version, new_version, changes: list,
                       decision_diffs: dict) -> dict:
    """changes：[(description, affected_decision_count)]；
    decision_diffs：{transition: count}（如 HOLD→EXIT）"""
    total = sum(c[1] for c in changes)
    transitions = dict(decision_diffs or {})
    no_change = total - sum(transitions.values())
    return {
        "old_version": old_version,
        "new_version": new_version,
        "changes": [{"description": d, "affected": n}
                    for d, n in changes],
        "total_affected": total,
        "transition_breakdown": transitions,
        "no_change_ratio": round(max(0, no_change) / max(1, total), 4)
        if total else 1.0,
        "requires_decision_diff_report": bool(changes),
    }
