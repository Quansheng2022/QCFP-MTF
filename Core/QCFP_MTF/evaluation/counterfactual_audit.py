# coding: utf-8
"""Counterfactual Decision Audit（QCFP-MTF 2.8：54 号反事实决策审计）

把 Ablation 落到具体交易决策：Research 环境回答
    Without Liquidity Cap → X / Without Permission → Y /
    Without Wave Gate → Z
并观察实际结果，回答"约束是救了我还是错过了机会"。

铁律：Counterfactual 永远属于 Research Evidence，
不能回写历史 DecisionSnapshot，不能修改 Ledger。
"""

import hashlib
import json


def counterfactual_audit(decision_id, actual_target, counterfactuals,
                         outcome=None, binding_constraint=None) -> dict:
    """counterfactuals：{constraint: without_target}。

    binding_constraint：显式指定被审计的绑定约束；缺省取第一个
    "去掉后会改变实际目标"的约束（最紧的那条）。
    """
    effects, binding = {}, None
    for name, without in (counterfactuals or {}).items():
        try:
            w = float(without)
        except (TypeError, ValueError):
            w = None
        delta = round(w - float(actual_target), 4) \
            if w is not None else None
        effects[name] = {"without": w, "delta_vs_actual": delta}
    if binding_constraint:
        binding = binding_constraint
    else:
        for name, eff in effects.items():
            if eff["delta_vs_actual"] is not None \
                    and abs(eff["delta_vs_actual"]) > 1e-9:
                binding = name
                break
    raw = json.dumps({"decision_id": decision_id,
                      "actual_target": actual_target,
                      "counterfactuals": counterfactuals},
                     sort_keys=True, ensure_ascii=False, default=str)
    audit_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return {
        "audit_id": audit_id,
        "decision_id": decision_id,
        "actual_target": float(actual_target),
        "counterfactuals": effects,
        "binding_constraint": binding,
        "outcome": outcome,
        "research_only": True,
        "cannot_rewrite_snapshot": True,
        "note": "Research Evidence：审计治理价值，不修改历史事实",
    }


def constraint_verdict(audit, realized_return=None) -> dict:
    """结合实际结果给治理价值提示（仅 Research 使用）。"""
    if realized_return is None:
        return {"verdict": "NEEDS_OUTCOME",
                "guidance": "缺少实际结果，无法判定约束价值"}
    binding = audit.get("binding_constraint")
    effect = (audit.get("counterfactuals") or {}).get(binding or "")
    without = (effect or {}).get("without")
    if not binding or without is None:
        return {"verdict": "NO_BINDING_CONSTRAINT",
                "guidance": "该决策无绑定约束可审计"}
    actual = float(audit["actual_target"])
    ret = float(realized_return)
    if without > actual and ret > 0:
        return {"verdict": "MISSED_OPPORTUNITY",
                "guidance": f"去掉 {binding} 本可多持 "
                            f"{without-actual:.0%}，该约束限制了收益"}
    if without > actual and ret < 0:
        return {"verdict": "SAVED_BY_CONSTRAINT",
                "guidance": f"约束 {binding} 降低了实际亏损"}
    return {"verdict": "NEUTRAL",
            "guidance": "约束影响不显著"}


def counterfactual_from_snapshot(snapshot, outcome=None) -> dict:
    """新 54 号：从真实 DecisionSnapshot + ConstraintTrace + Outcome
    自动产生反事实；结果只能进入 Research Evidence Store。"""
    trace = getattr(snapshot, "constraint_trace", None) or {}
    steps = trace.get("steps") or []
    counterfactuals = {}
    raw = float(getattr(snapshot, "raw_target_position", 0.0) or 0.0)
    final = float(getattr(snapshot, "target_position", 0.0) or 0.0)
    for st in steps:
        name = st.get("constraint")
        if name and name != "raw_target":
            # 去掉该约束后的目标 ≈ 该约束的输入值（上游未压减值）
            counterfactuals[name] = st.get("input_value", raw)
    audit = counterfactual_audit(
        getattr(snapshot, "decision_id", ""), final, counterfactuals,
        outcome=outcome,
        binding_constraint=getattr(snapshot, "binding_constraint", "") or None)
    audit["evidence_store"] = "RESEARCH_EVIDENCE_STORE"
    audit["cannot_modify_ledger"] = True
    return audit
