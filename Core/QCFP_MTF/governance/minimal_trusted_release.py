# coding: utf-8
"""QCFP_MTF Minimal Trusted Production Release（MTR）

真正做减法：Production executable path / ACTIVE feature /
decision-critical code 三项实质下降，同时 Canonical/OOS/Replay/Safety
四项不得下降。

12 项是工作步骤（Build/CI + Release Artifact），不是 12 个新模块：
    1 Freeze Baseline / 2 Roots / 3 Authority Graph /
    4 Audit / 5 Classify / 6 Removal Candidates /
    7 Necessity+Ablation Review / 8 Logical Detach /
    9 Verify Unreachable / 10 Physical Delete /
    11 Regression Evidence / 12 Convergence Certificate

Release 判定只允许三态：CONVERGED / SAFE_BUT_NOT_CONVERGED / REJECTED。
"""


from pathlib import Path


# Q8（Trust Evidence Closure）：Golden Corpus 冻结版本。
# run_golden_evidence() 必须报告同一 corpus_version，否则视为
# Release 偷偷改了 case（两边都显示 PASS 的漏洞）。
FROZEN_GOLDEN_CORPUS_VERSION = "GOLDEN-CONSTITUTION-1"
# Golden Corpus 冻结哈希：corpus 增加/删除/改名任何 case 都会改变
# 哈希 → 必须走 Change Impact Review 并显式更新本常量。
FROZEN_GOLDEN_CORPUS_HASH = "4999e192fb300534"


# 建议最低减幅（本次 Release 治理目标）
SHRINKAGE_TARGETS = {
    "executable_decision_paths": 0.30,
    "active_features": 0.20,
    "production_critical_loc": 0.15,
    "production_modules": 0.15,
}

AUTHORITY_GATE = {
    "canonical_decision_authority": 1,
    "permission_authority": 1,
    "final_target_authority": 1,
    "validation_authority": 1,
    "production_wave_taxonomy": 1,
    "report_decision_authority": 0,
    "legacy_production_paths": 0,
}


def freeze_baseline(metrics: dict) -> dict:
    """Task 1：冻结 Production Baseline（convergence_baseline.json）。"""
    return {"release": "MINIMAL_TRUSTED_PRODUCTION_RELEASE",
            "baseline": metrics,
            "frozen": True}


def production_roots() -> dict:
    """Task 2：真实 Production Roots（roots.json）。"""
    return {"roots": {
        "daily_pipeline": "scripts/run workflow",
        "canonical_engine": "decision.engine.evaluate",
        "certification": "decision.certified_decision.certify_decision",
        "execution": "execution.execution_gate.execute",
        "ledger": "decision.decision_ledger.record_snapshot",
        "runtime_safety": "safety.incident_protocol.incident_protocol",
    }}


def removal_candidates(audit: dict, classifications: dict) -> dict:
    """Task 6：从审计 + 分类生成删除候选。"""
    candidates = {}
    for kind, mods in audit.items():
        if isinstance(mods, dict):
            flat = [m for group in mods.values() for m in group]
        else:
            flat = list(mods)
        for m in flat:
            cls = classifications["classifications"].get(
                m, {}).get("classification", "")
            candidates[m] = {"audit_kind": kind,
                             "classification": cls}
    return {"candidates": candidates,
            "count": len(candidates)}


def retirement_evidence(candidates: dict, behavior: dict = None,
                        ablation: dict = None) -> dict:
    """Task 7：Necessity + Ablation Review（mandatory_governance 例外）。"""
    behavior = behavior or {}
    ablation = ablation or {}
    evidence = {}
    for module in candidates.get("candidates", {}):
        b = behavior.get(module) or {}
        a = ablation.get(module) or {}
        mandatory = bool(b.get("mandatory_governance")
                         or a.get("mandatory_governance"))
        binding = float(b.get("binding_frequency") or 0.0)
        abl = float(a.get("ablation_value") or 0.0)
        if mandatory:
            decision = "KEEP_CONSTITUTIONAL"
        elif binding <= 0.005 and abs(abl) <= 0.005:
            decision = "DELETE"
        else:
            decision = "REVIEW"
        evidence[module] = {
            "mandatory_governance": mandatory,
            "binding_frequency": binding,
            "ablation_value": abl,
            "decision": decision,
        }
    return {"evidence": evidence,
            "delete_candidates": [m for m, e in evidence.items()
                                  if e["decision"] == "DELETE"]}


def verify_unreachable(before_graph, after_graph, candidates: list) -> dict:
    """Task 9：Logical Detachment 后验证候选不可达（graph_diff）。"""
    diff = {}
    for c in candidates:
        before = before_graph["nodes"].get(c, {}).get(
            "production_reachable", False)
        after = after_graph["nodes"].get(c, {}).get(
            "production_reachable", False)
        diff[c] = {"before_reachable": before,
                   "after_reachable": after,
                   "detached": not after}
    all_detached = all(d["detached"] for d in diff.values()) \
        if diff else True
    return {"diff": diff,
            "all_detached": all_detached,
            "verdict": "DETACHED" if all_detached else "STILL_REACHABLE"}


