# coding: utf-8
"""Model Decision Surface Audit（QCFP-MTF 2.8：74 号决策面审计）

检查整个 Canonical 决策面是否存在异常"跳变区"：
小幅 Evidence 变化导致 target 从 10% 突然跳到 60%，
或 permission/watch/wave 交互产生不连续。

只做研究诊断，不自动平滑；只有 OOS/Ablation 证明稳定化有价值
时才允许改规则。
"""


def decision_surface_audit(perturbations) -> dict:
    """perturbations：[{"input_delta": 0.01, "target_delta": 0.5,
    "dimension": "evidence_x", "from_target":..., "to_target":...}]"""
    jump_events = []
    for p in perturbations or []:
        input_delta = abs(float(p.get("input_delta") or 0.0))
        target_delta = abs(float(p.get("target_delta") or 0.0))
        if input_delta <= 0.05 and target_delta > 0.30:
            jump_events.append({
                "dimension": p.get("dimension"),
                "input_delta": round(input_delta, 4),
                "target_delta": round(target_delta, 4),
                "from_target": p.get("from_target"),
                "to_target": p.get("to_target"),
            })
    total = len(perturbations or [])
    index = round(len(jump_events) / total, 4) if total else None
    return {
        "total_perturbations": total,
        "jump_events": jump_events,
        "jump_count": len(jump_events),
        "surface_stability_index": index,
        "verdict": "REVIEW" if jump_events else "STABLE",
        "auto_smooth_forbidden": True,
        "note": "只做研究诊断；只有 OOS/Ablation 证明稳定化有价值"
                "才允许改规则",
    }


def cliff_classification(perturbation: dict,
                         permission_changed: bool = False) -> dict:
    """新 74 号：异常决策面必须说明是设计上的硬边界还是模型脆弱性。

        EXPECTED_GOVERNANCE_CLIFF   权限/治理规则导致的硬边界（合理）
        UNEXPECTED_MODEL_CLIFF      模型脆弱性（需审查）
        STATE_FLAPPING              状态高频来回
    """
    if permission_changed:
        return {"classification": "EXPECTED_GOVERNANCE_CLIFF",
                "reason": "Permission ALLOW→BLOCK 等治理硬边界导致的跳变合理",
                "review_required": False}
    input_delta = abs(float(perturbation.get("input_delta") or 0.0))
    target_delta = abs(float(perturbation.get("target_delta") or 0.0))
    flapping = bool(perturbation.get("flapping"))
    if flapping:
        return {"classification": "STATE_FLAPPING",
                "reason": "状态高频来回 → 需审查状态机",
                "review_required": True}
    if input_delta <= 0.05 and target_delta > 0.30:
        return {"classification": "UNEXPECTED_MODEL_CLIFF",
                "reason": "小幅输入导致大幅跳变且非治理边界 → 模型脆弱性",
                "review_required": True}
    return {"classification": "NORMAL",
            "reason": "无异常跳变",
            "review_required": False}
