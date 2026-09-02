# coding: utf-8
"""Production Acceptance Contract（QCFP-MTF 2.8：51 号生产验收契约）

把散落各处的测试收敛成一份最短的"什么叫可以正式使用"契约：
    PIT / REPLAY / LEDGER / OOS / STRESS / SHADOW / GOVERNANCE /
    NO_CRITICAL_UNKNOWN 全部 PASS 才 ACCEPTED。

验收规则：
    - 最终结论只能是 ACCEPTED / REJECTED（不设"基本通过"）；
    - 每个结论必须引用对应证据；
    - 任何一条治理失败都不能因 Sharpe 漂亮而被覆盖。
"""


PRODUCTION_ACCEPTANCE_GATES = (
    "PIT", "REPLAY", "LEDGER", "OOS", "STRESS", "SHADOW",
    "GOVERNANCE", "NO_CRITICAL_UNKNOWN",
)


def production_acceptance_contract(gate_results: dict) -> dict:
    """gate_results：{gate: {"ok": bool, "evidence": ref}} 或 {gate: bool}。"""
    results, failures = {}, []
    for gate in PRODUCTION_ACCEPTANCE_GATES:
        v = gate_results.get(gate)
        if isinstance(v, dict):
            ok, evidence = bool(v.get("ok")), str(v.get("evidence") or "")
        elif isinstance(v, tuple) and len(v) == 2:
            ok, evidence = bool(v[0]), str(v[1] or "")
        else:
            ok, evidence = bool(v), ""
        results[gate] = {"ok": ok, "evidence": evidence}
        if not ok:
            failures.append(gate)
    accepted = not failures
    return {
        "contract": "PRODUCTION_ACCEPTANCE_V1",
        "gates": results,
        "failures": failures,
        "verdict": "ACCEPTED" if accepted else "REJECTED",
        "reason": "全部生产门槛通过，可正式使用" if accepted
        else f"生产门槛未通过: {failures}（治理失败不能被收益覆盖）",
        "binary_verdict": True,
    }


def production_acceptance_gate(acceptance: dict, release_verdict="",
                               certified_decisions=None) -> dict:
    """新 51 号：Production Acceptance 成为唯一生产验收总闸——
    REJECTED Release → CertifiedDecision 数量必须为 0。"""
    rejected = acceptance.get("verdict") == "REJECTED" or \
        release_verdict == "REJECTED"
    certified = list(certified_decisions or [])
    violation = rejected and bool(certified)
    return {
        "acceptance_verdict": acceptance.get("verdict"),
        "release_verdict": release_verdict,
        "certified_decision_count": len(certified),
        "violation": violation,
        "verdict": "GATE_OK" if not violation else "GATE_VIOLATION",
        "rule": "REJECTED Release → CertifiedDecision 数量必须为 0；"
                "验收不通过就不能执行",
    }