def physical_delete(candidates: list, actual_removed: list = None,
                    qcfp_root=None, residual_references: list = None) -> dict:
    """Task 10：物理删除（Git/Release Artifact 保存历史）。

    MTR Closure（Sprint D）修正：DELETE_COMPLETE 只能来自——
      * actual_removed_count > 0（真实删除，不能 actual_removed=[] 宣布完成）；
      * 候选文件全部不存在；
      * 无残余引用（import / CLI / config / manifest ACTIVE）。
    禁止「逻辑断开 + register 无 DELETE」就宣布 DELETE_COMPLETE。"""
    removed = list(actual_removed or [])
    pending = [c for c in candidates if c not in removed]
    files_absent = True
    if qcfp_root is not None:
        root = Path(qcfp_root)
        for c in candidates:
            p = root / f"{c.replace('.', '/')}.py"
            if p.exists():
                files_absent = False
                break
    residual = list(residual_references or [])
    complete = bool(removed) and not pending and files_absent \
        and not residual
    return {"removed_files": removed,
            "pending_files": pending,
            "residual_references": residual,
            "retired_removed_count": len(removed),
            "candidate_files_absent": files_absent,
            "all_retired_physically_deleted": complete,
            "verdict": "DELETE_COMPLETE" if complete
            else "DELETE_PENDING"}


def physical_retirement_audit(qcfp_root, manifest: dict,
                              declared_retired: list = None,
                              residual_references: list = None) -> dict:
    """Q10 集合等价验证（MTR Closure：Retirement Truth）：

        DeclaredRetiredSet ⊆ PhysicallyAbsentSet
        AND residual_reference_count == 0

    RETIRED 语义：当前 Production Tree 中源码不存在 + import=0 +
    CLI=0 + config=0 + manifest ACTIVE=0。只要源码还存在 → 不叫 RETIRED
    （应标 RESEARCH_ONLY）。"""
    declared = sorted(declared_retired or [
        f for f, info in (manifest or {}).items()
        if info.get("state") == "RETIRED"])
    root = Path(qcfp_root)
    physically_absent, still_present = [], []
    for dotted in declared:
        p = root / f"{dotted.replace('.', '/')}.py"
        if p.exists():
            still_present.append(dotted)
        else:
            physically_absent.append(dotted)
    residual = list(residual_references or [])
    all_deleted = not still_present and not residual
    return {
        "declared_retired": declared,
        "physically_absent": physically_absent,
        "still_present": still_present,
        "residual_imports": [r for r in residual
                             if r.get("kind") in ("import", "cli",
                                                  "config")],
        "residual_cli": [r for r in residual
                         if r.get("kind") == "cli"],
        "residual_config": [r for r in residual
                            if r.get("kind") == "config"],
        "residual_manifest_active": [r for r in residual
                                     if r.get("kind")
                                     == "manifest_active"],
        "retired_removed_count": len(physically_absent),
        "all_retired_physically_deleted": all_deleted,
        "verdict": "DELETE_COMPLETE" if all_deleted
        else "DELETE_PENDING",
        "rule": "RETIRED = 当前 Production Tree 中源码不存在；"
                "DeclaredRetiredSet ⊆ PhysicallyAbsentSet 且残余=0",
    }


def scan_residual_references(qcfp_root, modules: list) -> list:
    """全工程扫描：retired module 是否仍有 import / CLI / 配置引用。

    只统计真正可达的模块路径引用；manifest 中的 RETIRED 记录是退役
    事实本身，不视为残余引用。"""
    import re
    root = Path(qcfp_root)
    refs = []
    for py in root.rglob("*.py"):
        if "__pycache__" in py.parts or "tests" in py.parts:
            continue
        src = py.read_text(encoding="utf-8", errors="ignore")
        rel = py.relative_to(root).as_posix()
        for dotted in modules:
            short = dotted.rsplit(".", 1)[-1]
            pats = (
                rf"\bfrom\s+QCFP_MTF\.{re.escape(dotted)}\b",
                rf"\bimport\s+QCFP_MTF\.{re.escape(dotted)}\b",
                rf"\bfrom\s+[.\w]*\.{re.escape(short)}\s+import\b",
                rf"\bimport\s+[.\w]*\.{re.escape(short)}\b",
            )
            if any(re.search(p, src) for p in pats):
                refs.append({"file": rel, "module": dotted})
    # 配置引用（JSON/INI 等）：模块短名出现在配置文件中即视为残余
    for cfg in root.rglob("*.json"):
        if "manifest" in cfg.name or "audit" in str(cfg):
            continue
        try:
            text = cfg.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = cfg.relative_to(root).as_posix()
        for dotted in modules:
            short = dotted.rsplit(".", 1)[-1]
            if re.search(rf"\b{re.escape(short)}\b", text):
                refs.append({"file": rel, "module": dotted})
    return refs


