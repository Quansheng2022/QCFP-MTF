# coding: utf-8
"""Continuous Validation + Safety State（QCFP-MTF 2.8：30 号持续验证与熔断）

把各类监控（数据/模型/权限/波段/执行/流动性/MFE-MAE/假进场/治理/
台账/回放/风险）聚合为安全状态：
    NORMAL → WARNING → SAFE_MODE → HALTED

系统级优先权（不可被 Wave/Permission/Strategy 覆盖）：
    Ledger Failure / Replay Mismatch  → HALTED
    PIT Failure / Data Failure / Governance Failure → SAFE_MODE
    Risk Breach / Drift / 绩效劣化      → WARNING
"""

from dataclasses import asdict, dataclass, field

from .kill_switch import evaluate_safety, safety_gate


EXTRA_CHECKS = {
    "permission_drift": "WARNING",
    "wave_perf_degraded": "WARNING",
    "liquidity_low": "WARNING",
    "mfe_mae_biased": "WARNING",
    "false_entry_high": "WARNING",
    "governance_failure": "SAFE_MODE",
    "unknown_production_evidence": "SAFE_MODE",
}


@dataclass(frozen=True)
class ContinuousValidationResult:
    status: str
    triggered: tuple
    degraded_metrics: dict
    recommendations: tuple

    def as_dict(self) -> dict:
        d = asdict(self)
        d["triggered"] = list(self.triggered)
        d["recommendations"] = list(self.recommendations)
        return d


def monitor_flags(metrics: dict) -> dict:
    """从监控指标值生成触发标记（阈值可调）。"""
    flags = {}
    # 关键监控指标缺失 → UNKNOWN → SAFE_MODE（不能"没有数据=默认正常"）
    if any(metrics.get(k) is None for k in (
            "data_missing_rate", "pit_grade", "ledger_integrity",
            "replay_consistent")):
        flags["unknown_production_evidence"] = True
    if metrics.get("data_missing_rate") is not None \
            and float(metrics["data_missing_rate"]) > 0.05:
        flags["data_failure"] = True
    if metrics.get("pit_grade") is not None \
            and str(metrics["pit_grade"]).upper() in ("D", "F"):
        flags["pit_failure"] = True
    if abs(float(metrics.get("settings_drift") or 0.0)) > 1e-9:
        flags["model_drift"] = True
    if float(metrics.get("permission_flip_rate") or 0.0) > 0.15:
        flags["permission_drift"] = True
    if float(metrics.get("wave_capture_trend") or 1.0) < 0.5:
        flags["wave_perf_degraded"] = True
    if float(metrics.get("slippage_ratio") or 0.0) > 3.0:
        flags["execution_failure"] = True
    if metrics.get("liquidity_flag") == "LIQUIDITY_LOW":
        flags["liquidity_low"] = True
    if float(metrics.get("mfe_bias") or 0.0) < -0.05 \
            or float(metrics.get("mae_bias") or 0.0) > 0.05:
        flags["mfe_mae_biased"] = True
    if float(metrics.get("false_entry_rate") or 0.0) > 0.4:
        flags["false_entry_high"] = True
    if metrics.get("governance_violations"):
        flags["governance_failure"] = True
    if metrics.get("ledger_integrity") is False:
        flags["ledger_failure"] = True
    if metrics.get("replay_consistent") is False:
        flags["replay_failure"] = True
    if float(metrics.get("risk_budget_breach") or 0.0) > 0:
        flags["risk_breach"] = True
    if metrics.get("abnormal_market"):
        flags["abnormal_market"] = True
    return flags


def _recommendations(status, triggered) -> tuple:
    recs = []
    if status == "HALTED":
        recs.append("HALTED：禁止产生任何新交易决策，先人工排查")
    if status == "SAFE_MODE":
        recs.append("SAFE_MODE：禁止新增风险，允许减仓/风控，进入研究复核")
    if status == "WARNING":
        recs.append("WARNING：降低风险敞口，切换 Shadow / Review 模式")
    if "ledger_failure" in triggered:
        recs.append("台账完整性异常：立即审计 qcfp_decision_ledger")
    if "replay_failure" in triggered:
        recs.append("回放不一致：检查输入漂移/版本漂移，发布 REPLAY_MISMATCH 报告")
    if "governance_failure" in triggered:
        recs.append("治理违规：审查 finalize_target 唯一仓位链")
    if "mfe_mae_biased" in triggered:
        recs.append("预期-实际校准偏移：下调 MFE 期望或重做 OOS 校准")
    if "false_entry_high" in triggered:
        recs.append("假进场率偏高：收紧 Entry Quality / Trigger 宽度")
    if "liquidity_low" in triggered:
        recs.append("流动性风险：生成 DELEVERAGE_PLAN，控制单笔规模")
    return tuple(recs or ["NORMAL：继续运行，维持常规监控"])


