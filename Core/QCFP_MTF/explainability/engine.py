# coding: utf-8
"""Decision Explanation Engine（QCFP-MTF 2.8：31 号决策解释引擎）

对每一次交易自动回答六个问题：
    1) 为什么允许做？        → Permission / Governance Proof
    2) 为什么现在做？        → Wave Stage + Entry Quality
    3) 为什么是这个仓位？    → Final Target
    4) 为什么不是更大？      → Constraint Trace 各级 Reduction
    5) 为什么不是更小？      → Raw Intent（模型原本想做的量）
    6) 为什么现在退出？      → Exit Quality / Reason

输出结构化 Q&A + 自然语言叙述（Decision Certificate 顶部）。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DecisionExplanation:
    decision_id: str
    qa: dict
    narrative: str
    constraint_reductions: dict

    def as_dict(self) -> dict:
        return asdict(self)


def _fmt(v):
    return f"{float(v or 0.0):.1%}"


def build_explanation(snap, constraint_trace=None, entry_quality=None,
                      exit_quality=None, wave_stage=None) -> DecisionExplanation:
    """从 DecisionSnapshot + 约束轨迹生成解释。

    snap：DecisionSnapshot 或 dict。
    """
    get = snap.get if isinstance(snap, dict) else \
        (lambda k: getattr(snap, k, None))
    ctx = (get("context") or {}) if isinstance(get("context"), dict) else {}
    perm = get("institutional_permission") or "?"
    target = float(get("target_position") or 0.0)
    raw = float(get("raw_target_position") or 0.0)
    prev = float(get("previous_position") or 0.0)
    reason = get("primary_reason") or "NONE"
    stage = wave_stage or ctx.get("wave_stage") or "N/A"
    eq = entry_quality or {}
    eq_timing = eq.get("timing_band") or eq.get("band") or "N/A"
    xq = exit_quality or {}
    xq_kind = xq.get("kind") or "NONE"
    trace = constraint_trace or ctx.get("constraint_trace") or {}
    reductions = trace.get("reductions") or {}
    # 解释：为什么不是更大 = 约束减少总和
    reductions_total = sum(reductions.values())
    qa = {
        "01_permission": (
            f"机构环境判定为 {perm}，{'允许' if target > 1e-9 else '不允许'}"
            f"产生交易意图（Governance Proof "
            f"{'PASS' if (ctx.get('governance_proof') or {}).get('proof') == 'PASS' else 'FAIL'}）"),
        "02_timing": (
            f"Wave 处于 {stage}，Entry Quality 为 {eq_timing}"
            f"{'，因此产生建仓意图' if target > 1e-9 else '，当前不是进场时机'}"),
        "03_position": f"最终仓位为 {_fmt(target)}（前仓 {_fmt(prev)}）",
        "04_not_larger": (
            f"Raw Target {_fmt(raw)} 被约束链压缩 "
            f"{_fmt(reductions_total)}："
            + ("；".join(f"{k} 减少 {_fmt(v)}"
                        for k, v in reductions.items()) or "无约束压缩")),
        "05_not_smaller": (
            f"模型原始意图为 {_fmt(raw)}，在权限/风险/组合允许范围内"
            f"保留至 {_fmt(target)}"),
        "06_exit": (
            f"退出判定 {xq_kind}（主因 {reason}）"
            if xq_kind not in ("NONE", "") and target < prev - 1e-9
            else "当前无退出信号（持有/继续观察）"),
    }
    narrative = (
        f"Wave 处于 {stage}，Entry Quality 为 {eq_timing}，因此产生建仓意图；"
        f"但 Portfolio Risk 和 Liquidity Cap 将 {_fmt(raw)} 的 Raw Target "
        f"限制至 {_fmt(target)}，最终执行 {_fmt(target)}。"
        if target > 1e-9 else
        f"机构环境为 {perm} 且主因 {reason}，当前不建立新仓"
        f"（Raw Target {_fmt(raw)} → Final {_fmt(target)}）。")
    return DecisionExplanation(
        decision_id=get("decision_id") or "?",
        qa=qa, narrative=narrative,
        constraint_reductions=reductions)


def explanation_to_md(exp: DecisionExplanation) -> str:
    lines = [
        f"# Decision Explanation　{exp.decision_id}",
        "",
        f"> {exp.narrative}",
        "",
        "| # | 问题 | 回答 |",
        "| --- | --- | --- |",
    ]
    for q in sorted(exp.qa):
        lines.append(f"| {q} | {exp.qa[q]} |")
    return "\n".join(lines)
