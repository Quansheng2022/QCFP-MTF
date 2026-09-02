# coding: utf-8
"""Requirement Traceability Matrix 审计（流程治理 Sprint A #3）

把 CANONICAL_SPEC 的永久 ID 连接到 Architecture Rule / Authority /
Production Module / Test / Failure Injection / Evidence / Release Gate，
并执行三类自动审计：
    * Orphan Requirement（有 Spec 需求但没有 Test）→ ERROR
    * Orphan Test（关键 Test 无法追溯 Requirement）→ REVIEW
    * Orphan Production Capability（ACTIVE Feature 无法映射 Spec）
      → RESEARCH_ONLY

P0 Requirement DoD：Spec → Architecture → Owner → Test → Evidence → Gate
全部连通，否则 TRACEABILITY_FAIL。
"""

import json
import re
from pathlib import Path

try:
    import yaml
    _HAS_YAML = True
except ImportError:  # pragma: no cover - CI 环境保证 pyyaml
    yaml = None
    _HAS_YAML = False


def get_qcfp_root() -> Path:
    return Path(__file__).resolve().parents[3]


MANIFEST_PATH = Path(__file__).resolve().parent / "traceability_manifest.yaml"

# C1：测试根目录必须真实存在且扫描到 test function，否则 TRACEABILITY_NOT_PROVEN
TEST_ROOT = Path(__file__).resolve().parents[1] / "tests"

REQUIRED_ENTRY_FIELDS = (
    "spec_id", "requirement", "architecture_rule", "authority",
    "production_modules", "tests", "evidence", "release_gate",
)

# C1：Production ACTIVE 能力分类
CAPABILITY_ACTIVE = "ACTIVE_MAPPED"
CAPABILITY_ORPHAN = "ACTIVE_ORPHAN"
CAPABILITY_NON_PRODUCTION = "NON_PRODUCTION"


