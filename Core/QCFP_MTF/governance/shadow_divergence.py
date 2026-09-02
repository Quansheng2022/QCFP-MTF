# coding: utf-8
"""Shadow–Production Divergence Monitor（QCFP-MTF 2.8：36 号变化监视器）

持续比较 ShadowProposal vs ProductionDecision，回答两者为何不同：
    MODEL_DELTA / CONFIG_DELTA / DATA_DELTA / GOVERNANCE_INTERCEPTION /
    VERSION_DELTA

同一 Evidence 下 Shadow 与 Production 差异无法解释 → 治理告警。
"""


def shadow_divergence_monitor(shadow, production, context=None) -> dict:
    """shadow/production：{target_position, permission, version,
    config_hash, data_snapshot_id, engine_version}"""
    st = float(shadow.get("target_position") or 0.0)
    pt = float(production.get("target_position") or 0.0)
    ctx = context or {}
    classifications = []
    if st != pt:
        if shadow.get("permission") != production.get("permission"):
            classifications.append("GOVERNANCE_INTERCEPTION")
        elif shadow.get("config_hash") != production.get("config_hash"):
            classifications.append("CONFIG_DELTA")
        elif shadow.get("data_snapshot_id") != \
                production.get("data_snapshot_id"):
            classifications.append("DATA_DELTA")
        elif shadow.get("version") != production.get("version") \
                or shadow.get("engine_version") != \
                production.get("engine_version"):
            classifications.append("VERSION_DELTA")
        else:
            classifications.append("MODEL_DELTA")
    explained = bool(classifications) or abs(st - pt) < 1e-9
    return {
        "shadow_target": round(st, 4),
        "production_target": round(pt, 4),
        "target_delta": round(pt - st, 4),
        "divergence_classifications": classifications,
        "explained": explained,
        "governance_alert": bool(classifications
                                 and "GOVERNANCE_INTERCEPTION"
                                 not in classifications
                                 and not ctx.get("expected_delta")),
        "note": "无法解释的 Shadow/Production 差异必须触发治理告警",
    }


def shadow_divergence_reason(shadow, production) -> dict:
    """新 36 号：每次 divergence 必须有 reason_code + decision_delta，
    而不是只记录"不同"。"""
    st = float(shadow.get("target_position") or 0.0)
    pt = float(production.get("target_position") or 0.0)
    delta = round(pt - st, 4)
    if abs(delta) < 1e-9:
        return {"reason_code": "NO_DIVERGENCE",
                "decision_delta": 0.0, "diverged": False}
    if shadow.get("permission") != production.get("permission"):
        code = "GOVERNANCE_INTERCEPTION"
    elif shadow.get("config_hash") != production.get("config_hash"):
        code = "CONFIG_DELTA"
    elif shadow.get("data_snapshot_id") != \
            production.get("data_snapshot_id"):
        code = "DATA_DELTA"
    elif shadow.get("version") != production.get("version") \
            or shadow.get("engine_version") != \
            production.get("engine_version"):
        code = "VERSION_DELTA"
    elif shadow.get("execution_cap") != production.get("execution_cap"):
        code = "EXECUTION_CONSTRAINT"
    else:
        code = "MODEL_DELTA"
    return {"reason_code": code, "decision_delta": delta,
            "diverged": True}
