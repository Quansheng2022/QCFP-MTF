# coding: utf-8
"""Execution Reality Calibration（QCFP-MTF 2.8：45 号执行现实校准）

用真实 Shadow/Paper 数据校准执行假设：
    Estimated vs Realized Slippage / Exit Days / Participation

ExecutionModelError；连续样本长期偏移 → 只进入 Research Review，
不允许自动修改 Production 参数。
"""


def execution_model_error(estimated, realized, dim="slippage") -> dict:
    """单样本执行误差。"""
    e = float(estimated or 0.0)
    r = float(realized or 0.0)
    if e == 0:
        err = None
    else:
        err = (r - e) / abs(e)
    return {"dimension": dim, "estimated": round(e, 6),
            "realized": round(r, 6),
            "error_ratio": round(err, 4) if err is not None else None,
            "pessimistic": bool(err is not None and err < -0.1),
            "optimistic": bool(err is not None and err > 0.1)}


def execution_calibration_report(samples: list) -> dict:
    """样本聚合：各维度平均误差 + 长期偏移判定。"""
    dims = {}
    for s in samples:
        dim = s.get("dimension") or "slippage"
        r = execution_model_error(s.get("estimated"), s.get("realized"), dim)
        dims.setdefault(dim, []).append(r["error_ratio"])
    summary = {}
    for dim, errors in dims.items():
        valid = [e for e in errors if e is not None]
        if valid:
            mean = sum(valid) / len(valid)
            summary[dim] = {
                "n": len(valid),
                "mean_error_ratio": round(mean, 4),
                "bias": "OPTIMISTIC" if mean > 0.05 else
                "PESSIMISTIC" if mean < -0.05 else "NEUTRAL",
            }
    return {
        "dimensions": summary,
        "research_review_required": any(
            v["bias"] != "NEUTRAL" for v in summary.values()),
        "auto_param_modify_forbidden": True,
        "note": "执行误差长期偏移 → Research Review，"
                "不允许自动修改 Production 参数",
    }


def execution_calibration_downgrade(report: dict) -> dict:
    """新 26 号：执行模型长期偏乐观 → 降级认证，不假装成本真实。"""
    optimistic = [d for d, v in (report.get("dimensions") or {}).items()
                  if v.get("bias") == "OPTIMISTIC"]
    if optimistic:
        return {"verdict": "CERTIFICATION_DOWNGRADED",
                "optimistic_dimensions": optimistic,
                "guidance": "执行假设长期偏乐观 → 降级认证，"
                            "只走 Detect→Review→Candidate→Shadow",
                "auto_recalibrate_forbidden": True}
    return {"verdict": "CERTIFICATION_STABLE",
            "optimistic_dimensions": [],
            "guidance": "执行假设与真实 Shadow/Paper 一致",
            "auto_recalibrate_forbidden": True}
