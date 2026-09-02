# coding: utf-8
"""Historical Decision Integrity Test（QCFP-MTF 2.8：89 号历史事实完整性）

Ledger 保证：升级代码后历史事实不能偷偷改变。
每个 Production Release 选择冻结历史日期，区分：
    Historical Fact / Historical Replay under old release /
    Counterfactual under new release

验收标准：历史 CanonicalDecision 不可变；
新模型只能生成 counterfactual_decision，不能修改历史事实。
"""


def historical_decision_integrity(frozen_fact: dict,
                                  old_release_replay: dict,
                                  new_release_counterfactual: dict
                                  = None) -> dict:
    """frozen_fact：历史冻结事实；old_release_replay：旧版本重放；
    new_release_counterfactual：新版本反事实（必须独立保存）。"""
    consistent = frozen_fact == old_release_replay
    return {
        "historical_fact": frozen_fact,
        "old_release_replay": old_release_replay,
        "old_replay_consistent": consistent,
        "new_release_counterfactual": new_release_counterfactual,
        "historical_fact_immutable": True,
        "counterfactual_separate": True,
        "verdict": "INTEGRITY_OK" if consistent
        else "INTEGRITY_FAILED",
        "rule": "新模型只能生成 counterfactual_decision，"
                "不能修改历史事实",
    }


def assert_historical_fact_immutable(ledger_operations) -> dict:
    """新 46 号：Ledger 只能追加（INSERT/APPEND），
    任何 UPDATE/DELETE 都算历史事实被改写。"""
    violations = []
    for op in ledger_operations or []:
        kind = str(op.get("kind") or "").upper()
        if kind in ("UPDATE", "DELETE", "REPLACE"):
            violations.append(op)
    return {
        "operations": list(ledger_operations or []),
        "violations": violations,
        "append_only": not violations,
        "verdict": "HISTORY_IMMUTABLE" if not violations
        else "HISTORY_MUTATED",
        "rule": "新知识可以重新评价历史，不能重新书写历史",
    }


def release_historical_replay_check(frozen_hash, replayed_hash,
                                    migration_event=None) -> dict:
    """新 89 号：升级代码后历史 CanonicalDecisionHash 变化 =
    release failure，除非明确记录 migration/correction event
    （而不是修改历史事实）。"""
    changed = frozen_hash != replayed_hash
    recorded = bool(migration_event)
    if changed and not recorded:
        return {"verdict": "RELEASE_FAILURE",
                "reason": "历史 CanonicalDecisionHash 变化且无 "
                          "migration/correction event → release failure",
                "allowed": False}
    if changed and recorded:
        return {"verdict": "MIGRATION_RECORDED",
                "reason": "历史变化已记录为 migration/correction event",
                "allowed": True}
    return {"verdict": "HISTORY_PRESERVED",
            "reason": "历史决策哈希完全不变",
            "allowed": True}


# Release 3（新 22 号）：Historical Integrity Corpus——固定历史保护测试
HISTORICAL_INTEGRITY_CORPUS = (
    "bull", "bear", "sideways", "crash",
    "high_liquidity", "low_liquidity",
    "permission_block", "strong_wave", "hard_exit",
)


def historical_integrity_corpus_check(cases: dict) -> dict:
    """每个历史 case 保存 EvidenceSnapshotID/ReleaseID/DecisionHash/
    FinalTarget/Action/BindingConstraint/LedgerHash；
    历史事实静默变化数量必须 = 0。"""
    required = ("evidence_snapshot_id", "release_id", "decision_hash",
                "final_target", "action", "binding_constraint",
                "ledger_hash")
    mutations = []
    for case_id in HISTORICAL_INTEGRITY_CORPUS:
        case = (cases or {}).get(case_id) or {}
        missing = [f for f in required if case.get(f) is None]
        if missing:
            mutations.append({"case": case_id, "missing": missing})
        elif case.get("silently_mutated"):
            mutations.append({"case": case_id,
                              "reason": "历史事实静默变化"})
    return {
        "corpus_cases": list(HISTORICAL_INTEGRITY_CORPUS),
        "silent_mutations": mutations,
        "silent_mutation_count": len(mutations),
        "verdict": "HISTORY_PROTECTED" if not mutations
        else "HISTORY_MUTATED",
        "rule": "历史事实静默变化数量 = 0；新版本只能 Counterfactual",
    }
