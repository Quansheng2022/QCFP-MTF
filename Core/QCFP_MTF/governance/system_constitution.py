# coding: utf-8
"""System Constitution Test（QCFP-MTF 2.8：80 号系统宪法）

把 QCFP-MTF 的核心原则固化成不可回归测试：
    Permission > Signal
    PIT > Prediction
    Risk > Return
    Production cannot self-modify
    Future-aware data cannot enter past decision
    Final target can only be reduced downstream
    Unknown must degrade
    Every production decision must be replayable

验收标准：任何版本只要违反其中一条，
就算收益提升也不能 Promotion。
"""


CONSTITUTION_PRINCIPLES = (
    ("PERMISSION_OVER_SIGNAL", "Permission > Signal"),
    ("PIT_OVER_PREDICTION", "PIT > Prediction"),
    ("RISK_OVER_RETURN", "Risk > Return"),
    ("LEDGER_HASH_REPLAY",
     "Ledger + Hash + Replay（每个生产决策必须可重放）"),
    ("OOS_ABLATION_STRESS_OVER_SUBJECTIVE",
     "OOS + Ablation + Stress > subjective judgment"),
    ("OPPORTUNITY_CANNOT_UPGRADE_PERMISSION",
     "Opportunity cannot upgrade Permission"),
    ("NO_SELF_MODIFY", "Production cannot self-modify"),
    ("NO_FUTURE_IN_PAST",
     "Future-aware data cannot enter past decision"),
    ("TARGET_ONLY_DOWNSTREAM_REDUCTION",
     "Final target can only be reduced downstream"),
    ("UNKNOWN_DEGRADES", "Unknown must degrade"),
    ("REPORT_CANNOT_CREATE_DECISION",
     "Report cannot create Decision"),
    ("RESEARCH_CANNOT_WRITE_PRODUCTION",
     "Research cannot write Production"),
)


def system_constitution_check(checks: dict) -> dict:
    """checks：{principle_key: bool 或 (ok, evidence)}。"""
    results, failures = {}, []
    for key, text in CONSTITUTION_PRINCIPLES:
        v = checks.get(key)
        if isinstance(v, tuple) and len(v) == 2:
            ok, evidence = bool(v[0]), str(v[1] or "")
        else:
            ok, evidence = bool(v), ""
        results[key] = {"principle": text, "ok": ok,
                        "evidence": evidence}
        if not ok:
            failures.append(key)
    return {
        "constitution": results,
        "failures": failures,
        "pass": not failures,
        "promotion_verdict": "PROMOTE_OK" if not failures
        else "PROMOTION_REJECTED",
        "rule": "违反任一条宪法 → 即使收益提升也不能 Promotion",
    }


def constitution_gate(checks: dict,
                      performance_evidence: dict = None) -> dict:
    """新 80 号：Constitution Test 是最高优先级 Regression Gate——
    优先级高于 Performance / Ablation / Retail Utility；
    任一失败 → CONSTITUTION_FAIL → Promotion = REJECTED，
    不允许 Sharpe+30% 破例。"""
    result = system_constitution_check(checks)
    if not result["pass"]:
        return {
            "verdict": "CONSTITUTION_FAIL",
            "failures": result["failures"],
            "promotion": "REJECTED",
            "performance_evidence": performance_evidence,
            "rule": "Sharpe +30% 也不能破例通过——"
                    "它决定的是这个系统是不是 QCFP_MTF，"
                    "而不仅仅是它赚不赚钱",
        }
    return {"verdict": "CONSTITUTION_PASS",
            "failures": [],
            "promotion": "ALLOWED",
            "performance_evidence": performance_evidence}
