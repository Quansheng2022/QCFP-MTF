# coding: utf-8
"""Strategy Health Score（QCFP-MTF 2.8：49 号策略健康度）

独立于收益率的系统体检：
    Data / Permission / Wave / Execution / Risk / Drift / Ledger / Research
    八维 → HEALTHY / DEGRADED / CRITICAL

即使收益暂时很好，也不能因"赚钱"掩盖"系统正在失效"。
"""

from dataclasses import asdict, dataclass, field


DIMENSIONS = ("data", "permission", "wave", "execution", "risk",
              "drift", "ledger", "research")


def _band(score) -> str:
    s = float(score or 0.0)
    if s >= 70:
        return "HEALTHY"
    if s >= 40:
        return "DEGRADED"
    return "CRITICAL"


@dataclass(frozen=True)
class StrategyHealth:
    dimensions: dict
    overall_band: str
    critical: tuple
    degraded: tuple

    def as_dict(self) -> dict:
        d = asdict(self)
        d["critical"] = list(self.critical)
        d["degraded"] = list(self.degraded)
        return d


def evaluate_strategy_health(scores: dict) -> StrategyHealth:
    """八维健康度评分 → 总评。

    scores：{data: 90, permission: 80, wave: 55, execution: 65, ...}
    缺省维度记 0（视为 CRITICAL，必须显式评分）。
    """
    dims = {}
    for d in DIMENSIONS:
        s = float(scores.get(d) or 0.0)
        dims[d] = {"score": round(min(100.0, max(0.0, s)), 1),
                   "band": _band(s)}
    critical = tuple(d for d, v in dims.items() if v["band"] == "CRITICAL")
    degraded = tuple(d for d, v in dims.items() if v["band"] == "DEGRADED")
    if critical:
        overall = "CRITICAL"
    elif degraded:
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"
    return StrategyHealth(dimensions=dims, overall_band=overall,
                          critical=critical, degraded=degraded)


def health_from_metrics(metrics: dict) -> StrategyHealth:
    """从监控指标自动打分。

    metrics 关键字段：
        data_missing_rate / pit_grade / permission_flip_rate /
        wave_capture_trend / slippage_ratio / risk_budget_breach /
        settings_drift / ledger_integrity / replay_consistent /
        research_validated
    """
    def _score(ok, weight):
        return 100.0 if ok else 100.0 - float(weight)
    scores = {
        "data": _score(
            float(metrics.get("data_missing_rate") or 0.0) <= 0.05
            and str(metrics.get("pit_grade") or "B").upper() in ("A", "B"),
            40),
        "permission": _score(
            float(metrics.get("permission_flip_rate") or 0.0) <= 0.15, 35),
        "wave": _score(
            float(metrics.get("wave_capture_trend") or 1.0) >= 0.5, 40),
        "execution": _score(
            float(metrics.get("slippage_ratio") or 1.0) <= 3.0, 40),
        "risk": _score(
            float(metrics.get("risk_budget_breach") or 0.0) == 0, 50),
        "drift": _score(
            abs(float(metrics.get("settings_drift") or 0.0)) < 1e-9, 45),
        "ledger": _score(
            bool(metrics.get("ledger_integrity", True))
            and bool(metrics.get("replay_consistent", True)), 60),
        "research": _score(
            bool(metrics.get("research_validated", False)), 60),
    }
    return evaluate_strategy_health(scores)


def health_to_md(health: StrategyHealth) -> str:
    lines = [
        "# Strategy Health Report",
        "",
        f"**Overall：{health.overall_band}**",
        "",
        "| 维度 | 得分 | 状态 |", "| --- | --- | --- |",
    ]
    for d in DIMENSIONS:
        v = health.dimensions[d]
        lines.append(f"| {d} | {v['score']:.0f} | {v['band']} |")
    if health.critical:
        lines += ["", f"⚠️ Critical：{', '.join(health.critical)}"]
    if health.degraded:
        lines += ["", f"⚠️ Degraded：{', '.join(health.degraded)}"]
    return "\n".join(lines)
