# coding: utf-8
"""Evidence-Aware ChatGPT Review（流程治理 Sprint C #7）

把「Code → ChatGPT Review」升级为：
    Canonical Spec + Architecture Baseline + ADR + Implementation Contract
    + Change Impact + Diff + Test Results + Authority Graph + Evidence
    → ChatGPT Review

Review 输出必须分类（SPEC_VIOLATION / ARCHITECTURE_VIOLATION /
AUTHORITY_VIOLATION / IMPLEMENTATION_DEFECT / TEST_GAP / EVIDENCE_GAP /
COMPLEXITY_REGRESSION / SCOPE_CREEP / DOCUMENTATION_DRIFT / NO_ISSUE），
每个问题必须包含 Finding ID / Severity / Spec ID / Evidence / Affected
file / Why / Required correction / Acceptance condition。

硬边界（QCFP-SPEC-RLS-004）：
    * ChatGPT 可以输出 REVIEW_CLEAN；
    * 绝不允许输出 RELEASE_PASS —— Reviewer 不能成为 Certification
      Authority。
"""

import json
from pathlib import Path


REVIEW_CATEGORIES = (
    "SPEC_VIOLATION", "ARCHITECTURE_VIOLATION", "AUTHORITY_VIOLATION",
    "IMPLEMENTATION_DEFECT", "TEST_GAP", "EVIDENCE_GAP",
    "COMPLEXITY_REGRESSION", "SCOPE_CREEP", "DOCUMENTATION_DRIFT",
    "NO_ISSUE",
)

# 固定输入（至少包含，缺一不可启动 Review）
REVIEW_INPUTS = (
    "change_id", "spec_ids", "architecture_baseline",
    "implementation_contract", "actual_diff", "test_evidence",
    "authority_audit", "complexity_diff", "changed_decision_samples",
    "known_not_proven_items",
)

FORBIDDEN_REVIEW_OUTCOMES = ("RELEASE_PASS",)

REVIEW_RESOLUTION_SCHEMA = "REVIEW-RESOLUTION-2"


def validate_review_inputs(inputs: dict) -> dict:
    missing = [k for k in REVIEW_INPUTS if inputs.get(k) is None]
    return {"missing": missing,
            "ready": not missing,
            "rule": "固定输入缺任一 → Review 不得开始"}


def check_finding(finding: dict) -> dict:
    """校验单个 Finding 完整性。"""
    required = ("finding_id", "severity", "category", "spec_id",
                "evidence", "affected_file", "why", "required_correction",
                "acceptance_condition")
    missing = [f for f in required if not finding.get(f)]
    category = finding.get("category")
    if category not in REVIEW_CATEGORIES:
        missing.append("category(invalid)")
    severity = finding.get("severity")
    if severity not in ("CRITICAL", "MAJOR", "MINOR"):
        missing.append("severity(invalid)")
    return {"finding_id": finding.get("finding_id"),
            "valid": not missing, "missing": missing}


def review_report(review: dict) -> dict:
    """生成 Evidence-Aware Review Report（md + json）。

    review: {
        change_id, reviewer="ChatGPT", inputs: {...}, findings: [...]
    }
    只允许 REPORT_CLEAN；RELEASE_PASS 被禁止（Reviewer 无认证权）。
    """
    inputs_ok = validate_review_inputs(review.get("inputs") or {})
    if not inputs_ok["ready"]:
        return {"report": "REVIEW_REPORT",
                "verdict": "REVIEW_NOT_STARTED",
                "missing_inputs": inputs_ok["missing"],
                "rule": "固定输入缺失 → Review 不启动（Evidence-Aware）"}
    findings = list(review.get("findings") or [])
    invalid = []
    for f in findings:
        if f.get("category") == "NO_ISSUE":
            # NO_ISSUE 只要求 finding_id + category
            if not (f.get("finding_id") and f.get("category")):
                invalid.append(f)
        elif not check_finding(f)["valid"]:
            invalid.append(f)
    if invalid:
        return {"report": "REVIEW_REPORT",
                "verdict": "REVIEW_INVALID",
                "invalid_findings": invalid,
                "rule": "Finding 必须包含完整九要素"}
    real = [f for f in findings if f.get("category") != "NO_ISSUE"]
    verdict = "REVIEW_CLEAN" if not real else "REVIEW_ISSUES"
    report = {
        "report": "REVIEW_REPORT",
        "schema": "REVIEW-2",
        "change_id": review.get("change_id"),
        "reviewer": review.get("reviewer", "ChatGPT"),
        "inputs_received": sorted(
            k for k, v in (review.get("inputs") or {}).items()
            if v is not None),
        "findings": findings,
        "n_findings": len(real),
        "verdict": verdict,
        "certification_authority": "None",
        "rule": "Reviewer 可以输出 REVIEW_CLEAN，但绝不能输出 "
                "RELEASE_PASS —— Reviewer 不能成为 Certification Authority",
    }
    return report


