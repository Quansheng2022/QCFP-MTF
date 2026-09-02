# coding: utf-8
"""Binding Constraint Frequency（QCFP-MTF 2.8：65 号约束绑定频率）

统计真正成为 binding constraint 的频率，例如
    Permission 18% / Liquidity 7% / Portfolio 2% / Drawdown 0.1% /
    Execution 0%

两类问题：
    - 几乎从未绑定 → 可能冗余；
    - 天天绑定 → 上游 Proposal 与实战约束严重脱节。

验收标准：长期 0 binding + 0 ablation value 的模块进入 REVIEW/RETIRE。
"""


def binding_constraint_frequency(decisions) -> dict:
    """decisions：[{"binding_constraint": name}] 或约束 trace。"""
    counts = {}
    total = len(decisions or [])
    for d in decisions or []:
        name = d.get("binding_constraint") if isinstance(d, dict) \
            else getattr(d, "binding_constraint", None)
        if name:
            counts[name] = counts.get(name, 0) + 1
    frequency = {k: round(n / total, 4) for k, n in counts.items()} \
        if total else {}
    never_binding = []
    return {"total_decisions": total, "frequency": frequency,
            "top_binding": max(frequency, key=frequency.get)
            if frequency else None,
            "never_binding": never_binding,
            "note": "长期 0 binding + 0 ablation value → REVIEW/RETIRE"}


def constraint_necessity(module, binding_frequency, ablation_value,
                         binding_threshold: float = 0.05) -> dict:
    """单个模块的必要性判定。"""
    freq = float(binding_frequency or 0.0)
    abl = float(ablation_value or 0.0)
    if freq > binding_threshold:
        return {"module": module, "verdict": "ACTIVE_BINDING",
                "binding_frequency": round(freq, 4),
                "reason": "实际成为 binding constraint，具备约束价值"}
    if freq == 0.0 and abs(abl) <= 0.005:
        return {"module": module, "verdict": "RETIRE_CANDIDATE",
                "binding_frequency": round(freq, 4),
                "reason": "长期 0 binding 且无 Ablation 增量 → 退役候选"}
    return {"module": module, "verdict": "REVIEW",
            "binding_frequency": round(freq, 4),
            "reason": "绑定频率低但有（潜在）独立价值 → 复核"}


def binding_constraint_attribution(snapshots) -> dict:
    """新 25 号：Binding Constraint Attribution 长期统计。

    每个 ACTIVE Governance module 回答：
        triggered frequency    约束出现在 trace 中的比例
        binding frequency      实际成为 binding 的比例
        independent impact     因该约束 target < raw_target 的比例
    """
    snapshots = list(snapshots or [])
    total = len(snapshots)
    triggered = {}
    binding = {}
    impact = {}
    for s in snapshots:
        trace = getattr(s, "constraint_trace", None) or {}
        steps = trace.get("steps") or []
        seen = {str(st.get("constraint")) for st in steps}
        for name in seen:
            triggered[name] = triggered.get(name, 0) + 1
        b = getattr(s, "binding_constraint", "") or ""
        if b:
            binding[b] = binding.get(b, 0) + 1
            raw = float(getattr(s, "raw_target_position", 0.0) or 0.0)
            final = float(getattr(s, "target_position", 0.0) or 0.0)
            if final < raw - 1e-9:
                impact[b] = impact.get(b, 0) + 1
    def _freq(d):
        return {k: round(n / total, 4) for k, n in d.items()} \
            if total else {}
    return {
        "n_snapshots": total,
        "triggered_frequency": _freq(triggered),
        "binding_frequency": _freq(binding),
        "independent_impact_frequency": _freq(impact),
        "rule": "存在一个约束 ≠ 这个约束有实际价值",
    }


def retirement_evidence(module, binding_frequency, ablation_value,
                        mandatory_governance=False) -> dict:
    """新 65 号：长期 binding=0 + ablation value=0 + non-mandatory
    governance → 必须进入删除审查。"""
    freq = float(binding_frequency or 0.0)
    abl = float(ablation_value or 0.0)
    if freq == 0.0 and abs(abl) <= 0.005 and not mandatory_governance:
        return {"module": module,
                "verdict": "RETIRE_REVIEW",
                "reason": "binding=0 + ablation value=0 + 非强制治理 → "
                          "删除审查",
                "retire": True}
    if freq == 0.0:
        return {"module": module, "verdict": "REVIEW",
                "reason": "从未 binding → 复核",
                "retire": False}
    return {"module": module, "verdict": "ACTIVE_BINDING",
            "reason": "实际成为 binding constraint",
            "retire": False}


def liquidity_high_binding_diagnosis(binding_frequency) -> dict:
    """新 65 号：Liquidity binding 65% 不一定是 Liquidity 太严格，
    更可能是上游 Raw Proposal 不符合港股实际容量——应修改 Proposal。"""
    freq = float(binding_frequency or 0.0)
    if freq >= 0.5:
        return {"diagnosis": "PROPOSAL_CAPACITY_MISMATCH",
                "guidance": "Liquidity 高频 binding → 修改上游 Proposal，"
                            "而不是放宽 Liquidity",
                "binding_frequency": round(freq, 4)}
    return {"diagnosis": "NORMAL",
            "guidance": "Liquidity 绑定频率在正常范围",
            "binding_frequency": round(freq, 4)}


def constraint_keep_verdict(module, attribution: dict,
                            ablation_value=0.0,
                            constitutional=False) -> dict:
    """Release 3（新 25 号）：每个 ACTIVE 约束必须有
    Binding/Ablation Evidence，否则进入删除审查。
    判定：KEEP / REVIEW / MERGE / RETIRE。"""
    binding = float(attribution.get("binding_frequency", 0.0) or 0.0)
    trigger = float(attribution.get("triggered_frequency", 0.0) or 0.0)
    impact = float(attribution.get(
        "independent_impact_frequency", 0.0) or 0.0)
    abl = float(ablation_value or 0.0)
    if constitutional:
        return {"module": module, "verdict": "KEEP",
                "reason": "宪法级治理规则强制保留"}
    if binding <= 0.005 and abs(abl) <= 0.005:
        return {"module": module, "verdict": "RETIRE",
                "reason": "binding=0 + ablation=0 → 删除审查"}
    if trigger > 0.1 and binding <= 0.005:
        return {"module": module, "verdict": "MERGE",
                "reason": "频繁触发但从不 binding → 可能被上游覆盖"}
    if impact <= 0.005:
        return {"module": module, "verdict": "REVIEW",
                "reason": "无独立决策影响 → 复核"}
    return {"module": module, "verdict": "KEEP",
            "reason": "具备 binding + 独立影响证据"}
