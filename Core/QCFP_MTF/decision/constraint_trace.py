# coding: utf-8
"""Constraint Trace（QCFP-MTF 2.8：32 号约束轨迹）

记录每一级约束如何改变仓位：
    Raw Target → Permission → Risk → Portfolio → Liquidity → Execution
    → Final Target

每级记录：constraint_name / input_value / limit / output_value / reason /
           version
并计算各级 Reduction（如 Permission Reduction = 2%），供审计/解释消费。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ConstraintStep:
    constraint: str
    input_value: float
    limit: float
    output_value: float
    reason: str = ""
    version: str = "1.0"

    def as_dict(self) -> dict:
        return asdict(self)


def build_constraint_trace(steps) -> dict:
    """steps：[(constraint, input_value, output_value, reason, version)]
    （按应用顺序，记录每级实际输入/输出）。"""
    trace = []
    for i, (constraint, input_value, output_value, reason, version) \
            in enumerate(steps):
        trace.append(ConstraintStep(
            constraint=constraint, input_value=round(input_value, 4),
            limit=round(float(input_value), 4),
            output_value=round(float(output_value), 4),
            reason=reason, version=version))
    reductions = {}
    for s in trace:
        red = s.input_value - s.output_value
        if red > 1e-9:
            reductions[s.constraint] = round(red, 4)
    return {
        "steps": [s.as_dict() for s in trace],
        "reductions": reductions,
        "final_target": trace[-1].output_value if trace else 0.0,
    }


def trace_to_md(trace: dict) -> str:
    lines = [
        "# Constraint Trace",
        "",
        "| 约束 | 输入 | 上限 | 输出 | 减少 | 原因 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i, s in enumerate(trace["steps"]):
        red = s["input_value"] - s["output_value"]
        lines.append(
            f"| {s['constraint']} | {s['input_value']:.1%} | "
            f"{s['limit']:.1%} | {s['output_value']:.1%} | "
            f"{red:.1%} | {s['reason']} |")
    return "\n".join(lines)


def binding_constraint(trace: dict) -> dict:
    """绑定约束（P1-7）：决定最终目标的那一层 + 各级减少归因。

    绑定约束 = 输出值等于最终目标的最后一个约束步（若多步相同取最先）。
    """
    steps = trace.get("steps") or []
    final = trace.get("final_target") or 0.0
    binding = None
    for s in steps:
        if abs(float(s.get("output_value") or 0.0)
               - float(final)) < 1e-9:
            binding = s
            break
    return {
        "binding_constraint": binding["constraint"] if binding else "raw_target",
        "binding_limit": binding["limit"] if binding else final,
        "final_target": round(float(final), 4),
        "reduction_attribution": trace.get("reductions") or {},
        "total_reduction": round(
            sum((trace.get("reductions") or {}).values()), 4),
    }
