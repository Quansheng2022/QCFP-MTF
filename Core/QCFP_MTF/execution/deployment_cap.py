# coding: utf-8
"""DeploymentCap（Runtime Evidence Wiring：第 7 项）

Small-Live 的 Deployment Risk Ceiling——放在 Canonical Decision 之后：
    Canonical FinalTarget → DeploymentCap → DeploymentTarget

硬不变量：
    DeploymentTarget <= CanonicalTarget
    DeploymentCap 不能改变 Permission/Wave/FSM/CanonicalAction，
    不能提高 Target；Hard Exit（Canonical=0）时 Deployment 必须 =0，
    不能阻止风险退出。

必须同时保存两个数字：CanonicalTarget 与 DeploymentTarget 不可合并。

Runtime Evidence Wiring 修改：
    * 0 <= canonical_target <= 1；0 <= deployment_cap <= approved_max；
      负 Cap / 负 target → INVALID_DEPLOYMENT_CAP（不是数学不变量）；
    * 删除 executed_target 字段——DeploymentTarget ≠ ExecutedTarget，
      ActualFill/Executed 只能来自 Runtime Event/Broker；
    * Cap 只能来自 signed deployment config（approved_max 参数），
      禁止运行时自动上调。
"""


def deployment_target(canonical_target, deployment_cap,
                      approved_max=1.0) -> dict:
    """DeploymentTarget = min(CanonicalTarget, DeploymentCap)。

    approved_max：Governance 批准的 Cap 上限（signed deployment config）。
    负值/超上限 → INVALID_DEPLOYMENT_CAP。"""
    canonical = float(canonical_target if canonical_target is not None
                      else 0.0)
    cap = float(deployment_cap if deployment_cap is not None else 0.0)
    max_cap = float(approved_max if approved_max is not None else 1.0)
    if canonical < -1e-9 or canonical > 1.0 + 1e-9:
        return {"valid": False, "reason": "INVALID_CANONICAL_TARGET",
                "canonical_target": round(canonical, 4),
                "deployment_cap": round(cap, 4),
                "approved_max": round(max_cap, 4),
                "deployment_target": None,
                "rule": "Long-only 体系：0 <= canonical_target <= 1"}
    if cap < -1e-9 or cap > max_cap + 1e-9:
        return {"valid": False, "reason": "INVALID_DEPLOYMENT_CAP",
                "canonical_target": round(canonical, 4),
                "deployment_cap": round(cap, 4),
                "approved_max": round(max_cap, 4),
                "deployment_target": None,
                "rule": "0 <= deployment_cap <= approved_max；"
                        "负 Cap / 超上限直接 INVALID"}
    target = min(canonical, cap)
    return {
        "valid": True,
        "canonical_target": round(canonical, 4),
        "deployment_cap": round(cap, 4),
        "approved_max": round(max_cap, 4),
        "deployment_target": round(target, 4),
        "invariant_ok": target <= canonical + 1e-9,
        "rule": "DeploymentTarget <= CanonicalTarget；"
                "Cap 不能提高 Target 或阻止风险退出；"
                "ExecutedTarget 只能来自 Fill/Broker，"
                "本层不产生 executed_target",
    }


def assert_deployment_invariant(result: dict) -> dict:
    ok = bool(result.get("valid")) and bool(result.get("invariant_ok"))
    return {"verdict": "DEPLOYMENT_OK" if ok
            else "DEPLOYMENT_INVARIANT_FAIL",
            "ok": ok}


def deployment_cap_authority_boundary(cap: dict) -> dict:
    """DeploymentCap 不得改变决策层字段。"""
    changed = [k for k in ("permission", "wave", "fsm", "action")
               if cap.get(k) is not None]
    return {"changed_decision_fields": changed,
            "violation": bool(changed),
            "rule": "DeploymentCap 只减权，不改变 Canonical Decision"}
