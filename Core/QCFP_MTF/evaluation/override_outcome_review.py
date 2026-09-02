# coding: utf-8
"""Override Outcome Review（QCFP-MTF 2.8：62 号人工干预价值评估）

统计 Canonical outcome vs Actual overridden outcome，
把人工干预分类为：避免损失 / 错过收益 / 提前退出 / 错误干预。

铁律：人工干预既不能天然被认为"更聪明"，也不能天然被认为"错误"；
必须通过 Outcome Evidence 评估，且属于 Research，
不允许自动学习后修改 Production。
"""


OVERRIDE_OUTCOME_CLASSES = ("avoided_loss", "missed_gain",
                            "premature_exit", "wrong_intervention")


def override_outcome_review(records) -> dict:
    """records：[{"class": ..., "canonical_return": ..., "actual_return": ...,
                  "delta": ...}] 或 [{"class": ...}]"""
    counts = {k: 0 for k in OVERRIDE_OUTCOME_CLASSES}
    deltas = []
    for r in records or []:
        cls = r.get("class")
        if cls in counts:
            counts[cls] += 1
        if r.get("canonical_return") is not None \
                and r.get("actual_return") is not None:
            deltas.append(float(r["actual_return"])
                          - float(r["canonical_return"]))
    total = sum(counts.values())
    mean_delta = round(sum(deltas) / len(deltas), 4) if deltas else None
    return {"counts": counts, "total_overrides": total,
            "mean_actual_minus_canonical": mean_delta,
            "research_only": True,
            "auto_production_modify_forbidden": True}


def override_value_verdict(review: dict) -> dict:
    """证据判定：HELPFUL / HARMFUL / NEUTRAL / INCONCLUSIVE。"""
    counts = review.get("counts") or {}
    total = review.get("total_overrides") or 0
    if total == 0:
        return {"verdict": "INCONCLUSIVE",
                "guidance": "无人工干预样本"}
    helpful = counts.get("avoided_loss", 0)
    harmful = counts.get("wrong_intervention", 0) \
        + counts.get("premature_exit", 0) \
        + counts.get("missed_gain", 0)
    if helpful >= 3 and helpful > harmful * 2:
        return {"verdict": "HELPFUL",
                "guidance": "人工干预整体避免了损失"}
    if harmful >= 3 and harmful > helpful * 2:
        return {"verdict": "HARMFUL",
                "guidance": "人工干预整体降低了结果"}
    mean = review.get("mean_actual_minus_canonical")
    if mean is not None and abs(mean) < 0.005:
        return {"verdict": "NEUTRAL",
                "guidance": "人工干预结果与 Canonical 相当"}
    return {"verdict": "INCONCLUSIVE",
            "guidance": "样本不足，无法给出结论"}


def override_quarterly_review(override_records) -> dict:
    """新 62 号：每季度回答"人工干预总体是增加价值还是增加噪声"。

    长期统计 Override count / Avoided loss / Missed gain /
    Wrong intervention / Net override value；结果只进入
    Research Evidence + Human Review，不能自动提高人工权限。
    """
    records = list(override_records or [])
    counts = {"avoided_loss": 0, "missed_gain": 0,
              "wrong_intervention": 0, "premature_exit": 0}
    net_value = 0.0
    for r in records:
        cls = r.get("class")
        if cls in counts:
            counts[cls] += 1
        net_value += float(r.get("value_delta") or 0.0)
    return {
        "override_count": len(records),
        "counts": counts,
        "net_override_value": round(net_value, 4),
        "verdict": "ADDING_VALUE" if net_value > 0 and len(records) >= 3
        else "ADDING_NOISE" if net_value < 0 and len(records) >= 3
        else "INCONCLUSIVE",
        "evidence_store": "RESEARCH_EVIDENCE",
        "human_review_required": True,
        "auto_permission_increase_forbidden": True,
        "auto_production_modify_forbidden": True,
        "rule": "人工连续几次成功 ≠ 自动提高人工权限",
    }
