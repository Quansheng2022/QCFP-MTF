# coding: utf-8
"""Live-vs-Backtest Gap Monitor（QCFP-MTF 2.8：59 号实盘/回测偏差监控）

持续比较回测预期与实盘现实：
    Return Gap / MFE Gap / MAE Gap / Slippage Gap / Entry Gap /
    Exit Gap / Holding Gap / Cost Gap

偏差持续恶化：
    WARNING → DEGRADED → MODEL_REVIEW（而不是继续扩大仓位）。
"""

from dataclasses import asdict, dataclass, field


GAP_FIELDS = ("return", "mfe", "mae", "slippage", "entry", "exit",
              "holding", "cost")


@dataclass(frozen=True)
class GapMonitorResult:
    gaps: dict
    status: str           # HEALTHY / WARNING / DEGRADED / MODEL_REVIEW
    degraded_fields: tuple

    def as_dict(self) -> dict:
        d = asdict(self)
        d["degraded_fields"] = list(self.degraded_fields)
        return d


def gap_monitor(backtest: dict, live: dict,
                warn_threshold=0.15, degrade_threshold=0.30) \
        -> GapMonitorResult:
    """gaps：live/backtest 偏差（0=一致，正值=实盘更差）。

    每个字段：gap = (bt − live) / bt（bt>0 时）；
    若字段为"越低越好"（mae/slippage/cost），取反向。
    """
    gaps = {}
    for f in GAP_FIELDS:
        b = float(backtest.get(f) or 0.0)
        l = float(live.get(f) or 0.0)
        if b == 0:
            gaps[f] = 0.0
            continue
        gap = (b - l) / abs(b)
        if f in ("mae", "slippage", "cost"):
            gap = -gap    # 这些字段越小越好：实盘更小 = 更差
        gaps[f] = round(gap, 4)
    degraded = [f for f, g in gaps.items()
                if abs(g) >= degrade_threshold]
    warned = [f for f, g in gaps.items()
              if warn_threshold <= abs(g) < degrade_threshold]
    if degraded:
        status = "MODEL_REVIEW" if len(degraded) >= 3 else "DEGRADED"
    elif warned:
        status = "WARNING"
    else:
        status = "HEALTHY"
    return GapMonitorResult(gaps=gaps, status=status,
                            degraded_fields=tuple(degraded))


def gap_to_md(r: GapMonitorResult) -> str:
    lines = [
        "# Live vs Backtest Gap Monitor",
        "",
        f"**Status：{r.status}**",
        "",
        "| 维度 | 偏差 |", "| --- | --- |",
    ]
    for f, g in r.gaps.items():
        lines.append(f"| {f} | {g:+.1%} |")
    if r.degraded_fields:
        lines += ["", f"Degraded：{', '.join(r.degraded_fields)}"]
    return "\n".join(lines)
