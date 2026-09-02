# coding: utf-8
"""PWC-2 Production Authority Graph + Physical Retirement

本模块是 Build/CI 工具 + Release Artifact，不是运行期子系统：
    Phase 0  冻结 Convergence Baseline
    Phase 1  从真实 entry points 自动建立 Production Authority Graph
    Phase 2  Authority / Path Audit（五类危险节点）
    Phase 3  Retirement Classification
    Phase 4  Logical Detachment 验证
    Phase 6  五层回归 Gate
    Phase 7  Convergence Acceptance（Before/After + 三降硬门）

最终只生成 5 个 Release Artifact：
    authority_graph / retirement_register / convergence_before_after /
    regression_evidence / production_manifest
"""

import json
import re
from pathlib import Path


# --- Phase 1：Production Roots（真实入口） ---
# 目标重新对齐（决策支持）：QCFP_MTF 不负责向 Broker 下交易指令，
# execution_gate（Broker/Order dispatch）不再是 Production Root；
# Broker/Small-Live 降级为 OPTIONAL_EXECUTION_EXTENSION。
PRODUCTION_ROOTS = {
    "canonical_decision": "QCFP_MTF.decision.engine.evaluate",
    "certification": "QCFP_MTF.decision.certified_decision.certify_decision",
    "ledger_commit": "QCFP_MTF.decision.decision_ledger.record_snapshot",
    "runtime_safety": "QCFP_MTF.safety.incident_protocol.incident_protocol",
}

# 生产域只包含 Canonical Engine / Certification / Ledger /
# Runtime Safety。Backtest/Research/Ablation 一律不是 Production Root，
# 避免研究代码污染 Authority Graph（MTR Closure：Sprint A）。
PRODUCTION_ROOT_SCOPE = (
    "canonical_decision", "certification",
    "ledger_commit", "runtime_safety",
)

# Authority 类型（区别于普通 dependency）
AUTHORITY_TYPES = ("NONE", "INPUT", "RISK_UPPER_BOUND",
                   "OPPORTUNITY_PROPOSAL", "LIFECYCLE_PROPOSAL",
                   "CAP", "FINAL_TARGET", "EXECUTION_ELIGIBILITY",
                   "FACT", "FORMAL_RESEARCH_STATUS", "CAP_SUPPORT")

# Canonical Stage 映射（ACTIVE_CORE 只能映射到这些）
CANONICAL_STAGES = {
    "INPUT": ("evidence", "pit"),
    "PERMISSION": ("institutional", "permission"),
    "OPPORTUNITY": ("wave",),
    "LIFECYCLE": ("fsm",),
    "GOVERNANCE": ("governance", "risk", "portfolio", "liquidity",
                   "execution", "caps"),
    "OUTPUT": ("decision", "snapshot", "certified"),
    "FACT": ("ledger",),
    "VALIDATION": ("validation", "replay", "certificate"),
}

# 静态 Authority Registry（工具用，非运行期 Authority）
STATIC_AUTHORITY = {
    "decision.governance": "FINAL_TARGET",
    "decision.institutional_permission": "RISK_UPPER_BOUND",
    "wave.canonical": "OPPORTUNITY_PROPOSAL",
    "decision.retail_position_fsm": "LIFECYCLE_PROPOSAL",
    # Q4（Complexity Closure）：governance_caps 是不可变数据结构 +
    # validation helper，不是独立决策 Authority——FINAL_TARGET 的唯一
    # Owner 是 decision.governance；caps 只是被它消费的输入。
    "decision.governance_caps": "CAP_SUPPORT",
    "decision.certified_decision": "EXECUTION_ELIGIBILITY",
    "decision.decision_ledger": "FACT",
    "governance.validation_certificate": "FORMAL_RESEARCH_STATUS",
}

EDGE_TYPES = ("IMPORTS", "CALLS", "READS", "WRITES", "DERIVES",
              "CAPS", "CERTIFIES", "EXECUTES", "PERSISTS", "REPORTS")

FORBIDDEN_PRODUCTION_PREFIXES = (
    "research.", "ablation.", "wave.outcome", "future_label.",
    "legacy.", "report.")


