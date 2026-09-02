# coding: utf-8
"""Production Simplicity KPI（QCFP-MTF 2.8：79 号生产简洁度 KPI）

把"系统变简单"正式纳入版本考核，只保留少量 KPI：
    Active decision modules / Duplicate authorities /
    Decision-critical parameters / Canonical path length /
    Report decision logic count / Legacy production imports

验收标准：每个大版本既汇报新增功能，也汇报这些指标是升还是降；
理想目标是长期下降或保持稳定，而不是版本越高越复杂。
"""


SIMPLICITY_KPIS = ("active_decision_modules", "duplicate_authorities",
                   "decision_critical_parameters", "canonical_path_length",
                   "report_decision_logic_count",
                   "legacy_production_imports")


def production_simplicity_kpi(current: dict,
                              previous: dict = None) -> dict:
    kpis, deltas = {}, {}
    for k in SIMPLICITY_KPIS:
        cur = int(current.get(k) or 0)
        prev = int(previous.get(k) or 0) if previous else None
        direction = "UP" if (prev is not None and cur > prev) else \
            "DOWN" if (prev is not None and cur < prev) else "STABLE"
        kpis[k] = {"current": cur, "previous": prev,
                   "direction": direction}
        if prev is not None:
            deltas[k] = cur - prev
    if previous is None:
        trend = "BASELINE"
    elif all(d == 0 for d in deltas.values()):
        trend = "STABLE"
    elif all(d <= 0 for d in deltas.values()):
        trend = "IMPROVING"
    else:
        trend = "REGRESSING"
    return {"kpis": kpis,
            "deltas": deltas,
            "overall_trend": trend,
            "rule": "版本越高不代表越复杂；简洁度也是版本考核指标"}


def release_simplicity_verdict(previous: dict, current: dict,
                               oos_improved=False,
                               risk_improved=False,
                               practicality_improved=False) -> dict:
    """新 79 号：每个大版本比较 Previous vs Current——
    复杂度显著上升而 OOS/Risk/Practicality 没有明显改善 →
    SIMPLIFY_REQUIRED。"""
    kpi = production_simplicity_kpi(current, previous)
    improvements = (oos_improved or risk_improved
                    or practicality_improved)
    if kpi["overall_trend"] == "REGRESSING" and not improvements:
        return {"verdict": "SIMPLIFY_REQUIRED",
                "reason": "复杂度显著上升但 OOS/Risk/Practicality "
                          "无明显改善",
                "simplify": True,
                "trend": kpi["overall_trend"]}
    return {"verdict": "OK",
            "reason": "复杂度未显著恶化或已有改善",
            "simplify": False,
            "trend": kpi["overall_trend"]}
