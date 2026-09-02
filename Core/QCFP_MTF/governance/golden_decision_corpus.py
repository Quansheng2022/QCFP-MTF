# coding: utf-8
"""Golden Decision Corpus（QCFP-MTF 2.8：新 42 号）

把 Golden Tests 升级成数量有限、永久保留的 Golden Decision Corpus，
覆盖：
    Permission: BLOCK / WATCH / TEST / ALLOW / STRONG_ALLOW
    Wave:      DISCOVERY / ACTIVE / MATURE / INVALID
    Events:    Hard Exit / Liquidity binding / Portfolio binding /
               PIT failure / Replay failure / Safe Mode

每个 Case 保存 EvidenceSnapshot / ReleaseManifest /
Expected DecisionSnapshot / Expected DecisionHash。

验收标准：Critical Golden Case 的 DecisionHash 变化必须进入
Change Impact Review，不能只是"测试结果更新了"。
"""

import hashlib
import json


GOLDEN_CORPUS = (
    # (case_id, permission, wave_stage, event)
    ("G_BLOCK_STRONG", "BLOCK", "ACTIVE", "NONE"),
    ("G_WATCH_OBSERVE", "WATCH", "ACTIVE", "NONE"),
    ("G_TEST_LIMITED", "TEST", "ACTIVE", "NONE"),
    ("G_ALLOW_TRADE", "ALLOW", "ACTIVE", "NONE"),
    ("G_STRONG_ALLOW", "STRONG_ALLOW", "ACTIVE", "NONE"),
    ("G_WAVE_DISCOVERY", "ALLOW", "DISCOVERY", "NONE"),
    ("G_WAVE_MATURE", "ALLOW", "MATURE", "NONE"),
    ("G_WAVE_INVALID", "ALLOW", "INVALID", "NONE"),
    ("G_HARD_EXIT", "ALLOW", "ACTIVE", "HARD_EXIT"),
    ("G_LIQUIDITY_BINDING", "ALLOW", "ACTIVE", "LIQUIDITY_CAP"),
    ("G_PORTFOLIO_BINDING", "ALLOW", "ACTIVE", "PORTFOLIO_CAP"),
    ("G_PIT_FAILURE", "ALLOW", "ACTIVE", "PIT_FAILURE"),
    ("G_REPLAY_FAILURE", "ALLOW", "ACTIVE", "REPLAY_FAILURE"),
    ("G_SAFE_MODE", "ALLOW", "ACTIVE", "SAFE_MODE"),
)


def golden_case_hash(case: dict) -> str:
    """Expected DecisionHash：case 全字段内容哈希。"""
    raw = json.dumps(case, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def golden_decision_corpus() -> dict:
    """Golden Corpus 定义：每个 case 带 case_id / 覆盖维度 / 空结果占位。"""
    cases = {}
    for case_id, perm, wave, event in GOLDEN_CORPUS:
        case = {"case_id": case_id, "permission": perm,
                "wave_stage": wave, "event": event,
                "evidence_snapshot": None,
                "release_manifest": None,
                "expected_decision_snapshot": None,
                "expected_decision_hash": ""}
        case["expected_decision_hash"] = golden_case_hash(case)
        cases[case_id] = case
    return {"corpus": cases, "n_cases": len(cases),
            "rule": "Golden DecisionHash 变化必须进入 Change Impact Review"}


def golden_change_requires_review(previous_hash, current_hash,
                                  case_id) -> dict:
    """新 42 号：Critical Golden Case 变化 → Change Impact Review。"""
    changed = previous_hash != current_hash
    return {"case_id": case_id,
            "previous_hash": previous_hash,
            "current_hash": current_hash,
            "changed": changed,
            "requires_change_impact_review": changed,
            "rule": "不能只是'测试结果更新了'，必须解释为什么改变"}


def golden_release_gate(changes: list) -> dict:
    """Release 2（新 14 号）：Golden Corpus 成为 Release Gate——
    Golden Hash 变化必须全部有批准的 Change Reason，否则 Release 阻塞。"""
    unexplained = []
    for change in changes or []:
        if change.get("changed") and not change.get("approved_reason"):
            unexplained.append(change.get("case_id"))
    return {
        "unexplained_changes": unexplained,
        "verdict": "RELEASE_OK" if not unexplained
        else "GOLDEN_CHANGE_UNEXPLAINED",
        "allowed": not unexplained,
        "rule": "Golden Corpus 100% explained——所有变化都必须有批准的 "
                "Change Reason，不能只是'更新 expected 值'",
    }
