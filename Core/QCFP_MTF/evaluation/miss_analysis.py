# coding: utf-8
"""Opportunity Miss Analysis（QCFP-MTF 2.8：97 号机会遗漏分析）

对每个 Strong Wave 追踪"为什么没做"：
    Permission / Risk / Entry Timing / Liquidity / Portfolio Capacity /
    Concentration / Confidence / FSM / Execution

输出：Capture Rate / Missed Alpha / 遗漏原因分布。
"""

from collections import Counter


def miss_analysis(wave_opportunities, captured_ids, miss_reasons=None) -> dict:
    """机会遗漏分析。

    wave_opportunities：[{wave_id, mfe_peak}]
    captured_ids：已捕获 wave_id 集合
    miss_reasons：{wave_id: reason}
    """
    total = len(wave_opportunities)
    captured = [w for w in wave_opportunities
                if w.get("wave_id") in set(captured_ids)]
    missed = [w for w in wave_opportunities
              if w.get("wave_id") not in set(captured_ids)]
    reasons = Counter((miss_reasons or {}).values())
    missed_alpha = sum(float(w.get("mfe_peak") or 0.0) for w in missed)
    return {
        "n_opportunities": total,
        "captured": len(captured),
        "missed": len(missed),
        "capture_rate": round(len(captured) / total, 4) if total else 0.0,
        "missed_alpha": round(missed_alpha, 4),
        "miss_reason_distribution": dict(reasons),
        "missed_waves": [w.get("wave_id") for w in missed],
    }


def capture_summary(wave_opportunities, captured_ids,
                    miss_reasons=None) -> dict:
    """Wave → 实战收益转化效率（Capture Rate + Missed Alpha）。"""
    m = miss_analysis(wave_opportunities, captured_ids, miss_reasons)
    return {
        "capture_rate": m["capture_rate"],
        "missed_alpha": m["missed_alpha"],
        "miss_reason_top": (
            sorted(m["miss_reason_distribution"].items(),
                   key=lambda x: -x[1])[:3]),
    }
