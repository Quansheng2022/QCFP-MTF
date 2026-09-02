# coding: utf-8
"""Convergence & Simplification Release（QCFP-MTF 2.8：新 10 号）

第一次真正的"收敛发布"：下一版不再强调新增功能，而是报告：
    Executable decision paths     ↓
    Duplicate authorities         ↓
    Legacy production imports     ↓
    Active feature count          ↓
    Decision-critical LOC         ↓
    Canonical coverage            ↑
    Replay coverage               ↑
    Invariant coverage            ↑
    OOS evidence quality          ↑

Feature 生命周期：
    DEFINED → WIRED → VALIDATED → CERTIFIED → ACTIVE → RETIRED
只有 ACTIVE 进入 ProductionManifest。

必须删除的旧路径（Legacy decision authority / 重复 Permission logic /
重复 performance calculation / 旧 Ablation / Report-side sizing /
Report-side action rewriting / 孤立 governance / 未接线 Feature /
重复 Wave taxonomy / 硬编码 Version）逐项审计，残余一律 ACTION_REQUIRED。
"""


FEATURE_LIFECYCLE = ("DEFINED", "WIRED", "VALIDATED", "CERTIFIED",
                     "ACTIVE", "RETIRED")

DECLUTTER_ITEMS = (
    "legacy_decision_authority",
    "duplicate_permission_logic",
    "duplicate_performance_calculation",
    "legacy_ablation_implementation",
    "report_side_sizing",
    "report_side_action_rewriting",
    "orphan_governance_modules",
    "unwired_feature_claims",
    "duplicate_wave_taxonomy",
    "hardcoded_version",
)

RELEASE_KPIS = ("executable_decision_paths", "duplicate_authorities",
                "legacy_production_imports", "active_feature_count",
                "decision_critical_loc", "canonical_coverage",
                "replay_coverage", "invariant_coverage",
                "oos_evidence_quality")

# 值越低越好的 KPI（下降 = 收敛）
LOWER_IS_BETTER = {"executable_decision_paths", "duplicate_authorities",
                   "legacy_production_imports", "active_feature_count",
                   "decision_critical_loc"}


def convergence_release_report(before: dict, after: dict) -> dict:
    """每项 KPI 报升/降，产出整体收敛判定。"""
    kpis, regressed = {}, []
    for k in RELEASE_KPIS:
        prev = float(before.get(k) or 0.0)
        cur = float(after.get(k) or 0.0)
        delta = round(cur - prev, 4)
        if k in LOWER_IS_BETTER:
            direction = "DOWN" if delta < 0 else \
                "STABLE" if delta == 0 else "UP"
            good = delta <= 0
        else:
            direction = "UP" if delta > 0 else \
                "STABLE" if delta == 0 else "DOWN"
            good = delta >= 0
        kpis[k] = {"before": round(prev, 4), "after": round(cur, 4),
                   "delta": delta, "direction": direction, "good": good}
        if not good:
            regressed.append(k)
    return {"kpis": kpis, "regressed": regressed,
            "converged": not regressed,
            "verdict": "CONVERGED" if not regressed
            else "REGRESSION_ACTION_REQUIRED",
            "rule": "成熟表现是能力不下降，但 Production 更短、"
                    "更硬、更简单"}


def feature_lifecycle_check(features: dict) -> dict:
    """features：{feature: state}；只有 ACTIVE 进入 ProductionManifest。"""
    results = {}
    manifest = []
    invalid = []
    for feature, state in (features or {}).items():
        state = str(state or "").upper()
        if state not in FEATURE_LIFECYCLE:
            invalid.append(feature)
            results[feature] = {"state": state, "invalid": True}
            continue
        results[feature] = {"state": state, "invalid": False}
        if state == "ACTIVE":
            manifest.append(feature)
    return {"features": results, "invalid": invalid,
            "production_manifest": manifest,
            "manifest_valid": not invalid,
            "rule": "只有 ACTIVE 进入 ProductionManifest"}


def declutter_audit(residuals: dict) -> dict:
    """逐项审计旧路径：residuals：{item: bool（True=仍存在残余）}。"""
    results = {}
    action = []
    for item in DECLUTTER_ITEMS:
        residual = bool(residuals.get(item))
        verdict = "CLOSED" if not residual else "ACTION_REQUIRED"
        results[item] = {"residual": residual, "verdict": verdict}
        if residual:
            action.append(item)
    return {"results": results, "action_required": action,
            "all_closed": not action,
            "rule": "收敛发布必须真正删除旧路径，"
                    "而不是只新增治理模块"}