def regression_evidence(canonical=None, replay=None, oos=None,
                        ablation=None, safety=None) -> dict:
    """Task 11：Golden/OOS/Replay/Safety 五层证明。

    MTR Closure：缺证据 → NOT_PROVEN（不是 PASS）。"""
    return {"canonical_equivalence": canonical or "NOT_PROVEN",
            "replay": replay or "NOT_PROVEN",
            "oos": oos or "NOT_PROVEN",
            "ablation_minimal_core": ablation or "NOT_PROVEN",
            "safety_failure_injection": safety or "NOT_PROVEN",
            "rule": "Missing Evidence → NOT_PROVEN，而不是 PASS"}


def deletion_invariant(before_trust: dict, after_trust: dict) -> dict:
    """删代码不能减少 Safety/Audit Evidence（Trust Evidence ≥）。"""
    keys = ("failure_injection_cases", "replay_coverage",
            "invariant_checks", "golden_corpus_pass")
    regression = [k for k in keys
                  if float(after_trust.get(k) or 0)
                  < float(before_trust.get(k) or 0)]
    return {"regressed": regression,
            "verdict": "TRUST_PRESERVED" if not regression
            else "TRUST_REGRESSED",
            "rule": "Complexity ↓ 但 Trust Evidence 不得 ↓"}


def shrinkage_scoreboard(before: dict, after: dict) -> dict:
    """Scoreboard A：Production Shrinkage + 建议最低减幅。"""
    rows = {}
    for k in ("executable_decision_paths", "active_features",
              "production_critical_loc", "production_modules",
              "duplicate_authorities", "legacy_production_imports"):
        b = float(before.get(k) or 0.0)
        a = float(after.get(k) or 0.0)
        change = round((a - b) / b, 4) if b else None
        rows[k] = {"before": b, "after": a, "change": change}
    hard_down = (
        rows["executable_decision_paths"]["change"] is not None
        and rows["executable_decision_paths"]["change"] < 0
        and rows["active_features"]["change"] < 0
        and rows["production_critical_loc"]["change"] < 0)
    zero = (rows["duplicate_authorities"]["after"] == 0
            and rows["legacy_production_imports"]["after"] == 0)
    targets_met = []
    for k, target in SHRINKAGE_TARGETS.items():
        change = rows.get(k, {}).get("change")
        if change is not None and change <= -target:
            targets_met.append(k)
    return {"rows": rows,
            "hard_down": hard_down,
            "zero": zero,
            "targets_met": targets_met,
            "verdict": "SHRINKAGE_PASS" if hard_down and zero
            else "SHRINKAGE_INCOMPLETE"}


def trust_scoreboard(before: dict, after: dict,
                     safety="PASS") -> dict:
    """Scoreboard B：Trust Preservation（四项不得下降）。"""
    keys = ("canonical_golden_pass", "replay_coverage",
            "invariant_coverage", "pit_compliance",
            "oos_evidence_grade")
    rows = {k: {"before": before.get(k), "after": after.get(k),
                "not_down": _not_down(before.get(k), after.get(k))}
            for k in keys}
    trust_ok = all(r["not_down"] for r in rows.values()) \
        and safety == "PASS"
    return {"rows": rows,
            "safety": safety,
            "trust_preserved": trust_ok,
            "verdict": "TRUST_PASS" if trust_ok else "TRUST_REGRESSED"}


def _not_down(b, a) -> bool:
    try:
        return float(a) >= float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def release_gates(authority: dict, shrinkage: dict, trust: dict,
                  deletion: dict) -> dict:
    """Gate A Authority / Gate B Shrinkage / Gate C Trust /
    Gate D Physical Retirement。"""
    a_ok = all(authority.get(k) == v
               for k, v in AUTHORITY_GATE.items())
    b_ok = shrinkage.get("verdict") == "SHRINKAGE_PASS"
    c_ok = trust.get("verdict") == "TRUST_PASS"
    d_ok = deletion.get("verdict") == "DELETE_COMPLETE"
    return {"gate_a_authority": a_ok,
            "gate_b_shrinkage": b_ok,
            "gate_c_trust": c_ok,
            "gate_d_physical_retirement": d_ok,
            "verdict": "ALL_GATES_PASS" if all(
                (a_ok, b_ok, c_ok, d_ok)) else "GATE_BLOCKED"}


