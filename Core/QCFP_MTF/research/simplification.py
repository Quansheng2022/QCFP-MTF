# coding: utf-8
"""Decision Policy Simplification Engine（QCFP-MTF 2.8：39 号最小有效系统）

Complex System → Ablation → Pruning → Simplification →
Minimum Effective System

目标不是"最简单"，而是 Minimum Effective Complexity：
    Complexity↓ ≥ 30% 且 Sharpe 损失 ≤ 5% → 推荐简化版。
"""


def simplification_engine(full_sharpe, simplified_sharpe,
                          full_complexity, simplified_complexity,
                          min_complexity_reduction=0.30,
                          max_sharpe_loss=0.05) -> dict:
    """简化判定。"""
    full_c = float(full_complexity or 0.0)
    simp_c = float(simplified_complexity or 0.0)
    full_s = float(full_sharpe or 0.0)
    simp_s = float(simplified_sharpe or 0.0)
    if full_c <= 0:
        return {"recommend": False, "reason": "NO_COMPLEXITY_BASELINE"}
    complexity_reduction = (full_c - simp_c) / full_c
    sharpe_loss = max(0.0, full_s - simp_s)
    sharpe_loss_ratio = sharpe_loss / max(full_s, 1e-9)
    recommend = (complexity_reduction >= min_complexity_reduction
                 and sharpe_loss_ratio <= max_sharpe_loss)
    return {
        "full_sharpe": round(full_s, 4),
        "simplified_sharpe": round(simp_s, 4),
        "full_complexity": round(full_c, 4),
        "simplified_complexity": round(simp_c, 4),
        "complexity_reduction": round(complexity_reduction, 4),
        "sharpe_loss_ratio": round(sharpe_loss_ratio, 4),
        "recommend_simplification": recommend,
        "reason": ("简化保留 ≥90% Sharpe 且复杂度↓"
                   if recommend else "不建议简化"),
    }


def minimum_effective_system(candidates: dict) -> dict:
    """在多个简化候选中选 Minimum Effective（Sharpe 损失最小且复杂度最低）。"""
    best = None
    for name, cand in candidates.items():
        r = simplification_engine(
            cand["full_sharpe"], cand["simplified_sharpe"],
            cand["full_complexity"], cand["simplified_complexity"])
        if r["recommend_simplification"]:
            if best is None or (cand["simplified_complexity"]
                                < best["simplified_complexity"]):
                best = {**cand, "name": name, "analysis": r}
    return {"best": best, "recommend": best is not None}
