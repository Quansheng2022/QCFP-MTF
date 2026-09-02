# coding: utf-8
"""Decision Coverage / Abstention Coverage（QCFP-MTF 2.8：58 号决策覆盖率）

统计系统到底有多少时候"有资格决策"：
    Certified Decision / Safe-mode / Abstain / Halted
并按原因拆分：PIT unknown / evidence missing / permission unavailable /
liquidity unavailable / replay failure。

验收标准：Production 报告必须同时报告 Performance 和 Decision Coverage，
不能只在"有数据、有决策"的样本里展示漂亮结果。
"""


COVERAGE_STATES = ("certified", "no_trade", "safe_mode", "abstain",
                   "halted")
ABSTAIN_REASON_KEYS = ("pit_unknown", "evidence_missing",
                       "permission_unavailable", "liquidity_unavailable",
                       "replay_failure", "no_wave", "permission_block",
                       "liquidity_fail", "data_missing")


def decision_coverage(counts: dict, abstain_reasons: dict = None) -> dict:
    total = sum(int(counts.get(k) or 0) for k in COVERAGE_STATES)
    coverage = {}
    for k in COVERAGE_STATES:
        n = int(counts.get(k) or 0)
        coverage[k] = round(n / total, 4) if total else None
    reasons = {}
    if total:
        for k in ABSTAIN_REASON_KEYS:
            reasons[k] = round(
                int((abstain_reasons or {}).get(k) or 0) / total, 4)
    certified = coverage["certified"] or 0.0
    return {
        "total_decisions": total,
        "coverage": coverage,
        "abstain_reason_breakdown": reasons,
        "certified_ratio": coverage["certified"],
        "maturity_concern": bool(total and certified < 0.70),
        "note": "成熟度要求：不能大量时间处于 UNKNOWN 还宣称可用",
    }


def decision_coverage_report(performance: dict, counts: dict,
                             abstain_reasons=None) -> dict:
    cov = decision_coverage(counts, abstain_reasons)
    return {
        "performance": performance,
        "coverage": cov,
        "report_rule": "Production 报告必须同时报告 "
                       "Performance 与 Decision Coverage",
        "reportable": True,
    }


def report_completeness_check(report: dict) -> dict:
    """新 58 号：OOS/Production 报告只显示 Sharpe/MDD 而不显示
    Coverage → INCOMPLETE_REPORT。"""
    has_performance = bool(report.get("performance"))
    has_coverage = bool(report.get("coverage"))
    if not (has_performance and has_coverage):
        return {"verdict": "INCOMPLETE_REPORT",
                "missing": [k for k, v in
                            ({"performance": has_performance,
                              "coverage": has_coverage}).items()
                            if not v],
                "complete": False,
                "rule": "只评价'系统愿意说话的时候'会产生选择性偏差"}
    cov = report.get("coverage") or {}
    states = cov.get("coverage") or cov
    no_trade = states.get("no_trade")
    abstain = states.get("abstain")
    distinct = no_trade is not None and abstain is not None
    return {"verdict": "COMPLETE_REPORT",
            "missing": [], "complete": True,
            "no_trade_distinct_from_abstain": distinct,
            "rule": "NO_TRADE ≠ ABSTAIN"}


def oos_coverage_requirement(performance: dict, coverage: dict) -> dict:
    """Release 3（新 24 号）：正式 OOS 必须同时报告
    Sharpe/MDD/Wave Capture + Certified/NoTrade/Abstain/Safe/Halted
    + 原因分布；缺 Coverage → INCOMPLETE_REPORT，不能用于 Promotion。"""
    perf_keys = ("sharpe", "mdd", "wave_capture")
    cov_keys = ("certified", "no_trade", "abstain", "safe_mode", "halted")
    missing = [k for k in perf_keys if performance.get(k) is None]
    missing += [k for k in cov_keys if coverage.get(k) is None]
    if missing:
        return {"verdict": "INCOMPLETE_REPORT",
                "missing": missing,
                "promotion_allowed": False,
                "rule": "正式 OOS 缺 Coverage → INCOMPLETE_REPORT，"
                        "不能用于 Production Promotion"}
    return {"verdict": "COMPLETE_OOS_REPORT",
            "missing": [],
            "promotion_allowed": True}