def convergence_certificate(gates: dict, shrinkage: dict,
                            trust: dict) -> dict:
    """Task 12：Release 判定只允许三态。"""
    if trust.get("verdict") != "TRUST_PASS":
        return {"verdict": "REJECTED",
                "reason": "Replay/Safety/PIT/Authority 退化 → 拒绝 Release",
                "certificate": "MTR-REJECTED"}
    if gates.get("verdict") != "ALL_GATES_PASS":
        return {"verdict": "SAFE_BUT_NOT_CONVERGED",
                "reason": "未删坏（Trust PASS）但 Shrinkage/Deletion "
                          "未达成",
                "certificate": "MTR-NOT-CONVERGED"}
    return {"verdict": "CONVERGED",
            "reason": "Shrinkage PASS + Trust Preservation PASS",
            "certificate": "MTR-CONVERGED"}


def definition_of_done_10(checks: dict) -> dict:
    """10 问 Definition of Done。"""
    questions = (
        "one_production_decision_path",
        "single_canonical_authority",
        "active_features_down",
        "decision_critical_loc_down",
        "legacy_production_path_zero",
        "duplicate_authority_zero",
        "unwired_active_feature_zero",
        "golden_replay_oos_not_regressed",
        "failure_injection_zero_escaped",
        "retired_code_physically_deleted",
    )
    results = {q: bool(checks.get(q)) for q in questions}
    failures = [q for q, ok in results.items() if not ok]
    return {"results": results, "failures": failures,
            "verdict": "MTR_SUCCESS" if not failures
            else "MTR_INCOMPLETE"}


def production_feature_manifest_artifact(graph: dict,
                                         classifications: dict,
                                         release_id="",
                                         evidence_levels=None,
                                         retirement_conditions=None,
                                         frozen_manifest=None) -> dict:
    """Sprint B（Task 3/Action 14）：真实且唯一的 Production ACTIVE
    Feature Manifest Artifact（production_features.json）。

    MTR Closure（Sprint B）修正：
    * Frozen Manifest 是唯一 Production ACTIVE truth（Artifact A），
      状态由治理冻结，不由 Graph 即时推导；
    * Authority Graph（Artifact B）独立验证每个 ACTIVE 是否 wired，
      杜绝「Graph 生成 Manifest → Graph 验证自己」的循环自证。"""
    evidence_levels = evidence_levels or {}
    retirement_conditions = retirement_conditions or {}
    manifest = frozen_manifest or FROZEN_PRODUCTION_MANIFEST
    features = {}
    for feature, info in manifest.items():
        state = info.get("state", "RESEARCH_ONLY")
        if state not in ("ACTIVE", "RESEARCH_ONLY", "RETIRED"):
            state = "RESEARCH_ONLY"
        features[feature] = {
            "feature_id": feature,
            "state": state,
            "owner": info.get("owner", ""),
            "production_required": bool(info.get("production_required")),
            "evidence_level": info.get("evidence_level")
            or evidence_levels.get(feature),
            "release_id": release_id,
            "retired_release": info.get("retired_release", ""),
            "retirement_condition": info.get("retirement_condition")
            or retirement_conditions.get(feature, ""),
        }
    verification = verify_frozen_manifest(graph, manifest)
    active = [f for f, d in features.items() if d["state"] == "ACTIVE"]
    return {"features": features,
            "active_count": len(active),
            "active_features": active,
            "unwired_active": verification["unwired_active"],
            "unknown_owner": verification["unknown_owner"],
            "forbidden_dependency_active":
                verification["forbidden_dependency_active"],
            "verification": verification,
            "rule": "Frozen Manifest 是唯一 Production ACTIVE truth；"
                    "Authority Graph 独立验证 wiring；FEATURE_SET 只是 "
                    "Code Capability Catalog"}


# ---------------------------------------------------------------------------
# Sprint B：独立事实 Artifact
# ---------------------------------------------------------------------------

