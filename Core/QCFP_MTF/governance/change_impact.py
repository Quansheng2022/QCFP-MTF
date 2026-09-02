# coding: utf-8
"""Change Impact Matrix（QCFP-MTF 2.8：38 号变更影响矩阵）

任何修改先说明影响哪条权力链：
    Evidence / Permission / Wave / FSM / Risk / Portfolio / Execution /
    Ledger / Report / Research-only

改变 Permission / Final Target / PIT / Decision Schema →
自动提高 validation requirement（小改 README 与修改 permission cap
不走同一条发布流程）。
"""


IMPACT_AREAS = ("Evidence", "Permission", "Wave", "FSM", "Risk",
                "Portfolio", "Execution", "Ledger", "Report",
                "Research-only")


def change_impact_matrix(change: dict) -> dict:
    """change：{change_type, touches: [areas], description}"""
    touches = set(change.get("touches") or ())
    affected = [a for a in IMPACT_AREAS if a in touches]
    critical = touches & {"Permission", "FinalTarget", "PIT",
                          "DecisionSchema"}
    only_research = affected and set(affected) == {"Research-only"}
    validation = "FULL_VALIDATION" if critical else \
        "STANDARD_VALIDATION" if affected and not only_research else "LOW"
    return {
        "change_type": change.get("change_type"),
        "description": change.get("description", ""),
        "affected_areas": affected,
        "unaffected": [a for a in IMPACT_AREAS if a not in touches],
        "critical_touches": sorted(critical),
        "validation_requirement": validation,
        "release_track": "HIGH" if critical else
        "STANDARD" if affected and not only_research else "LOW",
    }


def assert_change_reviewed(impact: dict) -> None:
    """关键影响（Permission/FinalTarget/PIT/Schema）未走 FULL_VALIDATION
    → 拒绝发布。"""
    if impact["critical_touches"] and \
            impact["validation_requirement"] != "FULL_VALIDATION":
        raise ValueError(
            f"Change Impact：关键变更 {impact['critical_touches']} "
            f"必须 FULL_VALIDATION")


FULL_VALIDATION_EVIDENCE = ("pit", "oos", "ablation", "replay", "shadow")


def change_impact_release_gate(impacts: list,
                               full_validation_evidence: dict = None) -> dict:
    """新 15 号：Change Impact Matrix 升级为实际 Release Gate。

    关键变更（Permission/FinalTarget/PIT/DecisionSchema）必须：
        - 有 ChangeImpactRecord（validation_requirement=FULL_VALIDATION）
        - 全套 PIT/OOS/Ablation/Replay/Shadow 证据通过
    否则 Promotion 直接失败。
    """
    evidence = full_validation_evidence or {}
    blocked = []
    for impact in impacts or []:
        critical = bool(impact.get("critical_touches"))
        if not critical:
            continue
        record_ok = impact.get("validation_requirement") == \
            "FULL_VALIDATION"
        missing = [g for g in FULL_VALIDATION_EVIDENCE
                   if not evidence.get(g)]
        if not record_ok or missing:
            blocked.append({
                "change_type": impact.get("change_type"),
                "critical_touches": impact.get("critical_touches"),
                "record_ok": record_ok,
                "missing_evidence": missing,
            })
    return {
        "blocked": blocked,
        "promotion": "ALLOW" if not blocked else "FAIL",
        "verdict": "RELEASE_GATE_PASS" if not blocked
        else "RELEASE_GATE_FAIL",
        "rule": "关键变更无 ChangeImpactRecord + Full Validation "
                "→ Release Promotion 直接失败",
    }


def change_blast_radius(change: dict, historical_decisions,
                        decision_diffs: dict = None) -> dict:
    """新 38 号：Change Blast Radius——每次关键改动明确
    影响哪些层 / 多少历史 Decision / 哪些 Report / Replay / Certificate。"""
    impact = change_impact_matrix(change)
    n_total = len(historical_decisions or [])
    affected = int(change.get("affected_decisions")
                   if change.get("affected_decisions") is not None
                   else n_total)
    affected_ratio = round(affected / n_total, 4) if n_total else None
    return {
        "change_type": change.get("change_type"),
        "affected_layers": impact["affected_areas"],
        "affected_decisions": affected,
        "affected_ratio": affected_ratio,
        "decision_flips": dict(decision_diffs or {}),
        "affected_reports": change.get("affected_reports") or [],
        "affected_replays": change.get("affected_replays") or [],
        "affected_certificates": change.get("affected_certificates") or [],
        "validation_requirement": impact["validation_requirement"],
        "requires_decision_impact_report": bool(
            impact["critical_touches"]),
    }


def decision_impact_report(change: dict, historical_decisions,
                           decision_diffs: dict = None) -> dict:
    """新 38 号：任何关键 Release 必须带 Decision Impact Report。"""
    blast = change_blast_radius(change, historical_decisions,
                                decision_diffs)
    return {"report": "DECISION_IMPACT_REPORT",
            "content": blast,
            "required": blast["requires_decision_impact_report"]}
