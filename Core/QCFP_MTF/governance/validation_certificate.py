# coding: utf-8
"""ValidationCertificate（QCFP-MTF 2.8：14 号统一验证证书）

正式状态只能来自证书：
    PIT / OOS / Ablation / CostStress / ExecutionStress / Regime /
    Replay / Governance / Shadow / OverallStatus

报告只显示证书；没有证书 → 只能显示 NOT CERTIFIED / UNKNOWN，
绝不能显示 "RESEARCH VALIDATED"。
"""


CERTIFICATE_GATES = ("pit", "oos", "ablation", "cost_stress",
                     "execution_stress", "regime_robustness", "replay",
                     "governance", "shadow")


def validation_certificate(checks: dict, certificate_id="") -> dict:
    """生成验证证书。

    checks：{gate: True/False}；缺失 gate 视为 UNKNOWN（fail-closed）。
    """
    statuses = {}
    for gate in CERTIFICATE_GATES:
        v = checks.get(gate)
        if v is None:
            statuses[gate] = "UNKNOWN"
        elif v:
            statuses[gate] = "PASS"
        else:
            statuses[gate] = "FAIL"
    failed = [g for g, s in statuses.items() if s == "FAIL"]
    unknown = [g for g, s in statuses.items() if s == "UNKNOWN"]
    if failed:
        overall = "NOT_CERTIFIED"
    elif unknown:
        overall = "UNKNOWN"
    else:
        overall = "CERTIFIED"
    return {
        "certificate_id": certificate_id or "CERT-NONE",
        "gates": statuses,
        "failed_gates": failed,
        "unknown_gates": unknown,
        "overall_status": overall,
        "is_validated": overall == "CERTIFIED",
        "display_status": "RESEARCH VALIDATED"
        if overall == "CERTIFIED" else
        "NOT CERTIFIED" if failed else "UNKNOWN",
    }


def certificate_display(certificate: dict) -> str:
    """报告唯一显示入口：无证书 → UNKNOWN（绝不显示 RESEARCH VALIDATED）。"""
    if not certificate:
        return "UNKNOWN"
    return certificate.get("display_status", "UNKNOWN")


def research_validated_from_summary(summary: dict) -> dict:
    """新 11 号：全项目唯一能从回测汇总推导研究状态的入口。

    Report/Script 禁止自行判断 RESEARCH VALIDATED；只能
    ResearchGate → ValidationCertificate → certificate_display()。
    缺失任一 gate → UNKNOWN（fail-closed）。
    """
    overall = (summary or {}).get("overall", {}) or {}
    rstatus = (summary or {}).get("run_status", {}) or {}
    oos = (summary or {}).get("rolling_oos_evaluation", []) or []
    oos_sharpes = [r.get("sharpe") for r in oos
                   if r.get("sharpe") is not None]
    median_oos = sorted(oos_sharpes)[len(oos_sharpes) // 2] \
        if oos_sharpes else None
    checks = {
        "pit": rstatus.get("pit_grade") in ("A", "B"),
        "oos": bool(median_oos is not None and median_oos > 0),
        # 可选 gate：缺失 → None → UNKNOWN（fail-closed，不是 FAIL）
        "ablation": (summary or {}).get("ablation_ok"),
        "cost_stress": (summary or {}).get("cost_stress_ok"),
        "execution_stress": (summary or {}).get("execution_stress_ok"),
        "regime_robustness": (summary or {}).get("regime_robustness_ok"),
        "replay": (summary or {}).get("replay_ok"),
        "governance": rstatus.get("status") != "FAILED",
        "shadow": (summary or {}).get("shadow_ok"),
    }
    cert = validation_certificate(checks)
    return {"certificate": cert,
            "display_status": certificate_display(cert)}