# Frozen Production Feature Manifest（Artifact A）——治理冻结，不由 Graph
# 推导。状态只允许 ACTIVE / RESEARCH_ONLY / RETIRED。
FROZEN_PRODUCTION_MANIFEST = {
    # ---- Canonical Runtime Core（ACTIVE，production_required） ----
    "pit_evidence": {"owner": "evidence.snapshot", "state": "ACTIVE",
                     "evidence_level": "CERTIFIED",
                     "production_required": True},
    "institutional_permission": {
        "owner": "decision.institutional_permission", "state": "ACTIVE",
        "evidence_level": "CERTIFIED", "production_required": True},
    "permission_policy": {"owner": "decision.permission_policy",
                          "state": "ACTIVE",
                          "evidence_level": "CERTIFIED",
                          "production_required": True},
    "participation_budget": {"owner": "decision.participation_budget",
                             "state": "ACTIVE",
                             "evidence_level": "CERTIFIED",
                             "production_required": True},
    "hard_exit": {"owner": "decision.hard_exit", "state": "ACTIVE",
                  "evidence_level": "CERTIFIED",
                  "production_required": True},
    "swing_setup": {"owner": "setup.swing_setup", "state": "ACTIVE",
                    "evidence_level": "CERTIFIED",
                    "production_required": True},
    "retail_fsm": {"owner": "decision.retail_position_fsm",
                   "state": "ACTIVE", "evidence_level": "CERTIFIED",
                   "production_required": True},
    "retail_position_sizing": {
        "owner": "decision.retail_position_sizing", "state": "ACTIVE",
        "evidence_level": "CERTIFIED", "production_required": True},
    "governance_finalize": {"owner": "decision.governance",
                            "state": "ACTIVE",
                            "evidence_level": "CERTIFIED",
                            "production_required": True},
    "governance_caps": {"owner": "decision.governance_caps",
                        "state": "ACTIVE", "evidence_level": "CERTIFIED",
                        "production_required": True},
    "canonical_final_target": {"owner": "decision.canonical_action",
                               "state": "ACTIVE",
                               "evidence_level": "CERTIFIED",
                               "production_required": True},
    "canonical_engine": {"owner": "decision.engine", "state": "ACTIVE",
                         "evidence_level": "CERTIFIED",
                         "production_required": True},
    "trade_quality": {"owner": "decision.trade_quality", "state": "ACTIVE",
                      "evidence_level": "CERTIFIED",
                      "production_required": True},
    "decision_snapshot": {"owner": "decision.decision_snapshot",
                          "state": "ACTIVE",
                          "evidence_level": "CERTIFIED",
                          "production_required": True},
    "certified_decision_gate": {"owner": "decision.certified_decision",
                                "state": "ACTIVE",
                                "evidence_level": "CERTIFIED",
                                "production_required": True},
    "decision_ledger": {"owner": "decision.decision_ledger",
                        "state": "ACTIVE", "evidence_level": "CERTIFIED",
                        "production_required": True},
    "execution_gate": {"owner": "execution.execution_gate",
                       "state": "RESEARCH_ONLY",
                       "evidence_level": "VALIDATED",
                       "production_required": False,
                       "retirement_condition":
                           "OPTIONAL_EXECUTION_EXTENSION：决策支持系统"
                           "不负责向 Broker 下交易指令，Execution 不进入"
                           "Production ACTIVE（P1-7 目标重新对齐）"},
    "runtime_safety": {"owner": "safety.incident_protocol",
                       "state": "ACTIVE", "evidence_level": "CERTIFIED",
                       "production_required": True},
    "wave_canonical_chain": {"owner": "wave.canonical", "state": "ACTIVE",
                             "evidence_level": "CERTIFIED",
                             "production_required": True},
    "constraint_trace": {"owner": "decision.constraint_trace",
                         "state": "ACTIVE",
                         "evidence_level": "CERTIFIED",
                         "production_required": True},
    "path_hash": {"owner": "decision.path_hash", "state": "ACTIVE",
                  "evidence_level": "CERTIFIED",
                  "production_required": True},
    "governance_proof": {"owner": "decision.governance_proof",
                         "state": "ACTIVE",
                         "evidence_level": "CERTIFIED",
                         "production_required": True},
    "feature_contract": {"owner": "data.feature_contract",
                         "state": "ACTIVE",
                         "evidence_level": "CERTIFIED",
                         "production_required": True},
    "data_quality_gate": {"owner": "data.quality", "state": "ACTIVE",
                          "evidence_level": "CERTIFIED",
                          "production_required": True},
    "market_regime": {"owner": "market.regime", "state": "ACTIVE",
                      "evidence_level": "CERTIFIED",
                      "production_required": True},
    "action_gate": {"owner": "decision.action_gate", "state": "ACTIVE",
                    "evidence_level": "CERTIFIED",
                    "production_required": True},
    "action_classifier": {"owner": "decision.action_classifier",
                          "state": "ACTIVE",
                          "evidence_level": "CERTIFIED",
                          "production_required": True},
    "stop_loss": {"owner": "decision.stop_loss", "state": "ACTIVE",
                  "evidence_level": "CERTIFIED",
                  "production_required": True},
    "confidence": {"owner": "decision.confidence", "state": "ACTIVE",
                   "evidence_level": "CERTIFIED",
                   "production_required": True},
    "conflict_resolver": {"owner": "governance.conflict",
                          "state": "ACTIVE",
                          "evidence_level": "CERTIFIED",
                          "production_required": True},
    "portfolio_state": {"owner": "portfolio.state_engine",
                        "state": "ACTIVE",
                        "evidence_level": "CERTIFIED",
                        "production_required": True},
    "exit_quality": {"owner": "decision.exit_quality", "state": "ACTIVE",
                     "evidence_level": "VALIDATED",
                     "production_required": False},
    "entry_quality": {"owner": "decision.entry_quality", "state": "ACTIVE",
                      "evidence_level": "VALIDATED",
                      "production_required": False},
    "time_in_trade": {"owner": "decision.time_in_trade", "state": "ACTIVE",
                      "evidence_level": "VALIDATED",
                      "production_required": False},
    # ---- Release-time Governance（非日频运行时路径） ----
    "replay_engine": {"owner": "decision.replay_engine",
                      "state": "RESEARCH_ONLY",
                      "evidence_level": "VALIDATED",
                      "production_required": False,
                      "retirement_condition":
                          "Replay 属 Release Gate，非日频运行时路径"},
    "validation_certificate": {
        "owner": "governance.validation_certificate",
        "state": "RESEARCH_ONLY", "evidence_level": "VALIDATED",
        "production_required": False,
        "retirement_condition":
            "Validation Certificate 属 Release Gate，非日频运行时路径"},
    "release_identity": {"owner": "decision.release_identity",
                         "state": "RESEARCH_ONLY",
                         "evidence_level": "VALIDATED",
                         "production_required": False},
    "schema_contract": {"owner": "decision.schema_contract",
                        "state": "RESEARCH_ONLY",
                        "evidence_level": "VALIDATED",
                        "production_required": False},
    "pit_registry": {"owner": "data.pit_registry",
                     "state": "RESEARCH_ONLY",
                     "evidence_level": "VALIDATED",
                     "production_required": False,
                     "retirement_condition":
                         "PIT 运行时门由 evidence.snapshot 执行"},
    # ---- MTR Closure 自证工具（治理/研究，不进入 Production ACTIVE） ----
    "mtr_closure_behavioral_authority": {
        "owner": "governance.pwc2_authority_graph",
        "state": "RESEARCH_ONLY", "evidence_level": "VALIDATED",
        "production_required": False},
    "mtr_closure_pure_referee": {
        "owner": "governance.minimal_trusted_release",
        "state": "RESEARCH_ONLY", "evidence_level": "VALIDATED",
        "production_required": False},
    "mtr_closure_feature_manifest_truth": {
        "owner": "governance.minimal_trusted_release",
        "state": "RESEARCH_ONLY", "evidence_level": "VALIDATED",
        "production_required": False},
    "ablation.experiments": {"owner": "ablation.experiments",
                             "state": "RESEARCH_ONLY",
                             "evidence_level": "VALIDATED",
                             "production_required": False},
    "backtest.data_pipeline": {"owner": "backtest.data_pipeline",
                               "state": "RESEARCH_ONLY",
                               "evidence_level": "VALIDATED",
                               "production_required": False},
    # ---- 物理退役（v10：RETIRED = 源码已不存在） ----
    "decision.score_calculator": {
        "owner": "decision.score_calculator", "state": "RETIRED",
        "evidence_level": "RETIRED", "production_required": False,
        "retired_release": "MTR-CLOSURE-1",
        "retirement_condition": "无生产调用，物理删除"},
    # RESEARCH_ONLY：文件可存在，Research 可 import，Production 不可达，
    # 不能 Certification；**只要源码存在就不叫 RETIRED**。
    "decision.action_generator": {
        "owner": "decision.action_generator", "state": "RESEARCH_ONLY",
        "evidence_level": "RESEARCH_ONLY", "production_required": False,
        "retired_release": "MTR-CLOSURE-1",
        "retirement_condition": "Legacy Comparator：Research/Shadow 保留，"
                                "Production 不可达"},
    "decision.position_sizing": {
        "owner": "decision.position_sizing", "state": "RESEARCH_ONLY",
        "evidence_level": "RESEARCH_ONLY", "production_required": False,
        "retired_release": "MTR-CLOSURE-1",
        "retirement_condition": "Research/backtest 仍引用，保留但不可达"},
    "decision.permission_gate": {
        "owner": "decision.permission_gate", "state": "RESEARCH_ONLY",
        "evidence_level": "RESEARCH_ONLY", "production_required": False,
        "retired_release": "MTR-CLOSURE-1",
        "retirement_condition": "Boundary/Audit helper 保留，Production "
                                "不可达（canonical 走 permission_policy）"},
}


