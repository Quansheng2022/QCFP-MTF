# coding: utf-8
"""Zero-Trust Certification（QCFP-MTF 2.8：P0-4 硬门禁认证）

Hard Gates 先行：C1 Permission / C2 Risk / C3 PIT / C4 Replay /
C5 OOS / C6 Version——任一 FAIL → 立即 NOT CERTIFIED。
全部 PASS 后才计算 Quality Score（Data/Retail/Execution/Model Health）。

不是"18 项 17 项过 → 94 分 → Certified"。
"""


HARD_GATES = ("C1_permission", "C2_risk", "C3_pit", "C4_replay",
              "C5_oos", "C6_version")


def zero_trust_certification(hard_gates: dict, quality_scores: dict = None,
                             hard_weight=0.7) -> dict:
    """零信任认证。

    hard_gates：{C1_permission: bool, ...}（必须由 Evidence 产生）
    quality_scores：{data_quality: 0-100, retail_utility: ...}
    """
    failed = [g for g in HARD_GATES if not hard_gates.get(g)]
    if failed:
        return {
            "certified": False,
            "status": "NOT_CERTIFIED",
            "failed_hard_gates": failed,
            "quality_score": 0.0,
            "hard_gate_failed": True,
        }
    q = quality_scores or {}
    if q:
        quality = sum(float(v) for v in q.values()) / len(q)
    else:
        quality = 0.0
    return {
        "certified": True,
        "status": "CERTIFIED",
        "failed_hard_gates": [],
        "quality_score": round(quality, 2),
        "hard_gate_failed": False,
        "quality_breakdown": {k: round(float(v), 2)
                              for k, v in q.items()},
    }
