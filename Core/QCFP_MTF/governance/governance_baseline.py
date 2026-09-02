# coding: utf-8
"""Canonical Baseline Freeze（流程治理 Sprint A #2）

把「Architecture Freeze = 文档不再变化」废弃，改为机器可验证的
**Canonical Baseline Freeze + Architecture Baseline Freeze**：
  * Spec / Architecture / Constitution / Production Manifest / Golden Corpus
    各自哈希，统一冻结为 governance_baseline.json；
  * Baseline 是 Create-Only、Immutable、No Overwrite；
  * 任一 Hash 漂移 → BASELINE_CHANGED → Change Review Required，
    禁止「测试失败 → 改 baseline → 测试重新 PASS」。

规则（QCFP-SPEC-CHG-003）：
    Change → 新 Baseline Candidate → Validation → Approval → 新 Baseline
"""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


BASELINE_VERSION = "GOV-BASELINE-1"
BASELINE_FILENAME = "governance_baseline.json"
CANDIDATE_FILENAME = "governance_baseline_candidate.json"


def get_qcfp_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_qcfp_module_dir() -> Path:
    """Core/QCFP_MTF 模块目录（Spec / Architecture / Golden 所在）。"""
    return Path(__file__).resolve().parents[1]


def default_baseline_dir(qcfp_root=None) -> Path:
    root = Path(qcfp_root) if qcfp_root else get_qcfp_root()
    return root / "audit" / "baseline"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_json(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_or_empty(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") \
        if path.exists() else ""


def spec_hash(qcfp_root=None) -> str:
    module_dir = get_qcfp_module_dir()
    return _sha256_text(_read_or_empty(module_dir / "CANONICAL_SPEC.md"))


def architecture_hash(qcfp_root=None) -> str:
    module_dir = get_qcfp_module_dir()
    return _sha256_text(_read_or_empty(module_dir / "ARCHITECTURE.md"))


def constitution_hash(qcfp_root=None) -> str:
    """系统宪法 + 最终设计原则的联合哈希（不可变最高过滤器）。"""
    root = Path(qcfp_root) if qcfp_root else get_qcfp_root()
    from QCFP_MTF.governance.system_constitution import \
        CONSTITUTION_PRINCIPLES
    from QCFP_MTF.governance.final_design_principles import \
        FINAL_DESIGN_PRINCIPLES
    return _sha256_json({
        "constitution": list(CONSTITUTION_PRINCIPLES),
        "final_design_principles": list(FINAL_DESIGN_PRINCIPLES),
    })


def production_manifest_hash(qcfp_root=None) -> str:
    """Frozen Production Feature Manifest（Artifact A）哈希。"""
    from QCFP_MTF.governance.minimal_trusted_release import \
        FROZEN_PRODUCTION_MANIFEST
    return _sha256_json(FROZEN_PRODUCTION_MANIFEST)


def golden_corpus_hash(qcfp_root=None) -> str:
    """Golden Corpus 冻结版本 + 冻结哈希 + 实际 golden 文件内容。"""
    from QCFP_MTF.governance.minimal_trusted_release import (
        FROZEN_GOLDEN_CORPUS_HASH,
        FROZEN_GOLDEN_CORPUS_VERSION,
    )
    module_dir = get_qcfp_module_dir()
    corpus_files = sorted(
        (module_dir / "tests" / "golden").glob("*.json"))
    corpus_text = "\n".join(
        _read_or_empty(p) for p in corpus_files)
    return _sha256_json({
        "version": FROZEN_GOLDEN_CORPUS_VERSION,
        "frozen_hash": FROZEN_GOLDEN_CORPUS_HASH,
        "files": [p.name for p in corpus_files],
        "corpus_text_hash": _sha256_text(corpus_text),
    })


def git_commit_hash(qcfp_root=None) -> str:
    """读取当前 commit（无 git 仓库时返回空串，不计为漂移）。"""
    root = Path(qcfp_root) if qcfp_root else get_qcfp_root()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(root),
            capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def compute_baseline(qcfp_root=None, commit_hash=None) -> dict:
    """Compute Current Baseline（Evidence Generator 职责）。"""
    root = Path(qcfp_root) if qcfp_root else get_qcfp_root()
    from QCFP_MTF.decision.versions import (
        DECISION_RULE_VERSION,
        MODEL_VERSION,
        SCHEMA_VERSION,
        feature_manifest_hash,
    )
    from QCFP_MTF.governance.phase1 import phase1_authority_surface_hash
    commit = commit_hash if commit_hash is not None \
        else git_commit_hash(root)
    return {
        "baseline_id": BASELINE_VERSION,
        "created_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "spec_hash": spec_hash(root),
        "architecture_hash": architecture_hash(root),
        "model_version": MODEL_VERSION,
        "rule_version": DECISION_RULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "engine_version": "canonical-2.8",
        "production_manifest_hash": production_manifest_hash(root),
        "golden_corpus_hash": golden_corpus_hash(root),
        "constitution_hash": constitution_hash(root),
        # P1-FIX-02：Phase 1 Authority Surface（9 个显式文件 path+content SHA）
        "phase1_authority_surface_hash":
            phase1_authority_surface_hash(root),
        "commit_hash": commit,
        "immutable": True,
        "create_only": True,
        "rule": "Create Only / Immutable / No Overwrite；"
                "任一 Hash 漂移 → BASELINE_CHANGED → Change Review Required",
    }


def write_baseline(baseline: dict, out_dir=None) -> dict:
    """Create-Only：目标已存在则拒绝覆盖（与 freeze_mtr_baseline 一致）。"""
    out_dir = Path(out_dir) if out_dir else default_baseline_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / BASELINE_FILENAME
    if path.exists():
        return {"frozen": False, "reason": "Baseline 已存在（不可变，禁止覆盖）",
                "path": str(path), "baseline_id": baseline.get("baseline_id")}
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return {"frozen": True, "path": str(path),
            "baseline_id": baseline.get("baseline_id")}


def load_baseline(baseline_path=None) -> dict:
    path = Path(baseline_path) if baseline_path \
        else default_baseline_dir() / BASELINE_FILENAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def verify_baseline(frozen: dict = None, qcfp_root=None,
                    commit_hash=None) -> dict:
    """DoD：Baseline 重算 == Frozen Baseline；任一 Hash 漂移 → 变化。"""
    frozen = frozen if frozen is not None else load_baseline()
    if not frozen:
        return {"verdict": "NO_BASELINE",
                "reason": "不存在 governance_baseline.json，"
                          "必须先 baseline-init 创建",
                "pass": False}
    current = compute_baseline(qcfp_root, commit_hash)
    hash_fields = (
        "spec_hash", "architecture_hash", "production_manifest_hash",
        "golden_corpus_hash", "constitution_hash",
        "phase1_authority_surface_hash",
    )
    drift = {}
    for field in hash_fields:
        if str(frozen.get(field) or "") != str(current.get(field) or ""):
            drift[field] = {"frozen": frozen.get(field),
                            "current": current.get(field)}
    version_fields = ("model_version", "rule_version", "schema_version",
                      "engine_version")
    version_drift = {}
    for field in version_fields:
        if frozen.get(field) != current.get(field):
            version_drift[field] = {"frozen": frozen.get(field),
                                    "current": current.get(field)}
    changed = bool(drift or version_drift)
    return {
        "baseline_id": frozen.get("baseline_id"),
        "drift": drift,
        "version_drift": version_drift,
        "pass": not changed,
        "verdict": "PASS" if not changed else "BASELINE_CHANGED",
        "rule": "任一 Hash 漂移 → BASELINE_CHANGED → Change Review Required；"
                "禁止修改 Baseline 让测试重新 PASS",
        "recompute": current,
    }


def baseline_gate(qcfp_root=None) -> dict:
    """Baseline Gate：frozen 存在且重算一致 → BASELINE_PASS。"""
    frozen = load_baseline()
    if not frozen:
        return {"verdict": "NO_BASELINE", "pass": False,
                "gate": "BASELINE_GATE",
                "rule": "Create Only / Immutable / No Overwrite"}
    result = verify_baseline(frozen, qcfp_root)
    if result["verdict"] != "PASS":
        return {"verdict": "BASELINE_CHANGED", "pass": False,
                "gate": "BASELINE_GATE",
                "drift": result["drift"],
                "version_drift": result["version_drift"],
                "rule": "Baseline 漂移 → 必须走新 Baseline Candidate "
                        "→ Validation → Approval → 新 Baseline"}
    return {"verdict": "BASELINE_PASS", "pass": True,
            "gate": "BASELINE_GATE",
            "baseline_id": frozen.get("baseline_id"),
            "rule": "Baseline 重算 == Frozen Baseline"}


def baseline_artifact(out_dir=None, qcfp_root=None) -> dict:
    """把当前 Baseline 检查写入 audit/baseline/ 下（供 Release Evidence 包）。"""
    out_dir = Path(out_dir) if out_dir else default_baseline_dir(qcfp_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = baseline_gate(qcfp_root)
    result["schema"] = "BASELINE-GATE-2"
    result["pass"] = bool(result["pass"])
    (out_dir / "baseline_gate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Baseline 变更流程：Change → 新 Baseline Candidate → Validation → Approval
# → 新 Baseline（QCFP-SPEC-CHG-003）。旧 Baseline 先归档，不覆盖、不删除。
# ---------------------------------------------------------------------------

def _next_baseline_id(out_dir) -> str:
    out_dir = Path(out_dir)
    existing = list(out_dir.glob("governance_baseline_GOV-*.json"))
    if (out_dir / BASELINE_FILENAME).exists():
        existing.append(out_dir / BASELINE_FILENAME)
    n = len(existing) + 1
    while (out_dir / f"governance_baseline_GOV-BASELINE-{n}.json").exists():
        n += 1
    return f"GOV-BASELINE-{n}"


def create_baseline_candidate(out_dir=None, qcfp_root=None) -> dict:
    """新 Baseline Candidate：只新增，不覆盖已有 Candidate/Frozen。"""
    out_dir = Path(out_dir) if out_dir else default_baseline_dir(qcfp_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = out_dir / CANDIDATE_FILENAME
    if candidate_path.exists():
        return {"created": False,
                "reason": "Candidate 已存在（先 approve 或人工评审后清理）",
                "path": str(candidate_path)}
    frozen = load_baseline(out_dir / BASELINE_FILENAME)
    baseline = compute_baseline(qcfp_root)
    baseline["baseline_id"] = _next_baseline_id(out_dir)
    baseline["supersedes"] = frozen.get("baseline_id", "")
    candidate_path.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return {"created": True, "path": str(candidate_path),
            "baseline_id": baseline["baseline_id"],
            "supersedes": baseline["supersedes"]}


def validate_baseline_candidate(out_dir=None, qcfp_root=None) -> dict:
    """Validation：Candidate 重算 == Candidate，并列出相对 Frozen 的漂移。"""
    out_dir = Path(out_dir) if out_dir else default_baseline_dir(qcfp_root)
    candidate_path = out_dir / CANDIDATE_FILENAME
    if not candidate_path.exists():
        return {"verdict": "NO_CANDIDATE",
                "pass": False,
                "reason": "不存在 governance_baseline_candidate.json，"
                          "先 baseline-candidate 创建"}
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    recompute = compute_baseline(qcfp_root)
    hash_fields = (
        "spec_hash", "architecture_hash", "production_manifest_hash",
        "golden_corpus_hash", "constitution_hash",
        "phase1_authority_surface_hash",
    )
    inconsistent = [f for f in hash_fields
                    if candidate.get(f) != recompute.get(f)]
    frozen = load_baseline(out_dir / BASELINE_FILENAME)
    drift = {}
    for field in hash_fields + ("model_version", "rule_version",
                                "schema_version", "engine_version"):
        if candidate.get(field) != frozen.get(field):
            drift[field] = {"frozen": frozen.get(field),
                            "candidate": candidate.get(field)}
    valid = not inconsistent
    return {
        "candidate_id": candidate.get("baseline_id"),
        "supersedes": candidate.get("supersedes"),
        "recompute_inconsistent": inconsistent,
        "drift_vs_frozen": drift,
        "valid": valid,
        "verdict": "CANDIDATE_VALID" if valid else "CANDIDATE_INVALID",
        "rule": "Candidate 必须重算一致；批准后旧 Baseline 归档、"
                "Candidate 成为新 Frozen",
    }


def approve_baseline_candidate(out_dir=None, qcfp_root=None,
                               human_approved: bool = False) -> dict:
    """Approval（仅 Human，QCFP-SPEC-RLS-004）：旧 Frozen 归档 → 新 Frozen。"""
    out_dir = Path(out_dir) if out_dir else default_baseline_dir(qcfp_root)
    if not human_approved:
        return {"approved": False,
                "reason": "AI 无权批准 Baseline；必须 Human Approval"}
    candidate_path = out_dir / CANDIDATE_FILENAME
    if not candidate_path.exists():
        return {"approved": False, "reason": "无 Candidate 可批准"}
    validation = validate_baseline_candidate(out_dir, qcfp_root)
    if not validation["valid"]:
        return {"approved": False,
                "reason": "Candidate 重算不一致，拒绝批准",
                "validation": validation}
    frozen_path = out_dir / BASELINE_FILENAME
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    archive = ""
    if frozen_path.exists():
        frozen_data = json.loads(frozen_path.read_text(encoding="utf-8"))
        archive = out_dir / \
            f"governance_baseline_{frozen_data.get('baseline_id')}.json"
        if not archive.exists():
            frozen_path.rename(archive)
    candidate_path.rename(frozen_path)
    return {"approved": True,
            "baseline_id": candidate.get("baseline_id"),
            "supersedes": candidate.get("supersedes"),
            "archive": str(archive),
            "rule": "旧 Baseline 归档保留；新 Baseline 为唯一 Frozen"}
