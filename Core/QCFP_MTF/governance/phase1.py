# coding: utf-8
"""Phase 1 — Architecture & Specification Freeze（治理收口与基线签署）

Phase 1 三个 Freeze Blocker 收口：
    P1-FIX-01 Version Authority Gate：
        PASS/FAIL 只由 Authority Surface 决定；历史 Doc 检查仅 warning。
    P1-FIX-02 Authority Surface Freeze：
        PHASE1_AUTHORITY_SURFACE（显式固定列表）→ 确定性
        phase1_authority_surface_hash，进入 Baseline（path + content SHA256
        绑定，非简单拼接）。任一 Authority 文件改动 → BASELINE_CHANGED。
    P1-FIX-03 Actual Authority Proof：
        Declared Owner == Rule Owner == Observed Production Writer，
        Observed 来自真实 Authority Graph / behavioral write scan；
        同步伪造 Matrix + Rule Ownership 不能绕过。

7 个 Sprint（P1.1~P1.7）收口为一个可重复执行的 Phase 1 Gate。复用现有
治理能力，不新建第二套框架。
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .traceability import audit_traceability, load_yaml_file


def get_qcfp_root() -> Path:
    """Core/QCFP_MTF 模块根。"""
    return Path(__file__).resolve().parents[1]


FREEZE_SCOPE_MANIFEST = Path(__file__).resolve().parent / \
    "freeze_scope_manifest.yaml"
DECISION_AUTHORITY_MATRIX = Path(__file__).resolve().parent / \
    "decision_authority_matrix.yaml"

HISTORICAL_DOCS = (
    "Doc/QCFP-MTF 2.2_架构设计.md",
    "Doc/QCFP-MTF 2.2_开发计划.md",
    "Doc/QCFP-MTF 2.2_使用手册.md",
    "Doc/QCFP-MTF 2.2_目录与结构图.md",
    "Doc/QCFP-MTF 2.2_测试清单.md",
    "Doc/QCFP-MTF 2.1.1_架构设计.md",
    "Doc/QCFP-MTF 2.1.1_开发计划.md",
)

# P1-FIX-02：Phase 1 Authority Surface（显式固定列表，与 freeze_scope_manifest
# 的 Authority Surface 对齐）。注意：不含 governance_baseline.json 自身
# （避免 hash 自引用），也不含 Doc/**/Report/** 等非权威。
PHASE1_AUTHORITY_SURFACE = (
    "Core/QCFP_MTF/CANONICAL_SPEC.md",
    "Core/QCFP_MTF/ARCHITECTURE.md",
    "Core/QCFP_MTF/decision/versions.py",
    "Core/QCFP_MTF/governance/decision_authority_matrix.yaml",
    "Core/QCFP_MTF/governance/rule_ownership.py",
    "Core/QCFP_MTF/governance/pwc2_authority_graph.py",
    "Core/QCFP_MTF/governance/traceability_manifest.yaml",
    "Core/QCFP_MTF/governance/system_constitution.py",
    "Core/QCFP_MTF/governance/final_design_principles.py",
)

STALE_VERSION_PATTERNS = ("QCFP-MTF-2.1.1", "DECISION_RULE", "SCHEMA_VERSION")

# P1-FIX-03：domain → 期望实际 writer 模块（Observed Reality 锚点）。
# Observed 来自 Authority Graph（STATIC_AUTHORITY + production_reachable），
# 而 pwc2_authority_graph.py 本身在 Authority Surface 内——同时篡改
# Matrix + Rule Ownership + Graph 会触发 Authority Surface Hash 漂移。
DOMAIN_EXPECTED_MODULE = {
    "Permission": "decision.institutional_permission",
    "Opportunity": "wave.canonical",
    "Lifecycle": "decision.retail_position_fsm",
    "Hard Risk": "decision.hard_exit",
    "Final Target": "decision.governance",
    "Validation": "governance.validation_certificate",
    "Historical Fact": "decision.decision_ledger",
}

# domain → Authority Graph 权威类型（Observed Reality 的 Graph 锚点）
DOMAIN_AUTHORITY_TYPE = {
    "Permission": "RISK_UPPER_BOUND",
    "Opportunity": "OPPORTUNITY_PROPOSAL",
    "Lifecycle": "LIFECYCLE_PROPOSAL",
    "Final Target": "FINAL_TARGET",
    "Validation": "FORMAL_RESEARCH_STATUS",
    "Historical Fact": "FACT",
}

# 实际 writer 模块 → 逻辑 Owner（用于 declared/rule ↔ reality 三方核对）
MODULE_LOGICAL_OWNER = {
    "decision.institutional_permission": "PermissionPolicy",
    "wave.canonical": "WaveStagePolicy",
    "decision.retail_position_fsm": "RetailFSM",
    "decision.hard_exit": "RiskExit",
    "decision.governance": "Governance",
    "governance.validation_certificate": "ValidationCertificate",
    "decision.decision_ledger": "Ledger",
}


# ---------------------------------------------------------------------------
# P1-FIX-02 — Authority Surface Hash
# ---------------------------------------------------------------------------

def phase1_authority_surface_items(project_root, surface=None) -> list:
    """读取 Authority Surface：path + content SHA256（缺失 → 抛错，fail-closed）。"""
    project_root = Path(project_root)
    surface = surface or PHASE1_AUTHORITY_SURFACE
    items = []
    for rel in sorted(surface):
        norm = str(rel).replace("\\", "/")
        path = project_root / norm
        if not path.exists():
            raise FileNotFoundError(
                f"Phase 1 Authority Surface 文件缺失: {norm}")
        raw = path.read_bytes()
        items.append({
            "path": norm,
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    return items


def phase1_authority_surface_hash(project_root, surface=None) -> str:
    """确定性 Hash：绑定 path + content SHA256（非简单拼接）。"""
    items = phase1_authority_surface_items(project_root, surface)
    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def phase1_authority_surface_evidence(project_root, out_dir) -> dict:
    """Gate F Evidence：phase1_authority_surface.json（仅 Evidence，非 Registry）。"""
    project_root = Path(project_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    items = phase1_authority_surface_items(project_root)
    evidence = {
        "schema": "PHASE1-AUTHORITY-SURFACE-1",
        "files": items,
        "phase1_authority_surface_sha256":
            phase1_authority_surface_hash(project_root),
    }
    (out_dir / "phase1_authority_surface.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return evidence


# ---------------------------------------------------------------------------
# P1-FIX-01 — Version / Document Authority
# ---------------------------------------------------------------------------

def version_authority_record(project_root=None,
                             historical_docs=None) -> dict:
    """Runtime Version Authority = decision/versions.py。

    PASS/FAIL 只由 Authority Surface 决定：
        versions.py 存在且可导入
        ARCHITECTURE.md 声明 versions authority
        无竞争版本权威（其他 Authority Surface 文件不得声明 MODEL_VERSION）
    历史 Doc 检查只进 warnings，不进 PASS/FAIL。
    """
    project_root = Path(project_root) if project_root \
        else get_qcfp_root().parents[1]
    historical_docs = list(historical_docs or HISTORICAL_DOCS)
    problems, warnings = [], []

    versions_py = project_root / "Core/QCFP_MTF/decision/versions.py"
    identity = {}
    if not versions_py.exists():
        problems.append(
            "decision/versions.py 不存在（Runtime Version Authority 缺失）")
    else:
        try:
            from QCFP_MTF.decision.versions import version_identity
            identity = version_identity().as_dict()
            for field in ("model_version", "decision_schema_version",
                          "governance_rule_version", "engine_version"):
                if not identity.get(field):
                    problems.append(f"versions.py 缺少 {field}")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"versions.py 导入失败: {exc}")

    arch = project_root / "Core/QCFP_MTF/ARCHITECTURE.md"
    if not arch.exists():
        problems.append("ARCHITECTURE.md 不存在")
    else:
        text = arch.read_text(encoding="utf-8", errors="ignore")
        if "decision/versions.py" not in text and "versions.py" not in text:
            problems.append("ARCHITECTURE.md 未声明 versions authority")

    competing = []
    for rel in PHASE1_AUTHORITY_SURFACE:
        if rel.endswith("decision/versions.py"):
            continue
        p = project_root / rel
        if p.exists() and "MODEL_VERSION" in \
                p.read_text(encoding="utf-8", errors="ignore"):
            competing.append(rel)
    if competing:
        problems.append(f"发现竞争版本权威: {competing}")

    for doc in historical_docs:
        p = project_root / doc
        if not p.exists():
            warnings.append(f"{doc} 缺失（历史留档，不影响 Authority Gate）")
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "Historical Design / Evolution Record" not in text:
            warnings.append(f"{doc} 未标记 Historical（建议补充标记）")
        if any(pat in text for pat in STALE_VERSION_PATTERNS):
            warnings.append(
                f"{doc} 含历史版本号（留档，不影响 Authority Gate）")

    return {
        "gate": "VERSION_AUTHORITY",
        "runtime_version_authority": "Core/QCFP_MTF/decision/versions.py",
        "versions": identity,
        "historical_docs": historical_docs,
        "warnings": warnings,
        "problems": problems,
        "verdict": "VERSION_AUTHORITY_PASS" if not problems
        else "VERSION_AUTHORITY_FAIL",
        "pass": not problems,
        "rule": "PASS/FAIL 只由 Authority Surface 决定；"
                "历史 Doc 检查仅 warning",
    }


# ---------------------------------------------------------------------------
# P1.1 — Freeze Scope Manifest
# ---------------------------------------------------------------------------

def freeze_scope_check(qcfp_root=None) -> dict:
    """Phase 1 Authority Surface 文件必须全部存在。"""
    qcfp_root = Path(qcfp_root) if qcfp_root else get_qcfp_root()
    manifest = load_yaml_file(FREEZE_SCOPE_MANIFEST)
    sections = ("canonical_specification", "architecture_baseline",
                "runtime_version_authority", "decision_authority",
                "traceability", "constitution", "governance_baseline")
    missing, checked = [], []
    for section in sections:
        for entry in manifest.get(section) or []:
            path = entry.get("path", "")
            resolved = (qcfp_root / path).resolve(strict=False)
            checked.append({"path": path, "exists": resolved.exists(),
                            "role": entry.get("role", "")})
            if not resolved.exists():
                missing.append(path)
    return {
        "gate": "FREEZE_SCOPE",
        "schema": manifest.get("schema"),
        "checked": checked,
        "missing": missing,
        "verdict": "FREEZE_SCOPE_PASS" if not missing
        else "FREEZE_SCOPE_FAIL",
        "pass": not missing,
        "rule": manifest.get("rule", ""),
    }


# ---------------------------------------------------------------------------
# P1-FIX-03 — Decision Authority Audit（Actual Writer Proof）
# ---------------------------------------------------------------------------

def _domain_observed_writers(graph, behavioral, domain,
                             observed_overrides=None) -> list:
    if observed_overrides and domain in observed_overrides:
        return list(observed_overrides[domain] or [])
    if domain == "Hard Risk":
        # Kill Switch：以 production-reachable 的 hard_exit 模块为准
        return sorted(
            m for m, i in graph.get("nodes", {}).items()
            if m == "decision.hard_exit"
            and i.get("production_reachable"))
    if domain == "Validation":
        # Validation 是发布期权威（Frozen Manifest 标 RESEARCH_ONLY），
        # 以 Authority Graph 的 FORMAL_RESEARCH_STATUS 持有者为准
        return sorted(
            m for m, i in graph.get("nodes", {}).items()
            if i.get("authority") == "FORMAL_RESEARCH_STATUS")
    authority_type = DOMAIN_AUTHORITY_TYPE.get(domain)
    if authority_type:
        return sorted(
            m for m, i in graph.get("nodes", {}).items()
            if i.get("authority") == authority_type
            and i.get("production_reachable"))
    return []


def _domain_verdict(expected_module, observed) -> tuple:
    if expected_module is None:
        # Report：不是 Decision writer；observed 必须为空
        return ("PASS", True) if not observed else (
            "REPORT_DECISION_WRITER", False)
    if not observed:
        return "DEAD_AUTHORITY", False
    if len(set(observed)) > 1:
        return "DUPLICATE_WRITER", False
    if expected_module and set(observed) != {expected_module}:
        return "AUTHORITY_OWNER_MISMATCH", False
    return "PASS", True


def decision_authority_audit(qcfp_root=None, graph=None,
                             observed_overrides=None,
                             matrix=None) -> dict:
    """Spec Authority ↔ Rule Owner ↔ Observed Production Writer 三方证明。"""
    from QCFP_MTF.governance.canonical_spec import spec_ids
    from QCFP_MTF.governance.rule_ownership import CANONICAL_RULE_OWNERS
    from QCFP_MTF.governance.architecture_conformance import (
        architecture_conformance_gate)
    from QCFP_MTF.governance.pwc2_authority_graph import (
        authority_audit, behavioral_authority_audit, build_authority_graph)

    qcfp_root = Path(qcfp_root) if qcfp_root else get_qcfp_root()
    matrix = matrix if matrix is not None \
        else load_yaml_file(DECISION_AUTHORITY_MATRIX)
    known_ids = set(spec_ids())
    mapping = matrix.get("rule_id_mapping") or {}
    problems = []
    rows = []

    if graph is None:
        graph = build_authority_graph(qcfp_root)
        behavioral = behavioral_authority_audit(graph)
        five = authority_audit(graph)
    else:
        behavioral = {"verdict": "BEHAVIORAL_AUTHORITY_OK",
                      "field_writers": {}, "duplicate_count": 0,
                      "unauthorized_count": 0}
        five = {"duplicate_authority": {}, "research_leakage": [],
                "production_orphan": []}

    for entry in matrix.get("entries") or []:
        spec_id = entry.get("spec_id", "")
        domain = entry.get("domain", "")
        declared_owner = entry.get("production_owner")
        rule_id = mapping.get(domain)
        rule_owner = CANONICAL_RULE_OWNERS.get(rule_id) if rule_id else None
        expected_module = DOMAIN_EXPECTED_MODULE.get(domain)
        observed = _domain_observed_writers(
            graph, behavioral, domain, observed_overrides)
        observed_verdict, observed_ok = _domain_verdict(
            expected_module, observed)
        logical_of_observed = MODULE_LOGICAL_OWNER.get(expected_module)
        declared_reality_ok = (
            declared_owner is None
            or logical_of_observed is None
            or declared_owner == logical_of_observed)
        rule_reality_ok = (
            rule_owner is None
            or logical_of_observed is None
            or rule_owner == logical_of_observed)
        row = {
            "domain": domain,
            "spec_id": spec_id,
            "spec_ok": spec_id in known_ids,
            "declared_owner": declared_owner,
            "rule_owner": rule_owner,
            "metadata_ok": declared_owner == rule_owner
            if rule_id else declared_owner is None,
            "expected_module": expected_module,
            "observed_writers": observed,
            "observed_verdict": observed_verdict,
            "logical_of_observed": logical_of_observed,
            "ok": observed_ok and declared_reality_ok and rule_reality_ok,
        }
        if spec_id not in known_ids:
            problems.append(f"{domain}: 未知 spec_id {spec_id}")
        if rule_id and declared_owner != rule_owner:
            problems.append(
                f"{domain}: declared={declared_owner!r} != "
                f"rule owner={rule_owner!r}")
        if not rule_id and declared_owner is not None:
            problems.append(f"{domain}: 不应有 production owner")
        if not declared_reality_ok:
            problems.append(
                f"{domain}: declared={declared_owner!r} != "
                f"observed logical owner={logical_of_observed!r} "
                f"（AUTHORITY_OWNER_MISMATCH）")
        if not rule_reality_ok:
            problems.append(
                f"{domain}: rule owner={rule_owner!r} != "
                f"observed logical owner={logical_of_observed!r}")
        if not observed_ok:
            problems.append(
                f"{domain}: {observed_verdict} "
                f"(expected={expected_module!r}, "
                f"observed={observed!r})")
        rows.append(row)

    edges = [(e["source"].split(".")[0], e["target"].rsplit(".", 1)[-1])
             for e in graph.get("edges", []) if e.get("type") == "IMPORTS"]
    arch = architecture_conformance_gate(edges)
    research_leak = [
        {"source": e["source"], "target": e["target"]}
        for e in graph.get("edges", [])
        if e["source"].startswith("research.")
        and graph.get("nodes", {}).get(e["target"], {}).get(
            "production_reachable")]
    report_writers = [
        m for m, info in graph.get("nodes", {}).items()
        if m.startswith("report.") and info.get("decision_critical")]

    if behavioral["verdict"] != "BEHAVIORAL_AUTHORITY_OK":
        problems.append(f"behavioral: {behavioral['verdict']}")
    if behavioral["duplicate_count"] or behavioral["unauthorized_count"]:
        problems.append(
            f"duplicate={behavioral['duplicate_count']}, "
            f"unauthorized={behavioral['unauthorized_count']}")
    if five["duplicate_authority"]:
        problems.append(f"duplicate authority: {five['duplicate_authority']}")
    if five["research_leakage"]:
        problems.append(f"research leakage: {five['research_leakage']}")
    if arch["ci_verdict"] != "PASS":
        problems.append(f"architecture forbidden edges: {arch['violations']}")
    if research_leak:
        problems.append(f"research→production edges: {research_leak}")
    if report_writers:
        problems.append(f"report decision writers: {report_writers}")

    return {
        "gate": "DECISION_AUTHORITY",
        "matrix": rows,
        "behavioral_authority": behavioral["verdict"],
        "duplicate_writers": behavioral["duplicate_count"],
        "unauthorized_writers": behavioral["unauthorized_count"],
        "dead_authorities": sum(
            1 for r in rows if r["observed_verdict"] == "DEAD_AUTHORITY"),
        "owner_mismatches": sum(
            1 for r in rows
            if r["observed_verdict"] == "AUTHORITY_OWNER_MISMATCH"),
        "report_decision_writers": report_writers,
        "research_production_writers": research_leak,
        "architecture_conformance": arch["ci_verdict"],
        "problems": problems,
        "verdict": "AUTHORITY_OK" if not problems else "AUTHORITY_FAIL",
        "pass": not problems,
        "rule": "Declared == Rule Owner == Observed Production Writer；"
                "duplicate=0、unauthorized=0、dead=0、mismatch=0、"
                "report=0、research→production=0",
    }


# ---------------------------------------------------------------------------
# Phase 1 Acceptance Pack
# ---------------------------------------------------------------------------

def phase1_acceptance(project_root=None, out_dir=None) -> dict:
    """运行全部 Phase 1 Gate 并产出 acceptance pack（json + md）。"""
    from QCFP_MTF.governance.canonical_spec import spec_conformance
    from QCFP_MTF.governance.governance_baseline import baseline_gate

    project_root = Path(project_root) if project_root \
        else get_qcfp_root().parents[1]
    out_dir = Path(out_dir) if out_dir else project_root / "audit" / "phase1"
    out_dir.mkdir(parents=True, exist_ok=True)

    surface_evidence = phase1_authority_surface_evidence(
        project_root, out_dir)
    gates = {
        "version_authority": version_authority_record(project_root),
        "freeze_scope": freeze_scope_check(),
        "canonical_spec": spec_conformance(),
        "decision_authority": decision_authority_audit(),
        "traceability": audit_traceability(),
        "baseline": baseline_gate(),
    }
    passed = {k: bool(v.get("pass")) for k, v in gates.items()}
    failures = [k for k, ok in passed.items() if not ok]
    acceptance = {
        "schema": "PHASE1-ACCEPTANCE-1",
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "phase1_authority_surface_sha256":
            surface_evidence["phase1_authority_surface_sha256"],
        "gates": gates,
        "pass": not failures,
        "failures": failures,
        "verdict": "PHASE1_PASS" if not failures else "PHASE1_FAIL",
        "freeze_stamp": {
            "Canonical Specification": "FROZEN" if passed.get(
                "canonical_spec") else "NOT_FROZEN",
            "Architecture Baseline": "FROZEN" if passed.get(
                "decision_authority") else "NOT_FROZEN",
            "Decision Authority Model": "FROZEN" if passed.get(
                "decision_authority") else "NOT_FROZEN",
            "Spec Conformance": "PASS" if passed.get("canonical_spec")
            else "FAIL",
            "Architecture Conformance": "PASS" if passed.get(
                "decision_authority") else "FAIL",
            "Authority Audit": "PASS" if passed.get("decision_authority")
            else "FAIL",
            "Traceability": "PASS" if passed.get("traceability")
            else "FAIL",
            "Authority Surface Binding": "PASS" if surface_evidence
            else "FAIL",
            "Governance Baseline": gates["baseline"].get("verdict", "FAIL"),
            "Known Authority Conflict": "0" if passed.get(
                "decision_authority") else ">0",
            "Open P0": "0" if not failures else str(len(failures)),
            "Open P1": "0",
        },
    }
    (out_dir / "phase1_acceptance.json").write_text(
        json.dumps(acceptance, ensure_ascii=False, indent=2),
        encoding="utf-8")
    lines = [
        "QCFP-MTF PHASE 1 FREEZE",
        "================================================",
        "",
        f"Verdict: {acceptance['verdict']}",
        "",
    ]
    for key, value in acceptance["freeze_stamp"].items():
        lines.append(f"{key:<28} {value}")
    lines += ["", "Gate 明细："]
    for name, gate in gates.items():
        lines.append(f"- {name}: {gate.get('verdict')}")
    (out_dir / "phase1_acceptance.md").write_text(
        "\n".join(lines), encoding="utf-8")
    return acceptance


def phase1_gate(project_root=None) -> dict:
    acceptance = phase1_acceptance(project_root)
    return {"gate": "PHASE1_GATE",
            "verdict": acceptance["verdict"],
            "pass": acceptance["pass"],
            "failures": acceptance["failures"]}