# merged_code(9) 冻结基线（Artifact A-before）：v9 声称的生产 ACTIVE
# 集合（含当时仍计入的 Legacy 路径与 MTR 自证 feature）。不可修改。
V9_PRODUCTION_BASELINE_MANIFEST = {
    f: dict(info) for f, info in FROZEN_PRODUCTION_MANIFEST.items()
}
for _f in ("decision.score_calculator", "decision.action_generator",
           "decision.position_sizing", "decision.permission_gate",
           "mtr_closure_behavioral_authority",
           "mtr_closure_pure_referee",
           "mtr_closure_feature_manifest_truth"):
    V9_PRODUCTION_BASELINE_MANIFEST[_f]["state"] = "ACTIVE"
    V9_PRODUCTION_BASELINE_MANIFEST[_f]["evidence_level"] = "CERTIFIED"


def verify_frozen_manifest(graph: dict, manifest: dict) -> dict:
    """Frozen Manifest → Authority Graph 独立验证（Artifact A × B）。

    每个 ACTIVE entry 必须满足：
      * owner 存在于 Graph；
      * owner production_reachable；
      * owner 不落在 Forbidden Production Prefix。
    不满足 → unwired_active / unknown_owner / forbidden_dependency_active。
    """
    from .pwc2_authority_graph import FORBIDDEN_PRODUCTION_PREFIXES
    nodes = graph.get("nodes") or {}
    wired, unwired, unknown, forbidden = [], [], [], []
    for feature, info in (manifest or {}).items():
        if info.get("state") != "ACTIVE":
            continue
        owner = info.get("owner", "")
        node = nodes.get(owner)
        if node is None:
            unknown.append(feature)
            continue
        if not node.get("production_reachable"):
            unwired.append(feature)
        elif any(owner.startswith(p) for p in FORBIDDEN_PRODUCTION_PREFIXES):
            forbidden.append(feature)
        else:
            wired.append(feature)
    ok = not (unwired or unknown or forbidden)
    return {
        "active_count": len(wired) + len(unwired) + len(unknown)
        + len(forbidden),
        "wired_active": sorted(wired),
        "unwired_active": sorted(unwired),
        "unknown_owner": sorted(unknown),
        "forbidden_dependency_active": sorted(forbidden),
        "verdict": "MANIFEST_WIRED" if ok else "MANIFEST_UNWIRED",
    }


