# coding: utf-8
"""Research Debt Register（QCFP-MTF 2.8：78 号研究债务登记）

防止未验证想法永久堆在代码里。未完成研究项只能处于：
    HYPOTHESIS / EXPERIMENTAL / VALIDATED / REJECTED / RETIRED

验收标准：超过两个版本周期仍无实验结果的 EXPERIMENTAL feature，
默认进入 DELETE/ARCHIVE review。
"""


RESEARCH_STATES = ("HYPOTHESIS", "EXPERIMENTAL", "VALIDATED",
                   "REJECTED", "RETIRED")


def research_debt_register(features: dict,
                           experimental_cycle_limit: int = 2) -> dict:
    """features：{feature: {"state":..., "cycles_in_state": n}}"""
    results, expired = {}, []
    for feature, attrs in (features or {}).items():
        attrs = attrs or {}
        state = str(attrs.get("state") or "HYPOTHESIS").upper()
        if state not in RESEARCH_STATES:
            state = "HYPOTHESIS"
        cycles = int(attrs.get("cycles_in_state") or 0)
        entry = {"state": state,
                 "cycles_in_state": cycles,
                 "expired_experimental": False}
        if state == "EXPERIMENTAL" \
                and cycles >= experimental_cycle_limit:
            entry["expired_experimental"] = True
            entry["action"] = "DELETE_ARCHIVE_REVIEW"
            expired.append(feature)
        results[feature] = entry
    return {
        "results": results,
        "expired_experimental": expired,
        "rule": "EXPERIMENTAL 超过两个版本周期无实验结果 "
                "→ 默认进入 DELETE/ARCHIVE review",
        "no_half_finished_states": True,
    }


def experimental_feature_aging_report(features: dict,
                                      oos_results: dict = None) -> dict:
    """新 78 号：每个 Release 跑一次 Experimental Feature Aging——
    EXPERIMENTAL 不能成为永久状态。"""
    oos_results = oos_results or {}
    report = {}
    for feature, attrs in (features or {}).items():
        attrs = attrs or {}
        state = str(attrs.get("state") or "HYPOTHESIS").upper()
        cycles = int(attrs.get("cycles_in_state") or 0)
        oos = oos_results.get(feature)
        if state == "REJECTED":
            action = "REJECTED"
        elif state == "RETIRED":
            action = "RETIRED"
        elif state == "VALIDATED":
            action = "VALIDATED"
        elif state == "EXPERIMENTAL" and cycles >= 2:
            action = "DELETE_REVIEW"
        elif state == "EXPERIMENTAL":
            action = "KEEP_EXPERIMENTAL"
        else:
            action = "KEEP_EXPERIMENTAL"
        if oos is False:
            action = "REJECTED"
        report[feature] = {"state": state,
                           "cycles_in_state": cycles,
                           "action": action,
                           "permanent_experimental": False}
    return {"report": report,
            "delete_review": [f for f, r in report.items()
                              if r["action"] == "DELETE_REVIEW"],
            "rule": "EXPERIMENTAL 不能成为永久状态，"
                    "否则 Research 区也会无限膨胀"}
