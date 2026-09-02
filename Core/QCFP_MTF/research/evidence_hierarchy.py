# coding: utf-8
"""Evidence Hierarchy（QCFP-MTF 2.8：93 号研究证据等级）

明确不同研究证据的权重：
    L0 Theory / intuition
    L1 In-sample observation
    L2 Backtest
    L3 Walk-forward / OOS
    L4 Ablation + Stress
    L5 Shadow / Paper
    L6 Production evidence

低等级证据只能产生 Hypothesis，不能直接产生 Production Change。
每个 Feature 的 ACTIVE 状态必须附最小 Evidence Level。
"""


EVIDENCE_LEVELS = {
    0: "THEORY",
    1: "IN_SAMPLE",
    2: "BACKTEST",
    3: "OOS_WALK_FORWARD",
    4: "ABLATION_STRESS",
    5: "SHADOW_PAPER",
    6: "PRODUCTION",
}

MIN_EVIDENCE_FOR = {
    "HYPOTHESIS": 0,
    "CANDIDATE": 2,
    "SHADOW": 3,
    "PRODUCTION": 4,
}


def evidence_level_check(feature, evidence_level,
                         target="PRODUCTION") -> dict:
    """Feature 的 ACTIVE 状态必须有足够证据等级。"""
    level = int(evidence_level or 0)
    required = MIN_EVIDENCE_FOR.get(target, 4)
    ok = level >= required
    return {
        "feature": feature,
        "evidence_level": level,
        "level_name": EVIDENCE_LEVELS.get(level, "UNKNOWN"),
        "target": target,
        "required_level": required,
        "ok": ok,
        "verdict": "ALLOWED" if ok else "INSUFFICIENT",
        "rule": "低等级证据只能产生 Hypothesis，"
                "不能直接产生 Production Change",
    }


def evidence_level_lifecycle(evidence_level) -> dict:
    """新 93 号：不同等级证据拥有不同权力——
        L0–L1 → HYPOTHESIS
        L2    → CANDIDATE
        L3    → SHADOW candidate
        L4+   → Production eligibility
        L5/L6 → 持续认证证据
    """
    level = int(evidence_level or 0)
    if level <= 1:
        lifecycle = "HYPOTHESIS"
    elif level == 2:
        lifecycle = "CANDIDATE"
    elif level == 3:
        lifecycle = "SHADOW_CANDIDATE"
    elif level >= 5:
        lifecycle = "SUSTAINING_CERTIFICATION"
    else:
        lifecycle = "PRODUCTION_ELIGIBLE"
    return {"evidence_level": level,
            "level_name": EVIDENCE_LEVELS.get(level, "UNKNOWN"),
            "lifecycle": lifecycle,
            "production_power": level >= 4,
            "rule": "不允许'逻辑上非常合理'直接升级成 Production Rule"}


def active_feature_evidence_required(feature, evidence_level) -> dict:
    """新 93 号：每个 ACTIVE Production Feature 必须回答
    Current Evidence Level = ?；没有 → RESEARCH_ONLY。"""
    if evidence_level is None:
        return {"feature": feature, "evidence_level": None,
                "verdict": "RESEARCH_ONLY",
                "production_allowed": False,
                "rule": "ACTIVE Feature 必须附最小 Evidence Level"}
    lifecycle = evidence_level_lifecycle(evidence_level)
    return {"feature": feature,
            "evidence_level": evidence_level,
            "verdict": "ACTIVE_OK" if lifecycle[
                "production_power"] else "RESEARCH_ONLY",
            "production_allowed": lifecycle["production_power"]}