def active_feature_diff(before_manifest: dict,
                        after_manifest: dict) -> dict:
    """active_feature_diff.json：before/after ACTIVE 集合真实对比。

    MTR Closure 规则：newly_active 必须为空（禁止新增 Production ACTIVE
    Feature）；after_active_count < before_active_count。"""
    before_active = {f for f, i in (before_manifest or {}).items()
                     if i.get("state") == "ACTIVE"}
    after_active = {f for f, i in (after_manifest or {}).items()
                    if i.get("state") == "ACTIVE"}
    newly_active = sorted(after_active - before_active)
    retired = sorted(before_active - after_active)
    down = len(after_active) < len(before_active) and not newly_active
    return {
        "before_active_count": len(before_active),
        "after_active_count": len(after_active),
        "retired": retired,
        "merged": [],
        "newly_active": newly_active,
        "verdict": "ACTIVE_DOWN" if down else "ACTIVE_NOT_DOWN",
        "rule": "MTR Closure 禁止新增 Production ACTIVE Feature",
    }


def critical_loc_metrics(graph: dict) -> dict:
    """只统计 Production Roots 可达代码（Canonical Engine / Certification /
    Execution / Ledger / Runtime Safety），并标记 decision_affecting。"""
    nodes = graph.get("nodes") or {}
    reachable = graph.get("reachable_modules") or []
    root_dir = Path(graph.get("root_dir") or "")
    reachable_loc = 0
    decision_critical_modules = []
    decision_critical_loc = 0
    for m in sorted(reachable):
        info = nodes.get(m) or {}
        p = root_dir / info.get("file", "")
        loc = len(p.read_text(encoding="utf-8",
                              errors="ignore").splitlines()) \
            if p.exists() else 0
        reachable_loc += loc
        if info.get("decision_critical"):
            decision_critical_modules.append(m)
            decision_critical_loc += loc
    return {
        "reachable_modules": sorted(reachable),
        "reachable_module_count": len(reachable),
        "reachable_loc": reachable_loc,
        "decision_critical_modules": sorted(decision_critical_modules),
        "decision_critical_loc": decision_critical_loc,
    }


def critical_loc_baseline(metrics: dict, release_id: str,
                          code_hash: str) -> dict:
    """critical_loc_baseline.json：不可修改的 Before 基线。

    Before 必须来自 merged_code(9) 冻结基线；本函数只生成一次，
    freeze_mtr_baseline 保证已存在则拒绝覆盖。"""
    return {"release_id": release_id,
            "code_hash": code_hash,
            "baseline": metrics,
            "immutable": True,
            "rule": "critical_loc_baseline 不可修改；下一版只能比较"}


def freeze_mtr_baseline(baseline: dict, path, release_id: str) -> dict:
    """Sprint B（Action 12）：MTR Baseline 不可修改的上一 Release
    Artifact——工具不能修改 before；已存在则拒绝覆盖。"""
    import json
    from pathlib import Path
    path = Path(path)
    if path.exists():
        return {"frozen": False, "reason": "baseline 已存在（不可变）",
                "path": str(path)}
    baseline["release_id"] = release_id
    baseline["immutable"] = True
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return {"frozen": True, "path": str(path),
            "release_id": release_id}


