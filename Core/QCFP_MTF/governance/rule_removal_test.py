# coding: utf-8
"""Rule Removal Test（QCFP-MTF 2.8：83 号规则删除测试）

把 Ablation 正式变成 Production simplification gate：
    Current Canonical vs Canonical - Rule X
比较 CAGR / Sharpe / MDD / Tail loss / Wave capture / Turnover /
Decision burden / Retail practicality / Binding constraint coverage。

如果删除后 Performance ≈、Risk ≈、Practicality ↑、Complexity ↓
→ 优先删除。删除功能也必须像增加功能一样经过正式验证。
"""


REMOVAL_METRICS = ("cagr", "sharpe", "mdd", "tail_loss", "wave_capture",
                   "turnover", "decision_burden", "retail_practicality",
                   "binding_constraint_coverage")

HIGHER_BETTER = {"cagr", "sharpe", "wave_capture",
                 "retail_practicality", "binding_constraint_coverage"}

DEFAULT_TOLERANCES = {
    "cagr": 0.02, "sharpe": 0.10, "mdd": 0.02, "tail_loss": 0.02,
    "wave_capture": 0.05, "turnover": 0.20, "decision_burden": 0.10,
    "retail_practicality": 0.0, "binding_constraint_coverage": 0.05,
}


def rule_removal_test(current: dict, without_rule: dict,
                      tolerances=None) -> dict:
    """比较删除规则前后的生产指标，输出 REMOVE / REVIEW / KEEP。"""
    tol = dict(DEFAULT_TOLERANCES)
    tol.update(tolerances or {})
    worse, improved = [], []
    for metric in REMOVAL_METRICS:
        cur = float(current.get(metric) or 0.0)
        new = float(without_rule.get(metric) or 0.0)
        if metric in HIGHER_BETTER:
            delta = new - cur
            if delta < -tol.get(metric, 0.0):
                worse.append(metric)
            elif delta > tol.get(metric, 0.0) * 0.5:
                improved.append(metric)
        else:
            delta = cur - new  # 值下降 = 改善
            if delta < -tol.get(metric, 0.0):
                worse.append(metric)
            elif delta > tol.get(metric, 0.0) * 0.5:
                improved.append(metric)
    if not worse:
        verdict = "REMOVE"
        reason = "Performance/Risk ≈、Practicality/复杂度改善 → 优先删除"
    elif len(worse) == 1:
        verdict = "REVIEW"
        reason = f"单一指标 {worse} 轻微变差 → 复核后决定"
    else:
        verdict = "KEEP"
        reason = f"删除后 {worse} 明显变差 → 保留"
    return {"worse_metrics": worse, "improved_metrics": improved,
            "verdict": verdict, "reason": reason,
            "rule": "删除功能也必须像增加功能一样经过正式验证"}


def rule_removal_candidates(modules: dict, evidence_ok: bool = True) -> dict:
    """新 83 号：周期性产生 Rule Removal Candidate——
    删除同样走 PIT/OOS/Ablation/Stress，目标反过来：
    证明没有它仍然足够好。"""
    candidates = []
    for module, m in (modules or {}).items():
        if m.get("removal_candidate"):
            candidates.append(module)
    return {
        "removal_candidates": candidates,
        "removal_count": len(candidates),
        "validation_required": "FULL_VALIDATION",
        "evidence_ok": bool(evidence_ok),
        "verdict": "REMOVAL_GATE_OK" if candidates and evidence_ok
        else "REMOVAL_GATE_BLOCKED" if candidates else "NO_CANDIDATES",
        "rule": "每个大版本至少主动挑战若干 ACTIVE rules，"
                "而不是只研究新增规则",
    }
