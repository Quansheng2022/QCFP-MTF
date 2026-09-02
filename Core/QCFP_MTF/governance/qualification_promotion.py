# coding: utf-8
"""Software Qualification 与 Strategy Promotion 分离（FGC-1 C6 + SF-5）

状态机（只允许邻接转移）：
    DEVELOPMENT → SOFTWARE_QUALIFIED → RESEARCH_CANDIDATE →
    OOS_VALIDATED → ABLATION_STRESS_VALIDATED → SHADOW →
    PRODUCTION_ELIGIBLE → HUMAN_APPROVED → PRODUCTION_DSS

SF-5 Identity Hardening：
    * Gate A 必须消费 release_verdict.json 且绑定 release_id /
      baseline_id / change_id；生产 Promotion Context 三字段全非空。
    * Human Approval 升级为 HUMAN-APPROVAL-2 Authority Artifact：
      actor_type == HUMAN；approval 绑定 release_verdict_hash /
      evidence_manifest_hash；approval_hash 自校验；不可跨 Release /
      Baseline / Change 复用。
    * HUMAN_APPROVED → PRODUCTION_DSS 复用同一有效 approval
      （target_states 含 PRODUCTION_DSS 或
      production_promotion_authorized=true），不要求重复审批。
"""

import hashlib
import json
from pathlib import Path


HUMAN_APPROVAL_SCHEMA = "HUMAN-APPROVAL-2"

SOFTWARE_QUALIFICATION_CHECKS = (
    "canonical_spec", "architecture_conformance", "authority_uniqueness",
    "static_check", "unit", "integration", "golden", "invariant",
    "failure_injection", "replay_determinism", "ledger_integrity",
    "release_identity", "complexity",
)

STRATEGY_PROMOTION_CHECKS = (
    "pit", "oos", "ablation", "stress", "benchmark", "no_trade_quality",
    "practicality", "shadow_evidence", "risk_behaviour",
    "decision_stability",
)

PROMOTION_STATES = (
    "DEVELOPMENT", "SOFTWARE_QUALIFIED", "RESEARCH_CANDIDATE",
    "OOS_VALIDATED", "ABLATION_STRESS_VALIDATED", "SHADOW",
    "PRODUCTION_ELIGIBLE", "HUMAN_APPROVED", "PRODUCTION_DSS",
)

ALLOWED_TRANSITIONS = {
    "DEVELOPMENT": {"SOFTWARE_QUALIFIED"},
    "SOFTWARE_QUALIFIED": {"RESEARCH_CANDIDATE"},
    "RESEARCH_CANDIDATE": {"OOS_VALIDATED"},
    "OOS_VALIDATED": {"ABLATION_STRESS_VALIDATED"},
    "ABLATION_STRESS_VALIDATED": {"SHADOW"},
    "SHADOW": {"PRODUCTION_ELIGIBLE"},
    "PRODUCTION_ELIGIBLE": {"HUMAN_APPROVED"},
    "HUMAN_APPROVED": {"PRODUCTION_DSS"},
}

AI_FORBIDDEN_STATES = ("HUMAN_APPROVED", "PRODUCTION_DSS")