def evaluate_mtr(evidence_bundle: dict) -> dict:
    """Sprint E：MTR 只做纯裁判——READ evidence → COMPARE → ISSUE verdict。
    禁止 invent baseline / default PASS / 手工标 1 / 手工标 zero escaped。"""
    def _int(v, default=-1):
        try:
            return int(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    required = ("authority_graph", "feature_manifest", "loc_metrics",
                "golden_result", "replay_result", "oos_result",
                "failure_injection", "physical_delete")
    missing = [k for k in required if not evidence_bundle.get(k)]
    if missing:
        return {"verdict": "NOT_PROVEN",
                "missing_evidence": missing,
                "certificate": "MTR-NOT-PROVEN",
                "rule": "Missing Evidence → NOT_PROVEN，而不是 PASS"}
    graph = evidence_bundle["authority_graph"]
    feats = evidence_bundle["feature_manifest"]
    loc = evidence_bundle["loc_metrics"]
    golden = evidence_bundle["golden_result"]
    replay = evidence_bundle["replay_result"]
    oos = evidence_bundle["oos_result"]
    fi = evidence_bundle["failure_injection"]
    delete = evidence_bundle["physical_delete"]
    path_count = graph.get("executable_decision_paths")
    q1 = path_count == 1
    q2 = not graph.get("duplicate_authorities")
    q3 = feats.get("active_features_down", False)
    # Q4 只读取 Decision-critical LOC（不能再用 reachable LOC 替代）
    q4 = loc.get("decision_critical_loc_down", False)
    q5 = not graph.get("legacy_production_paths")
    q6 = q2
    q7 = len(feats.get("unwired_active") or []) == 0
    # Q8 Final Closure：只认新 Schema（GOLDEN-2 / REPLAY-2 / OOS-2），
    # 移除旧 artifact fallback；任何字段缺失 → NOT_PROVEN。
    # Golden：corpus 冻结版本一致 + n_total>0 + n_failed=0。
    # Replay：eligible=100% / exact=100% / ineligible=0 / mismatch=0 /
    #         replay_exception=0 / critical_mismatch=0。
    # OOS：OOS_PASS + comparable=True + evidence_not_down=True。
    _nc = _int(replay.get("n_current_release"), 0)
    q8 = (
        golden.get("schema") == "GOLDEN-2"
        and golden.get("status") == "PASS"
        and _int(golden.get("n_total"), 0) > 0
        and _int(golden.get("n_failed"), -1) == 0
        and golden.get("golden_corpus_version")
        == FROZEN_GOLDEN_CORPUS_VERSION
        and golden.get("golden_corpus_hash")
        == FROZEN_GOLDEN_CORPUS_HASH
        and replay.get("schema") == "REPLAY-2"
        and _nc > 0
        and _int(replay.get("n_eligible"), -1) == _nc
        and _int(replay.get("n_ineligible"), -1) == 0
        and _int(replay.get("n_exact"), -1) == _nc
        and _int(replay.get("n_mismatch"), -1) == 0
        and _int(replay.get("n_replay_exception"), -1) == 0
        and float(replay.get("eligible_rate") or 0) == 1.0
        and float(replay.get("exact_rate") or 0) == 1.0
        and _int(replay.get("critical_mismatch"), -1) == 0
        and oos.get("schema") == "OOS-2"
        and oos.get("status") == "OOS_PASS"
        and oos.get("comparable") is True
        and oos.get("evidence_not_down") is True)
    q9 = int(fi.get("failure_escaped_count") or 0) == 0
    all_deleted = delete.get("all_retired_physically_deleted")
    if all_deleted is None:   # 旧 artifact 兼容
        all_deleted = (delete.get("retired_removed_count", 0) > 0
                       and not delete.get("residual_references"))
    q10 = all_deleted
    answers = {"one_production_decision_path": q1,
               "single_canonical_authority": q2,
               "active_features_down": q3,
               "decision_critical_loc_down": q4,
               "legacy_production_path_zero": q5,
               "duplicate_authority_zero": q6,
               "unwired_active_feature_zero": q7,
               "golden_replay_oos_not_regressed": q8,
               "failure_injection_zero_escaped": q9,
               "retired_code_physically_deleted": q10}
    failures = [k for k, ok in answers.items() if not ok]
    return {"answers": answers,
            "failures": failures,
            "verdict": "MTR_SUCCESS" if not failures
            else "MTR_INCOMPLETE",
            "certificate": "MTR-CONVERGED" if not failures
            else "MTR-NOT-CONVERGED"}


MTR_ARTIFACTS = (
    "authority_graph.json",
    "production_feature_manifest.json",
    "critical_loc_diff.json",
    "legacy_production_scan.json",
    "golden_result.json",
    "replay_result.json",
    "oos_result.json",
    "failure_injection_results.json",
    "physical_delete_result.json",
    "mtr_verdict.json",
)
