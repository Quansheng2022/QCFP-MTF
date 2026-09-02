# coding: utf-8
"""Production Drift Monitor（QCFP-MTF 2.8：30 号生产监控与漂移检测）

四类漂移持续监控：
    Data Drift   特征分布 / 缺失率 / 可用滞后
    Model Drift  预测分布 / Wave 分布 / Permission 分布
    Trade Drift  胜率 / MFE / MAE / MFE Capture / 持有期 / 换手 / 滑点
    Risk Drift   回撤 / 暴露 / 集中度 / 流动性

状态阶梯：Healthy → Warning → Degraded → Halted
    Degraded → SAFE_MODE（禁新增风险）
    Halted   → HALTED（禁止新决策）
与 kill_switch 系统级优先权连接：漂移 CRITICAL 时先降风险，再事后解释。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DriftMonitorResult:
    categories: dict
    overall: str           # HEALTHY / WARNING / DEGRADED / HALTED
    safety_status: str     # NORMAL / WARNING / SAFE_MODE / HALTED
    triggered: tuple

    def as_dict(self) -> dict:
        d = asdict(self)
        d["triggered"] = list(self.triggered)
        return d


def _cat(score, name) -> dict:
    score = float(score)
    if score >= 70:
        band = "HEALTHY"
    elif score >= 40:
        band = "WARNING"
    else:
        band = "DEGRADED"
    return {"name": name, "score": round(score, 1), "band": band}


def drift_monitor(metrics: dict) -> DriftMonitorResult:
    """四类漂移汇总 → 状态阶梯 + 安全映射。

    metrics 关键字段：
        data_missing_rate / data_avail_lag
        permission_dist_shift / wave_dist_shift
        win_rate_trend / mfe_trend / mfe_capture_trend / slippage_ratio
        drawdown / exposure / concentration / liquidity_flag
    """
    # 每类漂移累积扣分（多项失败 → DEGRADED）
    data_s = 100.0
    if float(metrics.get("data_missing_rate") or 0.0) > 0.05:
        data_s -= 40
    if float(metrics.get("data_avail_lag") or 0.0) > 7:
        data_s -= 40
    model_s = 100.0
    if float(metrics.get("permission_dist_shift") or 0.0) > 0.15:
        model_s -= 35
    if float(metrics.get("wave_dist_shift") or 0.0) > 0.15:
        model_s -= 35
    trade_s = 100.0
    if float(metrics.get("win_rate_trend") or 1.0) < 0.8:
        trade_s -= 25
    if float(metrics.get("mfe_capture_trend") or 1.0) < 0.8:
        trade_s -= 25
    if float(metrics.get("mfe_trend") or 1.0) < 0.8:
        trade_s -= 20
    if float(metrics.get("slippage_ratio") or 1.0) > 3.0:
        trade_s -= 20
    risk_s = 100.0
    if abs(float(metrics.get("drawdown") or 0.0)) >= 0.08:
        risk_s -= 30
    if float(metrics.get("exposure") or 0.0) > 0.7:
        risk_s -= 25
    if metrics.get("liquidity_flag") == "LIQUIDITY_LOW":
        risk_s -= 30
    data = _cat(max(0.0, data_s), "data_drift")
    model = _cat(max(0.0, model_s), "model_drift")
    trade = _cat(max(0.0, trade_s), "trade_drift")
    risk = _cat(max(0.0, risk_s), "risk_drift")
    categories = {"data": data, "model": model, "trade": trade,
                  "risk": risk}
    triggered = []
    worst = 100.0
    for cat in categories.values():
        worst = min(worst, cat["score"])
        if cat["band"] != "HEALTHY":
            triggered.append(f"{cat['name']}:{cat['band']}")
    # 状态阶梯
    if any(c["band"] == "DEGRADED" for c in categories.values()):
        overall = "DEGRADED"
        safety = "SAFE_MODE"
    elif any(c["band"] == "WARNING" for c in categories.values()):
        overall = "WARNING"
        safety = "WARNING"
    else:
        overall = "HEALTHY"
        safety = "NORMAL"
    if metrics.get("halted"):
        overall, safety = "HALTED", "HALTED"
        triggered.append("HALTED")
    return DriftMonitorResult(
        categories=categories, overall=overall,
        safety_status=safety, triggered=tuple(triggered))


def drift_to_md(result: DriftMonitorResult) -> str:
    lines = [
        "# Production Drift Monitor",
        "",
        f"**Overall：{result.overall}**　Safety：{result.safety_status}",
        "",
        "| 类别 | 得分 | 状态 |", "| --- | --- | --- |",
    ]
    for name in ("data", "model", "trade", "risk"):
        c = result.categories[name]
        lines.append(f"| {c['name']} | {c['score']:.0f} | {c['band']} |")
    if result.triggered:
        lines += ["", "## 触发项", ""]
        lines += [f"- {t}" for t in result.triggered]
    return "\n".join(lines)
