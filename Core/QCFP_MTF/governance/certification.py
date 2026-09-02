# coding: utf-8
"""End-to-End Governance Certification（QCFP-MTF 2.8：50 号全链路治理认证）

每次 Release 必须通过五维认证（1–49 项收敛为可审计的生产准入标准）：
    A 不可越权  Permission Gate / Risk Cap / Portfolio Cap / Execution Cap /
                Governance Proof
    B 可审计    Ledger / Certificate / Reason Code / Constraint Trace /
                Data Lineage / Version Identity
    C 可回测    PIT / OOS / Cost / Execution / Replay
    D 可Ablation Permission / Wave / FSM / Risk / Execution Ablation
    E 牛散实战  Wave Lifecycle / Entry / Exit / MFE Capture /
                Progressive Sizing / Liquidity Exit / Capital Efficiency

输出：CERTIFIED / NOT_CERTIFIED（不是研究人员主观决定）。
"""


CERTIFICATION_DIMENSIONS = {
    "no_override": {
        "label": "不可越权",
        "checks": ("permission_gate", "risk_cap", "portfolio_cap",
                   "execution_cap", "governance_proof"),
    },
    "auditable": {
        "label": "可审计",
        "checks": ("ledger", "certificate", "reason_code",
                   "constraint_trace", "data_lineage", "version_identity"),
    },
    "backtestable": {
        "label": "可回测",
        "checks": ("pit", "oos", "cost", "execution", "replay"),
    },
    "ablatable": {
        "label": "可Ablation",
        "checks": ("permission_ablation", "wave_ablation", "fsm_ablation",
                   "risk_ablation", "execution_ablation"),
    },
    "retail_practical": {
        "label": "牛散实战",
        "checks": ("wave_lifecycle", "entry_quality", "exit_quality",
                   "mfe_capture", "progressive_sizing", "liquidity_exit",
                   "capital_efficiency"),
    },
}


def governance_certification(checks: dict) -> dict:
    """五维认证：任一检查缺失/失败 → NOT_CERTIFIED。"""
    dimensions = {}
    all_ok = True
    for dim, spec in CERTIFICATION_DIMENSIONS.items():
        missing = [c for c in spec["checks"] if not checks.get(c)]
        ok = not missing
        all_ok = all_ok and ok
        dimensions[dim] = {"label": spec["label"], "ok": ok,
                           "missing": missing}
    return {
        "certified": all_ok,
        "status": "CERTIFIED" if all_ok else "NOT_CERTIFIED",
        "dimensions": dimensions,
    }


def certification_to_md(cert: dict) -> str:
    lines = [
        "# QCFP-MTF Governance Certification",
        "",
        f"**{cert['status']}**",
        "",
        "| 维度 | 状态 | 缺失项 |", "| --- | --- | --- |",
    ]
    for dim, spec in cert["dimensions"].items():
        lines.append(f"| {spec['label']} | "
                     f"{'✅' if spec['ok'] else '❌'} | "
                     f"{', '.join(spec['missing']) or '-'} |")
    return "\n".join(lines)