def _module_dotted(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    return ".".join(rel.parts)


def scan_imports(source: str, current_module: str = "") -> list:
    """静态扫描 import 语句（含 from/import 与相对导入），
    相对导入按当前模块所在包解析。"""
    edges = []
    pkg = current_module.rsplit(".", 1)[0] if "." in current_module \
        else current_module
    for m in re.finditer(r"^\s*from\s+([.\w]+)\s+import\s+",
                         source, re.M):
        target = m.group(1)
        edges.append(("from", _resolve_import(pkg, target)))
    for m in re.finditer(r"^\s*import\s+([\w.]+)", source, re.M):
        edges.append(("import", _resolve_import(pkg, m.group(1))))
    return edges


def _resolve_import(pkg: str, target: str) -> str:
    if target.startswith("QCFP_MTF"):
        return target[len("QCFP_MTF."):]
    if target.startswith("."):
        up = len(target) - len(target.lstrip("."))
        base = pkg
        parts = base.split(".") if base else []
        if up > 0:
            parts = parts[:max(0, len(parts) - (up - 1))]
        rest = target[up:]
        return ".".join(parts + [rest]) if rest else ".".join(parts)
    if target.startswith("QCFP_"):
        return target
    return target


def build_authority_graph(root_dir, roots=None) -> dict:
    """Phase 1：从真实 roots 建立 Production Authority Graph。"""
    root_dir = Path(root_dir)
    roots = roots or PRODUCTION_ROOTS
    nodes, edges = {}, []
    for py in root_dir.rglob("*.py"):
        if "__init__" in py.name or "tests" in py.parts:
            continue
        dotted = _module_dotted(py, root_dir)
        source = py.read_text(encoding="utf-8", errors="ignore")
        authority = STATIC_AUTHORITY.get(dotted, "NONE")
        stage = _classify_stage(dotted, authority)
        nodes[dotted] = {
            "module": dotted,
            "file": str(py.relative_to(root_dir)),
            "authority": authority,
            "canonical_stage": stage,
            "production_reachable": dotted in roots.values() or
            any(r.split(".")[0] in dotted for r in roots.values()),
            "incoming_edges": [],
            "outgoing_edges": [],
            "decision_critical": authority not in ("NONE", "CAP_SUPPORT"),
        }
        for kind, target in scan_imports(source, dotted):
            edges.append({"source": dotted, "target": target,
                          "type": "IMPORTS"})
    # 反向可达性：从真实 roots 出发沿 IMPORTS 传递
    root_modules = {r[len("QCFP_MTF."):].rsplit(".", 1)[0]
                    for r in roots.values()}
    for e in edges:
        if e["source"] in nodes and e["target"] in nodes:
            nodes[e["source"]]["outgoing_edges"].append(e["target"])
            nodes[e["target"]]["incoming_edges"].append(e["source"])
    # 传递可达：BFS from roots
    reachable = set()
    queue = [m for m in nodes if m in root_modules or
             any(r.split(".")[0] == m for r in roots.values())]
    while queue:
        cur = queue.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        queue.extend(nodes[cur]["outgoing_edges"])
    for m, node in nodes.items():
        node["production_reachable"] = m in reachable
    return {"nodes": nodes, "edges": edges,
            "root_dir": str(root_dir),
            "roots": roots, "reachable_modules": sorted(reachable)}


def _classify_stage(dotted: str, authority: str) -> str:
    if authority == "NONE":
        return ""
    for stage, keys in CANONICAL_STAGES.items():
        if any(k in dotted for k in keys):
            return stage
    return ""


# MTR Closure（Action 13）：行为级写检测——谁真正写最终事实
DECISION_FIELDS = ("permission", "wave_stage", "fsm_state", "target",
                   "final_target", "action", "final_action", "position",
                   "certified", "validation_status")

# 字段级 Owner Contract（Sprint A）：每个最终事实只能由一个 Production
# owner 写入；其它 Production 模块写入同一字段 → UNAUTHORIZED_WRITER。
OWNER_CONTRACT = {
    "permission": "decision.institutional_permission",
    "wave_stage": "wave.canonical",
    "fsm_state": "decision.retail_position_fsm",
    "target": "decision.retail_position_sizing",
    "final_target": "decision.governance",
    "action": "decision.action_gate",
    "final_action": "decision.canonical_action",
    "position": "decision.governance",
    "certified": "decision.certified_decision",
    "validation_status": "governance.validation_certificate",
}

# 决策函数调用 → 其最终事实字段（evaluate 是唯一 Canonical 链，不计入）
CALL_FIELD_MAP = {
    "finalize_target": "final_target",
    "generate_action": "action",
    "effective_position_cqs": "position",
}


def behavioral_write_scan(source: str) -> list:
    """AST 级静态扫描：字段赋值 / SQL UPDATE·INSERT / 决策写函数调用。"""
    writes = []
    for m in re.finditer(
            r"(?:^\s*|\b)(?:df\[[\"']?(\w+)[\"']?\]|(\w+)\.(\w+)"
            r")\s*=(?!=)\s*", source, re.M):
        field = m.group(1) or m.group(3)
        if field in DECISION_FIELDS:
            writes.append(("ASSIGN", field))
    for m in re.finditer(
            r"\b(UPDATE|INSERT\s+INTO)\s+[\w_.]+"
            r"(?:\s+SET\s+([\w_,\s=]+))?", source, re.I):
        cols = m.group(2) or ""
        for f in DECISION_FIELDS:
            if f in cols:
                writes.append(("SQL", f))
    for fn, field in CALL_FIELD_MAP.items():
        if re.search(rf"\b{fn}\s*\(", source):
            writes.append(("CALLS", field))
    return writes


def behavioral_authority_audit(graph: dict) -> dict:
    """Task 6：行为级重复权威——两个平行路径都能写同一最终字段 → FAIL。

    MTR Closure（Sprint A）修复：
      * 只统计 production_reachable 模块（Research/Ablation 不得计为
        Production Authority）；
      * 同一模块内的 ASSIGN/SQL/CALLS 只计 1 个 owner（set(module)）；
      * 对每个字段执行 Owner Contract：非 Owner 写入 →
        UNAUTHORIZED_WRITER（比仅查 duplicate 更强）。"""
    field_writers = {f: set() for f in DECISION_FIELDS}
    nodes = graph["nodes"]
    root = graph.get("root_dir")
    for module, info in nodes.items():
        if not info["production_reachable"]:
            continue
        # 用节点文件路径读源码（避免运行时依赖 CORE_DIR）
        file_path = Path(root) / info.get("file", "") if root else None
        if file_path is None or not file_path.exists():
            continue
        try:
            src = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for kind, field in behavioral_write_scan(src):
            if field in DECISION_FIELDS:
                if kind == "CALLS":
                    # 调用 Owner 函数 = 委托给字段 Owner，不构成独立权威
                    field_writers[field].add(OWNER_CONTRACT.get(field)
                                             or module)
                else:
                    field_writers[field].add(module)
    duplicates = {}
    unauthorized = {}
    for field, writers in field_writers.items():
        if len(writers) > 1:
            duplicates[f"duplicate_{field}_authority"] = sorted(writers)
        owner = OWNER_CONTRACT.get(field)
        if owner and writers - {owner}:
            unauthorized[f"unauthorized_{field}_writer"] = \
                sorted(writers - {owner})
    if duplicates:
        verdict = "BEHAVIORAL_DUPLICATE_AUTHORITY"
    elif unauthorized:
        verdict = "BEHAVIORAL_UNAUTHORIZED_WRITER"
    else:
        verdict = "BEHAVIORAL_AUTHORITY_OK"
    return {"field_writers": {f: sorted(ws)
                              for f, ws in field_writers.items()},
            "duplicates": duplicates,
            "duplicate_count": len(duplicates),
            "unauthorized_writers": unauthorized,
            "unauthorized_count": len(unauthorized),
            "owner_contract": dict(OWNER_CONTRACT),
            "verdict": verdict}


def authority_audit(graph: dict) -> dict:
    """Phase 2：五类危险节点。"""
    nodes = graph["nodes"]
    # Duplicate Authority：同 Authority 且彼此互不可达（真正平行权威，
    # 同一链上的 governance→engine→canonical_action 不算重复）
    def _reachable_set(start):
        seen, queue = set(), [start]
        while queue:
            cur = queue.pop()
            if cur in seen:
                continue
            seen.add(cur)
            queue.extend(nodes[cur]["outgoing_edges"])
        return seen
    duplicate = {}
    for authority in ("FINAL_TARGET", "RISK_UPPER_BOUND"):
        holders = [m for m, i in nodes.items()
                   if i["authority"] == authority
                   and i["production_reachable"]]
        parallel = []
        for a in holders:
            reach_a = _reachable_set(a)
            if any(b not in reach_a for b in holders if b != a):
                parallel.append(a)
        if parallel:
            duplicate[authority] = parallel
    orphan = [m for m, i in nodes.items()
              if i["canonical_stage"] and not i["production_reachable"]
              and i["authority"] != "FORMAL_RESEARCH_STATUS"]
    leakage = [m for m, i in nodes.items()
               if i["production_reachable"]
               and any(m.startswith(p) for p in FORBIDDEN_PRODUCTION_PREFIXES)]
    islands = [m for m, i in nodes.items()
               if i["authority"] != "NONE"
               and not i["production_reachable"]
               and not i["canonical_stage"]]
    return {
        "duplicate_authority": {
            k: v for k, v in duplicate.items() if len(v) > 1},
        "production_orphan": orphan,
        "dead_production_path": [],
        "research_leakage": leakage,
        "governance_island": islands,
    }


def retirement_classify(graph: dict, feature_states: dict = None,
                        evidence: dict = None) -> dict:
    """Phase 3：所有模块强制分类。"""
    evidence = evidence or {}
    decisions = {}
    for module, info in graph["nodes"].items():
        stage = info["canonical_stage"]
        reachable = info["production_reachable"]
        authority = info["authority"]
        if stage and reachable:
            classification = "ACTIVE_CORE"
        elif reachable and authority == "NONE":
            classification = "ACTIVE_SUBCAPABILITY"
        elif module.startswith("scripts."):
            classification = "APPENDIX"
        else:
            classification = "RESEARCH_ONLY"
        # 证据驱动降级：binding=0 + ablation=0 + 非强制 → RETIRE 候选
        ev = evidence.get(module) or {}
        if ev.get("binding_frequency") == 0 \
                and abs(float(ev.get("ablation_value") or 0.0)) <= 0.005 \
                and not ev.get("mandatory_governance") \
                and classification in ("ACTIVE_SUBCAPABILITY", "RESEARCH_ONLY"):
            classification = "RETIRED"
        decisions[module] = {
            "classification": classification,
            "authority": authority,
            "canonical_stage": stage,
            "production_reachable": reachable,
        }
    return {"classifications": decisions,
            "unmapped": [m for m, d in decisions.items()
                         if not d["canonical_stage"]
                         and d["classification"] not in (
                             "APPENDIX", "RESEARCH_ONLY", "RETIRED")]}


def retirement_register(graph: dict, classifications: dict) -> dict:
    """Retirement Register 工作表。"""
    register = {}
    for module, info in graph["nodes"].items():
        cls = classifications["classifications"].get(
            module, {}).get("classification", "RESEARCH_ONLY")
        if cls in ("RESEARCH_ONLY", "RETIRED"):
            decision = "RESEARCH_ONLY" if cls == "RESEARCH_ONLY" \
                else "DELETE"
        elif cls == "ACTIVE_SUBCAPABILITY":
            decision = "MERGE" if not info["decision_critical"] else "KEEP"
        else:
            decision = "KEEP"
        register[module] = {
            "prod_reachable": info["production_reachable"],
            "authority": info["authority"],
            "decision_critical": info["decision_critical"],
            "decision": decision,
        }
    return {"register": register,
            "delete": [m for m, r in register.items()
                       if r["decision"] == "DELETE"],
            "merge": [m for m, r in register.items()
                      if r["decision"] == "MERGE"],
            "keep": [m for m, r in register.items()
                     if r["decision"] == "KEEP"]}


def logical_detachment(graph: dict, candidates: list) -> dict:
    """Phase 4：Logical Detachment——候选必须从 Production 真正断开。"""
    still_reachable = [c for c in candidates
                       if graph["nodes"].get(c, {}).get(
                           "production_reachable")]
    return {"detached": [c for c in candidates
                         if c not in still_reachable],
            "still_reachable": still_reachable,
            "verdict": "DETACHED" if not still_reachable
            else "STILL_REACHABLE"}


def regression_gates(results: dict) -> dict:
    """Phase 6：五层回归 Gate。"""
    gates = ("static", "golden_corpus", "replay", "research",
             "safety_failure_injection")
    return {g: bool(results.get(g)) for g in gates}


def convergence_before_after(before: dict, after: dict) -> dict:
    """Phase 7：三降硬门——ExecutablePaths/ACTIVE Features/Critical LOC
    必须下降；Duplicate Authorities/Legacy Imports 必须 = 0。"""
    kpis = {}
    for k in ("production_files", "production_critical_loc",
              "active_modules", "active_features",
              "executable_decision_paths", "duplicate_authorities",
              "legacy_production_imports", "canonical_coverage",
              "replay_coverage", "invariant_coverage",
              "oos_evidence_quality"):
        kpis[k] = {"before": before.get(k), "after": after.get(k)}
    hard_down = (
        after["executable_decision_paths"] < before["executable_decision_paths"]
        and after["active_features"] < before["active_features"]
        and after["production_critical_loc"] < before["production_critical_loc"])
    zero = (after["duplicate_authorities"] == 0
            and after["legacy_production_imports"] == 0)
    coverage_ok = (
        after["canonical_coverage"] >= before["canonical_coverage"]
        and after["replay_coverage"] >= before["replay_coverage"]
        and after["invariant_coverage"] >= before["invariant_coverage"]
        and after["oos_evidence_quality"] >= before["oos_evidence_quality"])
    verdict = "PHYSICAL_CONVERGENCE_PROVEN" if hard_down and zero \
        and coverage_ok else "PHYSICAL_CONVERGENCE_INCOMPLETE"
    return {"kpis": kpis,
            "hard_down": hard_down,
            "duplicate_zero": zero,
            "coverage_not_down": coverage_ok,
            "verdict": verdict}


def production_manifest_final(graph: dict, classifications: dict) -> dict:
    """最终 Production Manifest：只有 ACTIVE_CORE/ACTIVE_SUBCAPABILITY。"""
    active = [m for m, d in classifications["classifications"].items()
              if d["classification"] in ("ACTIVE_CORE",
                                         "ACTIVE_SUBCAPABILITY")]
    return {"production_modules": sorted(active),
            "count": len(active),
            "authorities": {m: graph["nodes"][m]["authority"]
                            for m in active},
            "rule": "只有 ACTIVE 进入 ProductionManifest"}


def pwc2_definition_of_done(checks: dict) -> dict:
    """Definition of Done 封板清单。"""
    requirements = (
        "graph_from_real_roots",
        "all_modules_classified",
        "unmapped_production_zero",
        "canonical_authority_one",
        "permission_authority_one",
        "final_target_authority_one",
        "validation_authority_one",
        "wave_taxonomy_one",
        "report_decision_authority_zero",
        "research_production_dependency_zero",
        "legacy_production_dependency_zero",
        "active_but_unwired_zero",
        "duplicate_authority_zero",
        "retirement_review_complete",
        "logical_detachment_complete",
        "physical_deletion_complete",
        "golden_corpus_pass",
        "replay_pass",
        "canonical_oos_pass",
        "canonical_stress_pass",
        "failure_injection_pass",
        "executable_paths_down",
        "active_features_down",
        "production_loc_down",
        "coverage_not_down",
    )
    results = {r: bool(checks.get(r)) for r in requirements}
    failures = [r for r, ok in results.items() if not ok]
    return {"results": results, "failures": failures,
            "verdict": "PWC2_CLOSED" if not failures
            else "PWC2_INCOMPLETE",
            "allowed": not failures}


def pwc2_release_artifacts(root_dir, before: dict, after: dict,
                           checks: dict) -> dict:
    """生成 5 个 Release Artifact（JSON + MD 摘要）。"""
    graph = build_authority_graph(root_dir)
    audit = authority_audit(graph)
    classifications = retirement_classify(graph)
    register = retirement_register(graph, classifications)
    gate_results = regression_gates(checks)
    convergence = convergence_before_after(before, after)
    manifest = production_manifest_final(graph, classifications)
    dod = pwc2_definition_of_done(checks)
    return {
        "authority_graph": {"nodes": graph["nodes"],
                            "edges": graph["edges"],
                            "roots": graph["roots"]},
        "retirement_register": register,
        "convergence_before_after": convergence,
        "regression_evidence": gate_results,
        "production_manifest": manifest,
        "definition_of_done": dod,
        "audit": audit,
    }


def write_pwc2_artifacts(artifacts: dict, out_dir) -> None:
    """把 5 个 Artifact 写为 JSON + MD。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("authority_graph", "retirement_register",
                 "convergence_before_after", "regression_evidence",
                 "production_manifest"):
        data = artifacts.get(name)
        (out_dir / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
    lines = ["# QCFP_MTF PWC-2 — Production Authority Graph "
             "& Physical Retirement", ""]
    conv = artifacts["convergence_before_after"]
    lines.append(f"## Convergence: {conv['verdict']}")
    for k, v in conv["kpis"].items():
        lines.append(f"- {k}: {v['before']} → {v['after']}")
    reg = artifacts["retirement_register"]
    lines += ["", "## Retirement Register",
              "", f"DELETE: {len(reg['delete'])}  "
                  f"MERGE: {len(reg['merge'])}  KEEP: {len(reg['keep'])}", ""]
    manifest = artifacts["production_manifest"]
    lines += ["## Final Production Manifest",
              "", f"Production modules: {manifest['count']}", ""]
    dod = artifacts["definition_of_done"]
    lines.append(f"## Definition of Done: {dod['verdict']}")
    (out_dir / "pwc2_convergence.md").write_text(
        "\n".join(lines), encoding="utf-8")