def review_artifact(review: dict, out_dir) -> dict:
    """写 review_report.json + review_report.md。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = review_report(review)
    (out_dir / "review_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8")
    lines = [
        "# QCFP-MTF Evidence-Aware Review Report",
        "",
        f"**Verdict：{report.get('verdict')}**",
        f"- Change ID：{report.get('change_id')}",
        f"- Reviewer：{report.get('reviewer')}",
        f"- 收到输入：{report.get('inputs_received')}",
        f"- Findings：{report.get('n_findings')}",
        "",
        "## Findings",
    ]
    for f in report.get("findings") or []:
        lines += [
            f"### {f.get('finding_id')} [{f.get('severity')}] "
            f"{f.get('category')}",
            f"- Spec ID：{f.get('spec_id')}",
            f"- Affected File：{f.get('affected_file')}",
            f"- Evidence：{f.get('evidence')}",
            f"- Why：{f.get('why')}",
            f"- Required Correction：{f.get('required_correction')}",
            f"- Acceptance Condition：{f.get('acceptance_condition')}",
            "",
        ]
    lines.append(
        "> Reviewer 无权输出 RELEASE_PASS；发布判定只属于 Pure Release "
        "Judge（SOFTWARE_QUALIFIED / NOT_PROVEN / REJECTED）。")
    (out_dir / "review_report.md").write_text(
        "\n".join(lines), encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# C7：Review Resolution 收口
# ---------------------------------------------------------------------------

def review_gate(resolution: dict) -> dict:
    """Review Gate（C7）：
        CRITICAL open > 0 → REJECTED
        MAJOR open > 0   → REJECTED（Production Release）
        MINOR open       → 允许，但必须记录 accepted risk
    """
    findings = resolution.get("findings") or []
    open_critical = sum(1 for f in findings
                        if f.get("severity") == "CRITICAL"
                        and f.get("resolution") != "FIXED")
    open_major = sum(1 for f in findings
                     if f.get("severity") == "MAJOR"
                     and f.get("resolution") != "FIXED")
    open_minor = sum(1 for f in findings
                     if f.get("severity") == "MINOR"
                     and f.get("resolution") not in ("FIXED", "ACCEPTED_RISK"))
    if open_critical > 0:
        verdict = "REJECTED"
        allowed = False
    elif open_major > 0:
        verdict = "REJECTED"
        allowed = False
    elif open_minor > 0:
        verdict = "REVIEW_CONDITIONAL"
        allowed = True
    else:
        verdict = "REVIEW_RESOLVED"
        allowed = True
    return {
        "gate": "REVIEW_GATE",
        "open_critical": open_critical,
        "open_major": open_major,
        "open_minor": open_minor,
        "verdict": verdict,
        "allowed": allowed,
        "rule": "CRITICAL open>0 → REJECTED；MAJOR open>0 → REJECTED；"
                "MINOR open → 允许但必须记录 accepted risk",
    }


def resolve_review(report: dict, resolutions: dict) -> dict:
    """把 review_report.json 的 findings 与处理结果合并成 resolution。

    resolutions: {finding_id: {resolution, patch_id, verification_test,
                               verified}}；未提供的 finding 视为 open。
    """
    resolutions = resolutions or {}
    findings = []
    for f in (report.get("findings") or []):
        if f.get("category") == "NO_ISSUE":
            continue
        res = resolutions.get(f.get("finding_id")) or {}
        findings.append({
            "finding_id": f.get("finding_id"),
            "severity": f.get("severity"),
            "category": f.get("category"),
            "resolution": res.get("resolution", "OPEN"),
            "patch_id": res.get("patch_id", ""),
            "verification_test": res.get("verification_test", ""),
            "verified": bool(res.get("verified")),
        })
    resolution = {
        "schema": REVIEW_RESOLUTION_SCHEMA,
        "review_id": report.get("change_id", ""),
        "findings": findings,
        "open_critical": sum(1 for f in findings
                             if f["severity"] == "CRITICAL"
                             and f["resolution"] != "FIXED"),
        "open_major": sum(1 for f in findings
                          if f["severity"] == "MAJOR"
                          and f["resolution"] != "FIXED"),
        "open_minor": sum(1 for f in findings
                          if f["severity"] == "MINOR"
                          and f["resolution"] not in
                          ("FIXED", "ACCEPTED_RISK")),
        "accepted_risk": [
            f["finding_id"] for f in findings
            if f["severity"] == "MINOR"
            and f["resolution"] == "ACCEPTED_RISK"],
        "gate": review_gate({
            "findings": findings,
        }),
    }
    return resolution


def review_resolution_artifact(report: dict, resolutions: dict,
                               out_dir) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    resolution = resolve_review(report, resolutions)
    (out_dir / "review_resolution.json").write_text(
        json.dumps(resolution, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return resolution