def module_classification_gate(module, stage, necessity_proven=False) -> dict:
    """Convergence 新 10 号：每个模块只能进入
    ACTIVE_CORE / ACTIVE_SUBCAPABILITY / RESEARCH_ONLY / SHADOW_ONLY /
    APPENDIX / ARCHIVE / RETIRED。"""
    if stage in ("INPUT", "PERMISSION", "OPPORTUNITY", "LIFECYCLE",
                 "GOVERNANCE", "OUTPUT", "FACT", "VALIDATION"):
        return {"module": module, "stage": stage,
                "classification": "ACTIVE_CORE",
                "production": True}
    if stage == "SUB_CAPABILITY" and necessity_proven:
        return {"module": module, "stage": stage,
                "classification": "ACTIVE_SUBCAPABILITY",
                "production": True}
    if stage in ("RESEARCH_ONLY", "SHADOW_ONLY", "APPENDIX",
                 "ARCHIVE", "RETIRED"):
        return {"module": module, "stage": stage,
                "classification": stage,
                "production": False}
    return {"module": module, "stage": stage or "UNMAPPED",
            "classification": "RETIRED",
            "production": False,
            "reason": "无法映射到 One-Page Canonical 且无独立必要性"}


def convergence_release_gate(checks: dict) -> dict:
    """Convergence 新 10 号：五个 Release Gate 总闸——
    A Canonical Semantics / B Fail Closed / C Fact Integrity /
    D Research Authority / E Convergence。"""
    gates = (
        "canonical_semantics", "fail_closed", "fact_integrity",
        "research_authority", "convergence")
    results = {g: bool(checks.get(g)) for g in gates}
    failures = [g for g, ok in results.items() if not ok]
    return {"gates": results,
            "failures": failures,
            "verdict": "CONVERGENCE_PASS" if not failures
            else "CONVERGENCE_BLOCKED",
            "allowed": not failures,
            "rule": "唯一决策链、唯一事实链、唯一认证链"}


def retirement_table(modules: dict) -> dict:
    """PWC-1（第 10 项）：物理删除前的 Retirement Table——
    KEEP / MERGE / RESEARCH_ONLY / ARCHIVE / DELETE（不新增状态）。"""
    decisions = {}
    for name, m in (modules or {}).items():
        prod = bool(m.get("production_imported"))
        formal = bool(m.get("formal_research_imported"))
        authority = bool(m.get("unique_authority"))
        value = float(m.get("marginal_value") or 0.0)
        if prod and authority:
            decision = "KEEP"
        elif prod and not authority:
            decision = "MERGE"
        elif formal:
            decision = "RESEARCH_ONLY"
        elif value > 0.01:
            decision = "ARCHIVE"
        else:
            decision = "DELETE"
        decisions[name] = {
            "production_imported": prod,
            "formal_research_imported": formal,
            "unique_authority": authority,
            "marginal_value": round(value, 4),
            "decision": decision,
        }
    return {"retirements": decisions,
            "delete": [n for n, d in decisions.items()
                       if d["decision"] == "DELETE"],
            "rule": "KEEP/MERGE/RESEARCH_ONLY/ARCHIVE/DELETE——"
                    "不新增一种状态"}


PWC1_ACCEPTANCE_QUESTIONS = (
    "final_target_change_changes_path_hash",
    "wave_material_change_changes_hash",
    "critical_data_missing_cannot_pass",
    "data_trust_no_hardcoded_pass",
    "cross_release_certification_blocked",
    "production_snapshot_release_id_present",
    "ledger_traceable_to_evidence_pack",
    "action_final_target_consistent_in_ledger",
    "unknown_cap_no_forced_exit",
    "formal_stress_no_legacy_target",
    "decision_manifest_not_all_features",
    "legacy_production_authority_zero",
    "report_decision_authority_zero",
    "formal_research_authority_one",
    "production_final_target_authority_one",
)


def pwc1_acceptance_matrix(checks: dict) -> dict:
    """PWC-1 最终验收矩阵：15 问必须全部满足。"""
    results = {q: bool(checks.get(q)) for q in PWC1_ACCEPTANCE_QUESTIONS}
    failures = [q for q, ok in results.items() if not ok]
    return {"results": results,
            "failures": failures,
            "verdict": "PWC1_PASS" if not failures
            else "PWC1_BLOCKED",
            "allowed": not failures,
            "rule": "不要再测试'函数存在'，而是测试'系统能否绕过它'"}
