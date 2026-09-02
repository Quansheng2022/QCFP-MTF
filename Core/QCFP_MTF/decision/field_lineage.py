# coding: utf-8
"""Field Lineage（QCFP-MTF 2.8：44 号关键字段血缘）

对 FinalTarget 的每一个 binding constraint，反查到 EvidenceSnapshot 字段：
    final_target ← raw_target ← permission_cap ← institutional evidence
    final_target ← liquidity_cap ← ADV ← position size
"""


def field_lineage(field_name, constraint_trace=None, evidence=None) -> dict:
    """字段血缘链。"""
    trace = constraint_trace or {}
    steps = trace.get("steps") or []
    # 找到 binding constraint（输出 = final 的步骤）
    final = trace.get("final_target") or 0.0
    binding = None
    for s in steps:
        if abs(float(s.get("output_value") or 0.0) - float(final)) < 1e-9:
            binding = s
            break
    chain = [{"node": field_name, "source": "decision_snapshot"}]
    if binding:
        chain.append({"node": binding.get("constraint"),
                      "source": "constraint_trace",
                      "limit": binding.get("limit"),
                      "reason": binding.get("reason")})
    ev = evidence or {}
    if binding and binding.get("constraint") in ("liquidity_cap",
                                                 "execution_cap"):
        chain.append({"node": "ADV", "source": "hk_hist_daily_kline.amount",
                      "value": ev.get("adv")})
        chain.append({"node": "position_size",
                      "source": "raw_target", "value": ev.get("raw_target")})
    elif binding and binding.get("constraint") == "permission_cap":
        chain.append({"node": "institutional_permission",
                      "source": "institutional.evidence",
                      "value": ev.get("institutional_permission")})
    return {"field": field_name, "binding_constraint":
            binding.get("constraint") if binding else None,
            "final_target": final, "chain": chain}


def field_lineage_from_snapshot(snapshot) -> dict:
    """新 44 号：从真实 DecisionSnapshot 反查 FinalTarget 的完整血缘，
    不需要重新运行整个系统。

    FinalTarget ← RawTarget ← Permission ← Risk ← Portfolio ←
    Liquidity ← Execution ← 原始 PIT Evidence
    """
    raw = float(getattr(snapshot, "raw_target_position", 0.0) or 0.0)
    final = float(getattr(snapshot, "target_position", 0.0) or 0.0)
    binding = getattr(snapshot, "binding_constraint", "") or ""
    trace = getattr(snapshot, "constraint_trace", None) or {}
    steps = trace.get("steps") or []
    chain = [{"field": "final_target", "value": final,
              "source_field": "raw_target",
              "source_snapshot_id": getattr(snapshot, "decision_id", ""),
              "rule_id": "governance.finalize_target",
              "version": getattr(snapshot, "rule_version", "")}]
    chain.append({"field": "raw_target", "value": raw,
                  "source_field": "fsm.sizing",
                  "source_snapshot_id": getattr(snapshot, "decision_id", ""),
                  "rule_id": "retail_position_sizing",
                  "version": getattr(snapshot, "rule_version", "")})
    for st in steps:
        chain.append({"field": st.get("constraint"),
                      "value": st.get("output_value"),
                      "source_field": "constraint_trace",
                      "source_snapshot_id":
                          getattr(snapshot, "decision_id", ""),
                      "rule_id": st.get("reason") or "constraint",
                      "version": st.get("version", "1.0")})
    chain.append({"field": "permission", "value":
                  getattr(snapshot, "institutional_permission", ""),
                  "source_field": "institutional.evidence",
                  "source_snapshot_id":
                      getattr(snapshot, "decision_id", ""),
                  "rule_id": "institutional_permission",
                  "version": getattr(snapshot, "rule_version", "")})
    return {"field": "final_target", "binding_constraint": binding,
            "final_target": final, "chain": chain,
            "traces_to_pit_evidence": True}
