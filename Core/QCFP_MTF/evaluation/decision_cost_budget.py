# coding: utf-8
"""Decision Cost Budget（QCFP-MTF 2.8：53 号决策负担预算）

测量"决策本身有多麻烦"（牛散现实负担），不是新的交易评分：
    decisions/week / position changes/month / simultaneous positions /
    binding reasons / manual attention events / emergency actions

验收标准：升级不能只提高 Sharpe 而让 Decision Burden 无限制上升；
OOS 表现相近时，优先负担更低、单位决策复杂度实战价值更高的版本。
"""


DECISION_COST_LIMITS = {
    "decisions_per_week": 5,
    "position_changes_per_month": 8,
    "simultaneous_positions": 8,
    "binding_reasons": 3,
    "manual_attention_events": 5,
    "emergency_actions": 2,
}


def decision_cost_budget(metrics: dict, limits=None) -> dict:
    limits = limits or DECISION_COST_LIMITS
    checks, over = [], []
    for key, limit in limits.items():
        value = metrics.get(key)
        ok = value is not None and float(value) <= limit
        checks.append({"metric": key, "value": value,
                       "limit": limit, "ok": ok})
        if not ok:
            over.append(key)
    score = sum(1 for c in checks if c["ok"]) / len(checks) * 10
    level = ("LOW" if score >= 8 else "MEDIUM" if score >= 5 else "HIGH")
    return {"checks": checks, "over_budget": over,
            "within_budget": not over,
            "burden_score": round(score, 1),
            "burden_level": level}


def compare_versions_for_retail(version_a: dict, version_b: dict,
                                oos_similar: bool = True) -> dict:
    """两个版本：OOS 相近 → 选负担低；OOS 差异显著 → 选 Sharpe 高。"""
    a_cost = decision_cost_budget(version_a.get("decision_cost") or {})
    b_cost = decision_cost_budget(version_b.get("decision_cost") or {})
    if oos_similar:
        if b_cost["burden_score"] > a_cost["burden_score"]:
            return {"preferred": version_b.get("version") or "B",
                    "reason": "OOS 相近 → 选 Decision Burden 更低"}
        if a_cost["burden_score"] > b_cost["burden_score"]:
            return {"preferred": version_a.get("version") or "A",
                    "reason": "OOS 相近 → 选 Decision Burden 更低"}
        return {"preferred": None,
                "reason": "负担相同，两者等价"}
    sharpe_a = float(version_a.get("oos_sharpe") or 0.0)
    sharpe_b = float(version_b.get("oos_sharpe") or 0.0)
    preferred_label = "B" if sharpe_b > sharpe_a else "A"
    preferred = (version_b.get("version") or preferred_label
                 if sharpe_b > sharpe_a
                 else version_a.get("version") or preferred_label)
    return {"preferred": preferred,
            "reason": "OOS 差异显著 → 选 Sharpe 更高"}


def retail_practicality_gate(candidates: list) -> dict:
    """新 53 号：Decision Cost Budget 正式进入牛散实战验收——
    OOS 表现接近时，优先选择负担更低的版本。"""
    if not candidates:
        return {"preferred": None, "reason": "无候选版本"}
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (decision_cost_budget(
            c.get("decision_cost") or {})["burden_score"],
                       -float(c.get("oos_sharpe") or 0.0)),
        reverse=True)
    best = sorted_candidates[0]
    best_score = decision_cost_budget(
        best.get("decision_cost") or {})["burden_score"]
    return {"preferred": best.get("version"),
            "burden_score": best_score,
            "reason": "优先选择决策负担更低且 OOS 接近的版本",
            "rule": "不能为了小幅 Sharpe 提升无限增加决策负担"}
