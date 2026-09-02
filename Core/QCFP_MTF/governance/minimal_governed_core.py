# coding: utf-8
"""Minimal Governed Core（QCFP-MTF 2.8：90 号最小治理核心）

QCFP-MTF 1–90 的最终架构目标——系统最少需要哪些组件，
仍然保持治理完整和牛散实战价值：
    1. PIT Evidence
    2. Institutional Permission
    3. Wave Opportunity
    4. FSM / Position Proposal
    5. Risk + Portfolio + Liquidity Governance
    6. Canonical Final Target
    7. Execution Plan
    8. DecisionSnapshot
    9. Append-only Ledger
    10. Research Validation

其他功能必须证明是这 10 个核心组件的必要子能力，
否则进入 Research-only / Shadow-only / Appendix / Archive / Retire。
"""


MINIMAL_GOVERNED_CORE = (
    ("pit_evidence", "PIT Evidence"),
    ("institutional_permission", "Institutional Permission"),
    ("wave_opportunity", "Wave Opportunity"),
    ("fsm_position_proposal", "FSM / Position Proposal"),
    ("risk_portfolio_liquidity_governance",
     "Risk + Portfolio + Liquidity Governance"),
    ("canonical_final_target", "Canonical Final Target"),
    ("execution_plan", "Execution Plan"),
    ("decision_snapshot", "DecisionSnapshot"),
    ("append_only_ledger", "Append-only Ledger"),
    ("research_validation", "Research Validation"),
)

NON_PRODUCTION_CLASSES = ("RESEARCH_ONLY", "SHADOW_ONLY", "APPENDIX",
                          "ARCHIVE", "RETIRE")


def minimal_governed_core_check(modules: dict) -> dict:
    """modules：{module: {"classification": str,
    "subcapability_of": str?}}"""
    core_keys = [k for k, _ in MINIMAL_GOVERNED_CORE]
    core_present = {k: False for k in core_keys}
    violations, missing = [], []
    for module, attrs in (modules or {}).items():
        attrs = attrs or {}
        cls = str(attrs.get("classification") or "").upper()
        parent = attrs.get("subcapability_of")
        if module in core_keys:
            core_present[module] = True
        elif cls == "SUB_CAPABILITY" and parent:
            if parent not in core_keys:
                violations.append(
                    f"{module}: subcapability 指向非核心 {parent}")
        elif cls in NON_PRODUCTION_CLASSES:
            pass
        else:
            violations.append(f"{module}: 非核心且非研究/附录/退役"
                              f"（classification={cls or '未声明'}）")
    missing = [k for k, present in core_present.items() if not present]
    aligned = not violations and not missing
    return {
        "core": dict(MINIMAL_GOVERNED_CORE),
        "core_present": core_present,
        "missing_core": missing,
        "violations": violations,
        "aligned": aligned,
        "verdict": "ALIGNED" if aligned else "ACTION_REQUIRED",
        "rule": "其他功能必须是核心的必要子能力，否则只能留在"
                "研究/影子/附录/归档/退役",
    }


def minimum_governed_core_decision(full_metrics: dict,
                                   minimal_metrics: dict,
                                   full_complexity=2.0,
                                   minimal_complexity=1.0,
                                   min_value_gain=0.05) -> dict:
    """新 30 号：第一版 Minimum Governed Core 决策规则。

    如果 Full 复杂度 +100% 但实战价值只 +2% → 默认 SIMPLIFY。
    实战价值 = Sharpe/MDD/WaveCapture/Practicality 综合。
    """
    def _value(m):
        sharpe = float(m.get("sharpe") or 0.0)
        mdd = abs(float(m.get("mdd") or 0.0))
        capture = float(m.get("wave_capture") or 0.0)
        practical = float(m.get("practicality") or 0.0)
        return sharpe - mdd * 0.3 + capture * 0.5 + practical * 0.5
    full_v = _value(full_metrics)
    min_v = _value(minimal_metrics)
    value_gain = round((full_v - min_v) / max(min_v, 1e-9), 4)
    complexity_ratio = round(
        float(full_complexity) / max(float(minimal_complexity), 1e-9), 2)
    if complexity_ratio >= 2.0 and value_gain < min_value_gain:
        verdict = "SIMPLIFY"
        reason = "Full 复杂度 ≥2× 但实战价值增量 <5% → 默认简化"
    elif value_gain >= min_value_gain:
        verdict = "KEEP_FULL"
        reason = "Full 提供了稳定实战价值增量"
    else:
        verdict = "SIMPLIFY"
        reason = "Full 未提供足够价值增量 → 保留更小版本"
    return {"full_value": round(full_v, 4),
            "minimal_value": round(min_v, 4),
            "value_gain": value_gain,
            "complexity_ratio": complexity_ratio,
            "verdict": verdict,
            "reason": reason,
            "rule": "最少保留哪些模块能保持 95%–100% 实战价值 "
                    "和 100% 治理完整性？"}


def production_chain_completeness(chain) -> dict:
    """新 90 号：Production 架构必须能用十阶段链完整解释，
    不允许存在第二套权力链。"""
    present = list(chain or [])
    core_keys = [k for k, _ in MINIMAL_GOVERNED_CORE]
    missing = [k for k in core_keys if k not in present]
    extra = [k for k in present if k not in core_keys]
    return {
        "core_stages": core_keys,
        "missing": missing,
        "extra_non_core_stages": extra,
        "complete": not missing,
        "single_authority_chain": not missing and not extra,
        "verdict": "SINGLE_CHAIN" if not missing and not extra
        else "SECOND_AUTHORITY_CHAIN_DETECTED" if extra
        else "INCOMPLETE",
        "rule": "Production 最终可以用一条十阶段链完整解释，"
                "不需要额外的第二套权力链",
    }


def remap_to_core(modules: dict) -> dict:
    """新 90 号：把全部模块重新映射到十个核心；
    无法映射且没有独立必要性 → 降级/删除。"""
    core_keys = [k for k, _ in MINIMAL_GOVERNED_CORE]
    remapped = {}
    downgraded = []
    for module, attrs in (modules or {}).items():
        attrs = attrs or {}
        parent = attrs.get("subcapability_of") or attrs.get("maps_to")
        if module in core_keys:
            remapped[module] = "CORE"
        elif parent in core_keys:
            remapped[module] = f"SUB_CAPABILITY_OF_{parent}"
        elif attrs.get("necessity_proven"):
            remapped[module] = "CORE_SUB_CAPABILITY"
        else:
            downgraded.append(module)
            remapped[module] = "DOWNGRADE_OR_RETIRE"
    return {"remapped": remapped,
            "downgraded": downgraded,
            "rule": "无法映射且无独立必要性的模块 → 降级或删除"}
