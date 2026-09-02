# coding: utf-8
"""Operational Observability（QCFP-MTF 2.8：49 号运行可观测性）

监控：Data / Feature / Decision / Ledger / Replay / Execution 延迟 +
Error Rate + Missing Rate + Queue Backlog。

健康维度：Data / Decision / Execution / Ledger / Research。
硬规则：Ledger 写不进去 = 交易风险 → Decision Health = DEGRADED → HALT。
（不能出现"交易已执行但 Ledger 没有记录"。）
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ObservabilityResult:
    dimensions: dict
    overall: str
    halt: bool
    latencies: dict
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def _band(ok, degraded_penalty=0.4):
    return "HEALTHY" if ok else "DEGRADED"


def observability_report(metrics: dict) -> ObservabilityResult:
    """metrics：{latency_ms: {data, feature, decision, ledger, replay,
    execution}, error_rate, missing_rate, queue_backlog, ledger_write_ok,
    research_validated}"""
    lat = metrics.get("latency_ms") or {}
    reasons = []
    dims = {}
    dims["data"] = _band(
        float(metrics.get("missing_rate") or 0.0) <= 0.05
        and float(lat.get("data") or 0.0) <= 5000)
    dims["decision"] = _band(
        float(metrics.get("error_rate") or 0.0) <= 0.01
        and float(lat.get("decision") or 0.0) <= 2000)
    dims["execution"] = _band(
        float(lat.get("execution") or 0.0) <= 1000
        and float(metrics.get("queue_backlog") or 0.0) <= 10)
    dims["ledger"] = _band(bool(metrics.get("ledger_write_ok", True)))
    dims["research"] = _band(bool(metrics.get("research_validated", False)))
    if not metrics.get("ledger_write_ok", True):
        dims["decision"] = "DEGRADED"
        reasons.append("LEDGER_WRITE_FAILURE→DECISION_DEGRADED→HALT")
    degraded = [k for k, v in dims.items() if v == "DEGRADED"]
    overall = "HEALTHY" if not degraded else "DEGRADED"
    halt = not metrics.get("ledger_write_ok", True)
    return ObservabilityResult(
        dimensions=dims, overall=overall, halt=halt,
        latencies={k: round(float(v), 2) for k, v in lat.items()},
        reasons=tuple(reasons))


def observability_to_md(r: ObservabilityResult) -> str:
    lines = [
        "# Operational Observability",
        "",
        f"**Overall：{r.overall}**　Halt：{'✅' if r.halt else '—'}",
        "",
        "| 维度 | 状态 |", "| --- | --- |",
    ]
    for k, v in r.dimensions.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 延迟（ms）", "", "| 环节 | 延迟 |", "| --- | --- |"]
    for k, v in r.latencies.items():
        lines.append(f"| {k} | {v:.0f} |")
    if r.reasons:
        lines += ["", "## 硬规则触发", ""]
        lines += [f"- {x}" for x in r.reasons]
    return "\n".join(lines)