def continuous_validation(metrics: dict, extra_flags: dict = None) \
        -> ContinuousValidationResult:
    """聚合监控 → 安全状态。metrics 为指标值，extra_flags 为人工/外部标记。"""
    flags = monitor_flags(metrics)
    flags.update(extra_flags or {})
    merged = {}
    for k in set(flags) | set(EXTRA_CHECKS):
        if k in EXTRA_CHECKS and k not in flags:
            merged[k] = False
        else:
            merged[k] = bool(flags.get(k))
    st = evaluate_safety(merged)
    status = st["status"]
    if status == "NORMAL" and any(
            merged.get(k) for k in EXTRA_CHECKS if EXTRA_CHECKS[k] == "WARNING"):
        status = "WARNING"
    triggered = tuple(st["triggered"])
    degraded = {k: metrics.get(k) for k in (
        "wave_capture_trend", "false_entry_rate", "slippage_ratio",
        "mfe_bias", "mae_bias", "permission_flip_rate", "liquidity_flag")
        if metrics.get(k) is not None}
    return ContinuousValidationResult(
        status=status, triggered=triggered,
        degraded_metrics=degraded,
        recommendations=_recommendations(status, triggered))


def continuous_validation_gate(metrics: dict, target,
                               previous_position=0.0,
                               extra_flags=None) -> dict:
    """持续验证门：安全状态直接作用于目标仓位（SAFE_MODE 禁新增、HALTED 归零）。"""
    cv = continuous_validation(metrics, extra_flags=extra_flags)
    checks = {k: v for k, v in
              (monitor_flags(metrics) | (extra_flags or {})).items()}
    gate = safety_gate(checks, target, previous_position)
    return {"validation": cv.as_dict(), "gate": gate}


def validation_to_md(result: ContinuousValidationResult) -> str:
    lines = [
        "# Continuous Validation Report",
        "",
        f"**安全状态：{result.status}**",
        "",
    ]
    if result.triggered:
        lines += ["## 触发项", ""]
        lines += [f"- {t}" for t in result.triggered]
        lines += [""]
    if result.degraded_metrics:
        lines += ["## 劣化指标", ""]
        for k, v in result.degraded_metrics.items():
            lines.append(f"- {k}：{v}")
        lines += [""]
    lines += ["## 建议", ""]
    lines += [f"- {r}" for r in result.recommendations]
    lines += [""]
    return "\n".join(lines)


PRODUCTION_REQUIRED_METRICS = ("ledger", "replay", "pit", "execution")


def fail_closed_validation(metrics: dict) -> dict:
    """Fail-Closed（P0-5 号）：UNKNOWN 不能等于 PASS。

    四态：PASS / WARN / FAIL / UNKNOWN。
    Production-required 指标为 UNKNOWN → 至少 SAFE_MODE；
    缺少 Ledger/Replay/PIT/Execution 关键证据时绝不显示 NORMAL。
    """
    statuses = {}
    for key in PRODUCTION_REQUIRED_METRICS:
        v = metrics.get(key)
        if v is None:
            statuses[key] = "UNKNOWN"
        elif v is True or v == "PASS":
            statuses[key] = "PASS"
        elif v is False or v == "FAIL":
            statuses[key] = "FAIL"
        else:
            statuses[key] = str(v).upper()
    unknown = [k for k, s in statuses.items() if s == "UNKNOWN"]
    fail = [k for k, s in statuses.items() if s == "FAIL"]
    if fail:
        overall = "SAFE_MODE" if any(
            k in ("ledger", "replay", "pit") for k in fail) else "WARNING"
    elif unknown:
        overall = "SAFE_MODE"     # 关键证据缺失 → 至少 SAFE_MODE
    else:
        overall = "NORMAL"
    return {"metric_statuses": statuses,
            "unknown_metrics": unknown,
            "failed_metrics": fail,
            "overall": overall,
            "fail_closed": bool(unknown or fail),
            "display_normal": overall == "NORMAL"}
