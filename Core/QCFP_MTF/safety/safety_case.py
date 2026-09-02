# coding: utf-8
"""System Safety Case（QCFP-MTF 2.8：99 号系统安全论证）

机器可验证的"为什么可以进入生产"证据链：
    Claim → Requirement → Test → Evidence → Certification

核心 Claim：
    C1 机构权限不可被 Signal Override
    C2 Risk Cap 不可被 Portfolio Override
    C3 PIT 数据约束成立
    C4 OOS 结果可复现
    C5 Ablation 结果完整
    C6 生产版本与认证版本一致（Hash/Provenance）
"""


SAFETY_CLAIMS = {
    "C1_permission_not_overridable": {
        "requirement": "Wave/Signal 不能改变 Permission 等级",
        "test": "assert_wave_cannot_upgrade + I10 不变量",
        "evidence_key": "permission_monotonicity"},
    "C2_risk_cap_not_overridable": {
        "requirement": "Risk Cap 不能被 Portfolio/信号覆盖",
        "test": "finalize_target min-chain + I3 不变量",
        "evidence_key": "risk_cap_respected"},
    "C3_pit_holds": {
        "requirement": "所有决策特征 available_at ≤ decision_time",
        "test": "InformationSet.assert_pit_clean + I7 不变量",
        "evidence_key": "pit_clean"},
    "C4_oos_reproducible": {
        "requirement": "OOS 结果可复现（确定性回放）",
        "test": "replay_engine + oos_summary",
        "evidence_key": "oos_reproducible"},
    "C5_ablation_complete": {
        "requirement": "Ablation 覆盖全部模块",
        "test": "ablation_matrix + incremental_alpha",
        "evidence_key": "ablation_complete"},
    "C6_version_matches": {
        "requirement": "生产版本 = 认证版本（Hash/Provenance）",
        "test": "release_identity + provenance chain",
        "evidence_key": "version_matches"},
}


def system_safety_case(evidence: dict) -> dict:
    """安全论证：evidence 提供各 claim 的布尔证据。"""
    claims = {}
    all_pass = True
    for claim_id, spec in SAFETY_CLAIMS.items():
        ok = bool(evidence.get(spec["evidence_key"]))
        all_pass = all_pass and ok
        claims[claim_id] = {
            "requirement": spec["requirement"],
            "test": spec["test"],
            "evidence": bool(evidence.get(spec["evidence_key"])),
            "certification": "PASS" if ok else "FAIL",
        }
    return {
        "claims": claims,
        "all_pass": all_pass,
        "status": "SAFE_FOR_PRODUCTION" if all_pass
        else "NOT_SAFE_FOR_PRODUCTION",
        "failed_claims": [c for c, s in claims.items()
                         if s["certification"] == "FAIL"],
    }


def safety_case_to_md(case: dict) -> str:
    lines = [
        "# System Safety Case",
        "",
        f"**Status：{case['status']}**",
        "",
        "| Claim | Requirement | Test | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for cid, spec in case["claims"].items():
        lines.append(f"| {cid} | {spec['requirement']} | {spec['test']} | "
                     f"{'✅' if spec['certification'] == 'PASS' else '❌'} |")
    return "\n".join(lines)
