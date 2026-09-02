# coding: utf-8
"""Retail Practicality Scorecard（QCFP-MTF 2.8：29 号牛散实战记分卡）

评价"统计意义上好的策略，是不是牛散现实中能执行的策略"（不是新交易评分）：
    Trades/year / Median holding / Concurrent positions / Turnover /
    Exit days / ADV participation / Max drawdown / Decision changes/month /
    Missed opportunity / Explanation complexity → A/B/C/D
"""


def retail_practicality_scorecard(metrics: dict) -> dict:
    """metrics 各指标 + 合格判定，总分 0-10 → A/B/C/D。"""
    checks = [
        ("trades_per_year", metrics.get("trades_per_year"),
         lambda v: 12 <= float(v) <= 120),
        ("median_holding_days", metrics.get("median_holding_days"),
         lambda v: 5 <= float(v) <= 60),
        ("median_concurrent_positions",
         metrics.get("median_concurrent_positions"),
         lambda v: float(v) <= 8),
        ("turnover", metrics.get("turnover"), lambda v: float(v) <= 3.0),
        ("exit_days", metrics.get("exit_days"), lambda v: float(v) <= 3),
        ("adv_participation", metrics.get("adv_participation"),
         lambda v: float(v) <= 0.10),
        ("max_drawdown", metrics.get("max_drawdown"),
         lambda v: abs(float(v)) <= 0.25),
        ("decision_changes_per_month",
         metrics.get("decision_changes_per_month"),
         lambda v: float(v) <= 10),
        ("missed_opportunity", metrics.get("missed_opportunity"),
         lambda v: float(v) <= 0.4),
        ("explanation_complexity",
         metrics.get("explanation_complexity"),
         lambda v: float(v) <= 0.5),
        # 新 29 号：资金效率与虚假参与
        ("capital_utilization", metrics.get("capital_utilization"),
         lambda v: 0.2 <= float(v) <= 0.9),
        ("false_participation", metrics.get("false_participation"),
         lambda v: float(v) <= 0.3),
    ]
    results = []
    score = 0.0
    for name, value, cond in checks:
        if value is None:
            ok = False
        else:
            try:
                ok = bool(cond(value))
            except (TypeError, ValueError):
                ok = False
        results.append({"metric": name, "value": value,
                        "pass": ok})
        if ok:
            score += 1.0
    # 极端高频/高换手 → 牛散无法执行 → 硬降级 D
    hard_fail = (metrics.get("trades_per_year") is not None
                 and float(metrics["trades_per_year"]) > 365) or \
        (metrics.get("turnover") is not None
         and float(metrics["turnover"]) > 10)
    if hard_fail:
        grade = "D"
    elif score >= 11:
        grade = "A"
    elif score >= 9:
        grade = "B"
    elif score >= 6:
        grade = "C"
    else:
        grade = "D"
    return {"grade": grade, "score": round(score, 1),
            "max_score": float(len(checks)), "metrics": results,
            "failed_metrics": [r["metric"] for r in results
                               if not r["pass"]]}


def promotion_requirement(statistical_valid: bool,
                          practicality_grade: str) -> dict:
    """新 29 号：Production Promotion 必须同时通过
    Statistical Validity + Retail Practicality。"""
    practical_ok = practicality_grade in ("A", "B")
    return {
        "statistical_valid": bool(statistical_valid),
        "retail_practicality": practicality_grade,
        "practical_ok": practical_ok,
        "promotion": "ALLOW" if statistical_valid and practical_ok
        else "BLOCK",
        "rule": "统计上能赚钱，不代表牛散现实里能执行",
    }


DEFAULT_RETAIL_OPERATING_ENVELOPE = {
    "trades_per_year_max": 120,
    "median_concurrent_positions_max": 8,
    "turnover_max": 3.0,
    "exit_days_max": 3,
    "adv_participation_max": 0.10,
    "max_drawdown_abs": 0.25,
}


def retail_operating_envelope(version="PRACTICALITY-1.0") -> dict:
    """Release 3（新 27 号）：阈值作为 Default Retail Operating Envelope，
    ReleaseManifest 固定其版本；改变阈值 → PracticalityPolicyVersion 变化
    → 进入 Version Impact。"""
    return {"policy_version": version,
            "envelope": DEFAULT_RETAIL_OPERATING_ENVELOPE,
            "rule": "阈值不是永远正确的固定真理，而是版本化 Operating "
                    "Envelope"}


def practicality_hard_gate(statistical_valid: bool,
                           practicality_grade: str) -> dict:
    """Release 3（新 27 号）：Retail Practicality 是 Promotion Hard Gate——
    Statistical Valid=YES + Practicality=C → PROMOTION BLOCKED。"""
    p = promotion_requirement(statistical_valid, practicality_grade)
    if statistical_valid and practicality_grade == "C":
        return {"verdict": "PROMOTION_BLOCKED",
                "reason": "统计有效但 Retail Practicality=C → 不能因 "
                          "Sharpe 高破例",
                "allowed": False}
    return {"verdict": "PROMOTION_ALLOWED" if p["promotion"] == "ALLOW"
            else "PROMOTION_BLOCKED",
            "allowed": p["promotion"] == "ALLOW"}
