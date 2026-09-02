# coding: utf-8
"""Counterfactual Decision Value（QCFP-MTF 2.8：42 号反事实决策价值）

Ablation 研究"模块是否重要"；Counterfactual 研究"某一次具体决策的价值"：
    Actual（BUY 8% → +8%）
    vs Counterfactual（BUY 4% / NO TRADE / EXIT earlier）

Decision Value = Actual Outcome − Counterfactual Outcome
"""


def counterfactual_value(actual_outcome, counterfactual_outcome,
                         label="counterfactual") -> dict:
    """单反事实决策价值。"""
    a = float(actual_outcome or 0.0)
    c = float(counterfactual_outcome or 0.0)
    return {"label": label,
            "actual_outcome": round(a, 4),
            "counterfactual_outcome": round(c, 4),
            "decision_value": round(a - c, 4),
            "decision_added_value": (a - c) > 0}


def counterfactual_engine(actual_outcome, scenarios: dict) -> dict:
    """多反事实场景对比（BUY 4% / NO TRADE / EXIT earlier /
    Permission OFF / Wave OFF）。"""
    results = {}
    for label, cf_outcome in scenarios.items():
        results[label] = counterfactual_value(actual_outcome, cf_outcome,
                                              label)
    return {"actual_outcome": round(float(actual_outcome or 0.0), 4),
            "scenarios": results,
            "best_alternative": max(
                results.items(),
                key=lambda kv: kv[1]["counterfactual_outcome"])[0]
            if results else None,
            "actual_is_best": all(
                r["decision_value"] >= 0 for r in results.values())}