def _sha256(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def qualification_gate(checks: dict) -> dict:
    """Gate A 检查清单（兼容保留；正式 Gate A 见 require_pure_judge）。"""
    failed = [c for c in SOFTWARE_QUALIFICATION_CHECKS
              if not checks.get(c)]
    return {
        "gate": "SOFTWARE_QUALIFICATION",
        "failed": failed,
        "verdict": "SOFTWARE_QUALIFIED" if not failed
        else "NOT_QUALIFIED",
        "qualified": not failed,
        "rule": "QUALIFIED 只代表实现可信，不代表策略有效",
    }


def strategy_promotion_gate(checks: dict) -> dict:
    """Gate B 检查清单（兼容保留；正式 Gate B 按阶段读证据）。"""
    failed = [c for c in STRATEGY_PROMOTION_CHECKS
              if not checks.get(c)]
    return {
        "gate": "STRATEGY_PROMOTION",
        "failed": failed,
        "verdict": "STRATEGY_PROMOTION_READY" if not failed
        else "NOT_READY",
        "ready": not failed,
        "rule": "低等级证据只能产生 Hypothesis；只有 Evidence Hierarchy "
                "完整才能成为正式 DSS 版本",
    }


def require_pure_judge(evidence: dict, context: dict) -> list:
    """Gate A（SF-5）：必须消费 Pure Judge 的 release_verdict.json，
    且绑定 change_id / release_id / baseline_id。"""
    verdict = evidence or {}
    context = context or {}
    errors = []
    if verdict.get("verdict") != "SOFTWARE_QUALIFIED":
        errors.append(f"release_verdict.verdict="
                      f"{verdict.get('verdict')} != SOFTWARE_QUALIFIED")
    if verdict.get("certificate") != "SOFTWARE-QUALIFIED":
        errors.append("certificate != SOFTWARE-QUALIFIED")
    # 生产 Promotion Context 三字段全非空
    missing_ctx = [f for f in ("change_id", "release_id", "baseline_id")
                   if not context.get(f)]
    if missing_ctx:
        errors.append(f"promotion context identity 缺失: {missing_ctx} → "
                      f"PROMOTION_NOT_PROVEN")
        return errors
    for field in ("change_id", "release_id", "baseline_id"):
        if verdict.get(field) != context.get(field):
            errors.append(
                f"release verdict {field} 与上下文不一致"
                f"（{verdict.get(field)} != {context.get(field)}）")
    return errors


def require_evidence(evidence: dict, keys) -> list:
    missing = [k for k in keys if not evidence.get(k)]
    return [] if not missing else [f"missing evidence: {missing}"]


def _approval_hash(approval: dict) -> str:
    payload = {k: v for k, v in approval.items()
               if k not in ("approval_hash", "approval_nonce")}
    return _sha256(payload)


def _validate_human_approval(approval: dict, target_state: str,
                             context: dict, evidence: dict) -> list:
    """HUMAN-APPROVAL-2 Authority Artifact 校验（SF-5）。"""
    errors = []
    if not isinstance(approval, dict):
        return ["human approval artifact 缺失"]
    if approval.get("schema") != HUMAN_APPROVAL_SCHEMA:
        errors.append(f"schema != {HUMAN_APPROVAL_SCHEMA}")
    if approval.get("actor_type") != "HUMAN":
        errors.append(f"actor_type={approval.get('actor_type')} != HUMAN "
                      f"（AI 生成 Human Approval 禁止）")
    for field in ("approval_id", "approved_by", "approved_at",
                  "change_id", "release_id", "baseline_id",
                  "source_state", "target_state", "release_verdict_hash",
                  "evidence_manifest_hash", "approval_nonce"):
        if not approval.get(field):
            errors.append(f"human approval 缺 {field}")
    target_ok = approval.get("target_state") == target_state \
        or target_state in (approval.get("target_states") or [])
    if target_state == "PRODUCTION_DSS":
        target_ok = target_ok \
            or approval.get("production_promotion_authorized") is True
    if not target_ok:
        errors.append(f"approval target_state 不覆盖 {target_state}")
    if approval.get("source_state") \
            and approval.get("source_state") not in (
                "PRODUCTION_ELIGIBLE", "HUMAN_APPROVED"):
        errors.append(f"source_state={approval.get('source_state')} 非法")
    context = context or {}
    for field in ("change_id", "release_id", "baseline_id"):
        if context.get(field) and approval.get(field) != context.get(field):
            errors.append(f"human approval {field} 与上下文不一致"
                          f"（跨 Release/Baseline/Change 复用）")
    if approval.get("approval_hash") \
            and approval["approval_hash"] != _approval_hash(approval):
        errors.append("approval_hash 自校验失败")
    # 绑定 release_verdict.json
    verdict = (evidence or {}).get("release_verdict") or {}
    if not verdict:
        errors.append("evidence 缺少 release_verdict（无法绑定）")
    elif _sha256(verdict) != approval.get("release_verdict_hash"):
        errors.append("approval.release_verdict_hash 与 release_verdict 不一致")
    # 绑定 evidence_manifest.json
    manifest = (evidence or {}).get("evidence_manifest") or {}
    if not manifest:
        errors.append("evidence 缺少 evidence_manifest（无法绑定）")
    elif _sha256(manifest) != approval.get("evidence_manifest_hash"):
        errors.append("approval.evidence_manifest_hash 不一致")
    return errors


# 每条 Transition 的独立 Gate
TRANSITION_GATES = {
    ("DEVELOPMENT", "SOFTWARE_QUALIFIED"):
        lambda evidence, ctx: require_pure_judge(evidence, ctx),
    ("SOFTWARE_QUALIFIED", "RESEARCH_CANDIDATE"):
        lambda evidence, ctx: require_evidence(
            evidence, ("research_candidate",)),
    ("RESEARCH_CANDIDATE", "OOS_VALIDATED"):
        lambda evidence, ctx: require_evidence(evidence, ("oos",)),
    ("OOS_VALIDATED", "ABLATION_STRESS_VALIDATED"):
        lambda evidence, ctx: require_evidence(
            evidence, ("ablation", "stress")),
    ("ABLATION_STRESS_VALIDATED", "SHADOW"):
        lambda evidence, ctx: require_evidence(
            evidence, ("shadow_eligibility",)),
    ("SHADOW", "PRODUCTION_ELIGIBLE"):
        lambda evidence, ctx: require_evidence(
            evidence, ("shadow_evidence", "strategy_evidence")),
    ("PRODUCTION_ELIGIBLE", "HUMAN_APPROVED"):
        lambda evidence, ctx: _validate_human_approval(
            evidence.get("human_approval"), "HUMAN_APPROVED", ctx, evidence),
    ("HUMAN_APPROVED", "PRODUCTION_DSS"):
        lambda evidence, ctx: _validate_human_approval(
            evidence.get("human_approval"), "PRODUCTION_DSS", ctx, evidence),
}


def transition_gate(from_state: str, to_state: str,
                    evidence: dict = None,
                    context: dict = None) -> dict:
    """执行指定 Transition 的独立 Gate。"""
    evidence = evidence or {}
    context = context or {}
    if to_state not in ALLOWED_TRANSITIONS.get(from_state, set()):
        return {"allowed": False,
                "verdict": "TRANSITION_BLOCKED",
                "failed": [f"{from_state} → {to_state} 非邻接转移"],
                "rule": "只允许相邻状态推进（禁止跳级）"}
    gate = TRANSITION_GATES.get((from_state, to_state))
    if gate is None:
        return {"allowed": False, "verdict": "TRANSITION_BLOCKED",
                "failed": [f"未定义 {from_state} → {to_state} 的 Gate"]}
    failed = gate(evidence, context)
    return {
        "allowed": not failed,
        "verdict": "TRANSITION_OK" if not failed
        else "TRANSITION_BLOCKED",
        "failed": failed,
        "from_state": from_state,
        "to_state": to_state,
        "gate": f"{from_state}→{to_state}",
    }


def promotion_verdict(from_state: str, to_state: str,
                      evidence: dict = None,
                      context: dict = None) -> dict:
    """Promotion 判定（每步只执行该步所需 Gate）。"""
    gate = transition_gate(from_state, to_state, evidence, context)
    if not gate["allowed"]:
        return {"verdict": "PROMOTION_BLOCKED",
                "gate": gate,
                "rule": "Specification governs; AI proposes/builds; "
                        "Tests prove; Evidence records; Judge qualifies; "
                        "Human promotes"}
    return {
        "verdict": "PROMOTION_OK",
        "gate": gate,
        "from_state": from_state,
        "to_state": to_state,
        "human_required": to_state in AI_FORBIDDEN_STATES,
        "rule": "ChatGPT recommend/reject/request evidence；DeepSeek "
                "build/patch；Test System prove；Pure Judge qualify；"
                "Human promote",
    }


def promotion_verdict_artifact(from_state: str, to_state: str,
                               evidence: dict, context: dict,
                               out_dir) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict = promotion_verdict(from_state, to_state, evidence, context)
    (out_dir / "promotion_verdict.json").write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return verdict
