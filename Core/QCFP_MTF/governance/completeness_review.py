# coding: utf-8
"""Governance Completeness Review（QCFP-MTF 2.8：70 号治理完整性关门检查）

对 QCFP-MTF 1–70 做正式"关门检查"，逐条确认：
    非 Canonical 决策路径 / 重复 Permission authority /
    future-aware Production import / Report-side decision / mutable Ledger /
    hidden defaults / uncertified feature / legacy default /
    无法 Replay 的 Production Decision / 无法解释的人工 override

每项只输出四类结论：CLOSED / ACCEPTED RISK / ACTION REQUIRED / RETIRE。
只有当关键旁路全部 CLOSED，才进入长期稳定迭代模式。
"""


COMPLETENESS_CHECKS = (
    "non_canonical_decision_path",
    "duplicate_permission_authority",
    "future_aware_production_import",
    "report_side_decision",
    "mutable_ledger",
    "hidden_defaults",
    "uncertified_feature",
    "legacy_default",
    "non_replayable_production_decision",
    "unexplained_human_override",
)

VERDICTS = ("CLOSED", "ACCEPTED_RISK", "ACTION_REQUIRED", "RETIRE")


def governance_completeness_review(check_results: dict) -> dict:
    """check_results：{check: verdict} 或 {check: (verdict, evidence)}。"""
    results = {}
    for check in COMPLETENESS_CHECKS:
        v = check_results.get(check)
        if isinstance(v, tuple) and len(v) == 2:
            verdict, evidence = str(v[0]).upper(), str(v[1] or "")
        else:
            verdict, evidence = str(v or "").upper(), ""
        if verdict not in VERDICTS:
            verdict = "ACTION_REQUIRED"
            evidence = "缺少判定（默认视为需要行动）"
        results[check] = {"verdict": verdict, "evidence": evidence}
    action = [c for c, r in results.items()
              if r["verdict"] == "ACTION_REQUIRED"]
    retire = [c for c, r in results.items()
              if r["verdict"] == "RETIRE"]
    accepted = [c for c, r in results.items()
                if r["verdict"] == "ACCEPTED_RISK"]
    if action:
        overall = "ACTION_REQUIRED"
    elif retire:
        overall = "RETIRE"
    elif accepted:
        overall = "ACCEPTED_RISK"
    else:
        overall = "CLOSED"
    return {"checks": results, "action_required": action,
            "retire": retire, "accepted_risk": accepted,
            "overall": overall,
            "mode": ("长期稳定迭代" if overall == "CLOSED"
                     else "结构收口未完，禁止继续扩张")}


CLOSEOUT_KEY_ITEMS = (
    "non_canonical_decision_path",
    "duplicate_permission_authority",
    "future_aware_production_import",
    "report_side_decision",
    "mutable_ledger",
    "hidden_defaults",
    "uncertified_feature",
    "legacy_default",
    "non_replayable_production_decision",
    "unexplained_human_override",
)


def governance_closeout(check_results: dict,
                        test_count: int = 0,
                        feature_count: int = 0) -> dict:
    """新 70 号：真正的 1–70 Governance Closeout——
    只有关键项 CLOSED 才能宣布进入长期稳定维护模式；
    不能因为测试多、Feature 多就认为架构完成。"""
    review = governance_completeness_review(check_results)
    key_not_closed = [k for k in CLOSEOUT_KEY_ITEMS
                      if (review["checks"].get(k) or {})
                      .get("verdict") != "CLOSED"]
    closeout = "ENTER_LONG_TERM_MAINTENANCE" if not key_not_closed \
        else "NOT_CLOSED"
    return {
        "closeout": closeout,
        "key_items_not_closed": key_not_closed,
        "overall": review["overall"],
        "test_count": test_count,
        "feature_count": feature_count,
        "statement": ("测试数量与 Feature 数量不能替代治理关门；"
                      "只有关键项 CLOSED 才进入长期稳定维护模式"),
        "entered_maintenance": not key_not_closed,
    }
