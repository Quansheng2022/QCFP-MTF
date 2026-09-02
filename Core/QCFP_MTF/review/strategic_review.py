# coding: utf-8
"""Strategic Decision Review（QCFP-MTF 2.8：80 号战略级决策复盘）

从单笔交易复盘升级到系统级长期复盘（季度/半年/年度）：
    Market Regime / Permission / Wave / Entry / Exit / FSM / Risk /
    Portfolio / Execution / Capacity / Cost / Model Decay

输出：
    What Worked? / What Failed? / What Changed? / What Should Be Retired? /
    What Should Be Tested? / What Must NOT Be Changed?

治理路径：Review → Hypothesis → Research → OOS → Ablation → Stress →
Governance Review → Release（不能直接改生产代码）。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class StrategicReview:
    period: str
    module_scores: dict
    worked: tuple
    failed: tuple
    changed: tuple
    should_retire: tuple
    should_test: tuple
    must_not_change: tuple
    governance_path: tuple

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("worked", "failed", "changed", "should_retire",
                  "should_test", "must_not_change", "governance_path"):
            d[k] = list(d[k])
        return d


GOVERNANCE_PATH = ("REVIEW", "HYPOTHESIS", "RESEARCH", "OOS", "ABLATION",
                   "STRESS", "GOVERNANCE_REVIEW", "RELEASE")


MUST_NOT_CHANGE = ("permission_gate", "pit_contract", "ledger_append_only",
                   "governance_proof", "hard_exit")


def strategic_review(period, module_scores: dict,
                     positive_threshold=60, negative_threshold=40,
                     decayed_modules=()) -> StrategicReview:
    """战略复盘。

    module_scores：{module: 0-100 绩效分}
    worked = 高分模块；failed = 低分模块；decayed = 衰减模块（应退役候选）。
    """
    worked = tuple(sorted((m for m, s in module_scores.items()
                           if s >= positive_threshold),
                          key=lambda m: -module_scores[m]))
    failed = tuple(sorted((m for m, s in module_scores.items()
                           if s < negative_threshold),
                          key=lambda m: module_scores[m]))
    changed = tuple(sorted(
        {m for m in worked if m in failed}
        | set(decayed_modules)))
    should_retire = tuple(sorted(set(decayed_modules)))
    should_test = tuple(sorted(
        {m for m in failed if m not in decayed_modules}))
    return StrategicReview(
        period=period, module_scores=dict(module_scores),
        worked=worked, failed=failed, changed=changed,
        should_retire=should_retire, should_test=should_test,
        must_not_change=MUST_NOT_CHANGE,
        governance_path=GOVERNANCE_PATH)


def review_to_md(r: StrategicReview) -> str:
    lines = [
        f"# Strategic Decision Review　{r.period}",
        "",
        "| 模块 | 得分 |", "| --- | --- |",
    ]
    for m, s in sorted(r.module_scores.items(), key=lambda x: -x[1]):
        lines.append(f"| {m} | {s:.0f} |")
    lines += ["", f"**What Worked?**：{', '.join(r.worked) or '—'}",
              f"**What Failed?**：{', '.join(r.failed) or '—'}",
              f"**What Changed?**：{', '.join(r.changed) or '—'}",
              f"**What Should Be Retired?**："
              f"{', '.join(r.should_retire) or '—'}",
              f"**What Should Be Tested?**："
              f"{', '.join(r.should_test) or '—'}",
              f"**What Must NOT Be Changed?**："
              f"{', '.join(r.must_not_change)}",
              "",
              "## 治理路径（禁止直接改生产）",
              "",
              " → ".join(r.governance_path)]
    return "\n".join(lines)