def load_yaml_file(path) -> object:
    """共享 YAML 加载（traceability / contract 等模块复用）。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"YAML 文件不存在: {path}")
    if not _HAS_YAML:
        raise RuntimeError("缺少 PyYAML：请安装 pyyaml 后再运行治理审计")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def load_manifest(path=None) -> list:
    return load_yaml_file(path or MANIFEST_PATH)


def scan_tests_index(qcfp_root=None) -> list:
    """扫描仓库测试树，收集全部 test_* 函数名（真实索引）。"""
    root = Path(qcfp_root) if qcfp_root else TEST_ROOT
    names = set()
    if not root.exists():
        return []
    for py in root.rglob("test_*.py"):
        src = py.read_text(encoding="utf-8", errors="ignore")
        names.update(re.findall(r"^def\s+(test_\w+)\s*\(", src, re.M))
    return sorted(names)


def production_manifest(qcfp_root=None) -> dict:
    from QCFP_MTF.governance.minimal_trusted_release import \
        FROZEN_PRODUCTION_MANIFEST
    return FROZEN_PRODUCTION_MANIFEST


def manifest_entries(manifest) -> list:
    """normalize：dict{entries: [...]} 或 list[entry] → list[entry]。"""
    if isinstance(manifest, dict):
        return list(manifest.get("entries") or [])
    return list(manifest or [])


def _capability_map_from_manifest(manifest) -> dict:
    """从 manifest 提取 capability_map：{feature: {feature, owner, spec_id}}。"""
    if isinstance(manifest, dict):
        return {m.get("feature"): m for m in
                (manifest.get("capability_map") or [])}
    return {}


def classify_capabilities(manifest=None) -> dict:
    """把 Frozen Production Manifest 的能力分成三类：
    ACTIVE_MAPPED / ACTIVE_ORPHAN / NON_PRODUCTION。
    ACTIVE 能力若 Owner 无法映射到 Traceability Manifest → ACTIVE_ORPHAN
    → TRACEABILITY_FAIL（不允许审计自行降级为 RESEARCH_ONLY）。"""
    from QCFP_MTF.governance.minimal_trusted_release import \
        FROZEN_PRODUCTION_MANIFEST
    manifest = manifest if manifest is not None else load_manifest()
    capability_map = _capability_map_from_manifest(manifest)
    mapped_modules = set()
    entries = manifest_entries(manifest)
    for entry in entries:
        mapped_modules.update(entry.get("production_modules") or [])
    mapped, orphan, non_production = [], [], []
    for feature, info in FROZEN_PRODUCTION_MANIFEST.items():
        state = info.get("state")
        owner = info.get("owner", "")
        if state != "ACTIVE":
            non_production.append(feature)
            continue
        mapped_entry = capability_map.get(feature)
        owner_mapped = any(
            owner and (owner == m or owner.startswith(m + ".")
                       or m.startswith(owner + "."))
            for m in mapped_modules)
        if mapped_entry or owner_mapped:
            mapped.append(feature)
        else:
            orphan.append(feature)
    return {
        "ACTIVE_MAPPED": sorted(mapped),
        "ACTIVE_ORPHAN": sorted(orphan),
        "NON_PRODUCTION": sorted(non_production),
    }


def audit_traceability(manifest=None, tests_index=None,
                       production_features=None) -> dict:
    """三类孤儿审计 + P0 全连通检查（C1 Fail-Closed）。

    * 测试索引为空 → TRACEABILITY_NOT_PROVEN（不得跳过 dangling 检查）
    * ACTIVE 能力无法映射 → TRACEABILITY_FAIL
    * P0/P1 Spec 任一条断链 → TRACEABILITY_FAIL
    """
    manifest = manifest if manifest is not None else load_manifest()
    entries = manifest_entries(manifest)
    tests_index = tests_index if tests_index is not None \
        else scan_tests_index()
    all_tests = set(tests_index)
    test_index_status = "VALID" if all_tests else "NOT_PROVEN"
    referenced = set()
    missing_fields = []
    orphan_requirements = []
    dangling_tests = []
    for entry in entries:
        sid = entry.get("spec_id", "?")
        missing = [f for f in REQUIRED_ENTRY_FIELDS
                   if not entry.get(f)]
        if missing:
            missing_fields.append({"spec_id": sid,
                                   "missing": missing})
        if not entry.get("tests"):
            orphan_requirements.append(sid)
        for t in entry.get("tests") or []:
            referenced.add(t)
            if all_tests and t not in all_tests:
                dangling_tests.append({"spec_id": sid, "test": t})
    orphan_tests = sorted(all_tests - referenced) if all_tests else []
    capabilities = classify_capabilities(manifest)
    active_orphan = capabilities["ACTIVE_ORPHAN"]
    if production_features is not None:
        # 测试注入：显式给定能力集合时按给定集合判定
        injected = set(production_features)
        active_orphan = sorted(
            f for f in injected
            if f not in capabilities["ACTIVE_MAPPED"])
    test_index_fail = test_index_status != "VALID"
    errors = bool(missing_fields or orphan_requirements or dangling_tests
                  or active_orphan or test_index_fail)
    n_entries = len(entries)
    p0_fully_connected = n_entries - len(missing_fields)
    return {
        "schema": "TRACEABILITY-2",
        "n_entries": len(entries),
        "p0_total": n_entries,
        "p0_fully_connected": p0_fully_connected,
        "test_index_status": test_index_status,
        "test_count": len(all_tests),
        "missing_fields": missing_fields,
        "orphan_requirements": orphan_requirements,
        "dangling_test_references": dangling_tests,
        "orphan_tests_review": orphan_tests,
        "capabilities": capabilities,
        "active_orphan_capabilities": active_orphan,
        "pass": not errors,
        "errors": errors,
        "verdict": "TRACEABILITY_NOT_PROVEN" if test_index_fail
        else "TRACEABILITY_PASS" if not errors else "TRACEABILITY_FAIL",
        "rule": "ACTIVE orphan=0、P0 orphan=0、P0 dangling=0、"
                "test_index=VALID 才允许 PASS；测试目录/索引异常 → "
                "TRACEABILITY_NOT_PROVEN",
    }


def traceability_gate(manifest=None, tests_index=None,
                      production_features=None) -> dict:
    result = audit_traceability(manifest, tests_index,
                                production_features)
    return {
        "gate": "TRACEABILITY_GATE",
        "verdict": result["verdict"],
        "pass": not result["errors"],
        "errors": {
            "missing_fields": result["missing_fields"],
            "orphan_requirements": result["orphan_requirements"],
            "dangling_test_references": result["dangling_test_references"],
            "active_orphan_capabilities": result["active_orphan_capabilities"],
            "test_index_status": result["test_index_status"],
        },
        "reviews": {
            "orphan_tests": result["orphan_tests_review"][:50],
        },
    }


def traceability_artifact(out_dir=None, qcfp_root=None) -> dict:
    out_dir = Path(out_dir) if out_dir \
        else (Path(qcfp_root) if qcfp_root else get_qcfp_root()) / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    audit = audit_traceability()
    (out_dir / "traceability_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8")
    lines = [
        "# QCFP-MTF Traceability Audit",
        "",
        f"**Verdict：{audit['verdict']}**",
        f"- Schema：{audit['schema']}",
        f"- Test Index：{audit['test_index_status']}（{audit['test_count']} 项）",
        f"- P0：{audit['p0_fully_connected']}/{audit['p0_total']} 全连通",
        f"- 条目数：{audit['n_entries']}",
        f"- 缺失字段：{audit['missing_fields'] or '无'}",
        f"- Orphan Requirements：{audit['orphan_requirements'] or '无'}",
        f"- 悬空测试引用：{audit['dangling_test_references'] or '无'}",
        f"- Orphan Tests（REVIEW）：{len(audit['orphan_tests_review'])} 项",
        f"- ACTIVE Orphan Capabilities："
        f"{audit['active_orphan_capabilities'] or '无'}",
    ]
    (out_dir / "traceability_audit.md").write_text(
        "\n".join(lines), encoding="utf-8")
    return audit
