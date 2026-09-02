# coding: utf-8
"""Decision Outcome Simulation（P0-3：Paper → Outcome）

QCFP_MTF 是辅助决策支持系统。Paper 不再回答"订单有没有成交"，
而是回答："如果参考这个决策，后续 5D/20D/60D 风险收益结果怎样"。

正式入口：
    simulate_decision_outcome(conn, decision, horizons, today)

输入：Certified/Canonical Decision（只读 Ledger）。
输出（PIT-safe，决策日后真实 K 线）：
    return / mfe / mae / wave_peak_return / wave_capture /
    exit_efficiency / holding_period / opportunity_cost

Outcome 只能用于评价，不允许反向自动修改 Production 参数
（auto_param_modify_forbidden 由调用方保证）。
"""

from datetime import datetime


OUTCOME_HORIZONS = ("5D", "20D", "60D")


def _horizon_days(horizon: str) -> int:
    h = str(horizon or "").upper()
    if h.endswith("D"):
        return int(h[:-1])
    if h.endswith("W"):
        return int(h[:-1]) * 7
    if h.endswith("M"):
        return int(h[:-1]) * 30
    return int(h or "0")


def load_pit_safe_kline(conn, stock_code, decision_date):
    """决策日后 K 线（as-of，无未来泄露；按日期升序）。"""
    rows = conn.execute(
        "SELECT date AS trade_date, close, high, low "
        "FROM hk_hist_daily_kline "
        "WHERE stock_code=? AND date>? ORDER BY date",
        (stock_code, str(decision_date)[:10])).fetchall()
    return [dict(r) for r in rows]


def compute_decision_outcome(rows, horizon_days, outcome_type="TRADE"):
    """从 PIT-safe 价格序列计算单 horizon Outcome 指标。
    数据不足 → 返回 None（未成熟，不算退化）。"""
    if not rows:
        return None
    horizon_rows = rows[:_horizon_days(horizon_days)] \
        if isinstance(horizon_days, str) else rows[:int(horizon_days)]
    need = _horizon_days(horizon_days) \
        if isinstance(horizon_days, str) else int(horizon_days)
    if len(horizon_rows) < max(1, need):
        return None
    entry = float(horizon_rows[0]["close"] or 0.0)
    if entry <= 0:
        return None
    exit_price = float(horizon_rows[-1]["close"] or 0.0)
    peak = max(float(r["high"] or entry) for r in horizon_rows)
    trough = min(float(r["low"] or entry) for r in horizon_rows)
    future_return = (exit_price - entry) / entry
    mfe = (peak - entry) / entry
    mae = (trough - entry) / entry
    wave_peak_return = mfe
    peak_ratio = (exit_price - entry) / (peak - entry) \
        if peak > entry else None
    exit_efficiency = round(peak_ratio, 4) \
        if peak_ratio is not None else None
    if outcome_type in ("NO_TRADE", "ABSTAIN"):
        opportunity_cost = round(max(0.0, future_return), 6)
    else:
        opportunity_cost = round(max(0.0, wave_peak_return
                                     - future_return), 6)
    return {
        "future_return": round(future_return, 6),
        "mfe": round(mfe, 6),
        "mae": round(mae, 6),
        "wave_peak_return": round(wave_peak_return, 6),
        "wave_capture": round(future_return / wave_peak_return, 4)
        if wave_peak_return > 0 else None,
        "exit_efficiency": exit_efficiency,
        "holding_period": len(horizon_rows),
        "opportunity_cost": opportunity_cost,
        "entry_reference_price": round(entry, 6),
        "exit_reference_price": round(exit_price, 6),
        "horizon_end": str(horizon_rows[-1]["trade_date"])[:10],
    }


def simulate_decision_outcome(conn, decision, horizons=OUTCOME_HORIZONS,
                              today=None) -> dict:
    """对单条 Ledger Decision 计算各 horizon Outcome（未成熟 → None）。"""
    today = today or datetime.now().strftime("%Y-%m-%d")
    rows = load_pit_safe_kline(conn, decision["stock_code"],
                               decision["decision_date"])
    outcome_type = "TRADE" if float(decision.get("final_target") or 0.0) \
        > 1e-9 else "NO_TRADE"
    results = {}
    for h in horizons:
        calc = compute_decision_outcome(rows, h, outcome_type)
        if calc is None or calc["horizon_end"] > today:
            results[h] = {"matured": False}
            continue
        results[h] = {"matured": True, **calc}
    return {
        "decision_id": decision.get("decision_id"),
        "stock_code": decision.get("stock_code"),
        "decision_date": decision.get("decision_date"),
        "outcome_type": outcome_type,
        "horizons": results,
        "auto_param_modify_forbidden": True,
        "rule": "Outcome 只用于评价；禁止反向自动修改 Production 参数",
    }


def outcome_evidence_summary(simulations) -> dict:
    """多决策 Outcome 汇总（供 Runtime Evidence outcome section）。"""
    matured = {h: 0 for h in OUTCOME_HORIZONS}
    total = 0
    for s in simulations or []:
        if s is None:
            continue
        total += 1
        for h, v in (s.get("horizons") or {}).items():
            if v.get("matured"):
                matured[h] = matured.get(h, 0) + 1
    return {
        "decisions_simulated": total,
        "outcome_maturity_5d": matured.get("5D", 0),
        "outcome_maturity_20d": matured.get("20D", 0),
        "outcome_maturity_60d": matured.get("60D", 0),
        "outcome_coverage": round(
            matured.get("5D", 0) / total, 4) if total else 0.0,
        "rule": "Outcome 成熟度显式化；未成熟不算退化",
    }


def outcome_maturity_summary(outcome_rows, expected_count, today=None) -> dict:
    """区分 Coverage 与 Maturity（P0-4）：
        outcome_record_coverage = 已生成记录 / 期望决策数
        outcome_5d/20d/60d_maturity_rate = 已成熟 / 期望决策数
    """
    today = today or datetime.now().strftime("%Y-%m-%d")
    outcome_rows = list(outcome_rows or [])
    matured = {"5D": 0, "20D": 0, "60D": 0}
    for o in outcome_rows:
        h = str((o.get("horizon") if isinstance(o, dict)
                 else o["horizon"]) or "").upper()
        he = (o.get("horizon_end") if isinstance(o, dict)
              else o["horizon_end"])
        if h in matured and he and str(he)[:10] <= today:
            matured[h] += 1
    expected = max(1, int(expected_count or 0))
    return {
        "outcome_record_coverage": round(
            len(outcome_rows) / expected, 4),
        "outcome_5d_maturity_rate": round(matured["5D"] / expected, 4),
        "outcome_20d_maturity_rate": round(matured["20D"] / expected, 4),
        "outcome_60d_maturity_rate": round(matured["60D"] / expected, 4),
        "outcome_maturity_5d": matured["5D"],
        "outcome_maturity_20d": matured["20D"],
        "outcome_maturity_60d": matured["60D"],
    }


def outcome_type_breakdown(outcome_rows) -> dict:
    """按决策类型拆 Outcome（P0-4）：
        TRADE   success（future_return>0）/ failure
        NO_TRADE correct rejection（future_return<=0）/
                 missed opportunity（future_return>2%）
        ABSTAIN correct abstention / false abstention
    """
    rows = list(outcome_rows or [])
    out = {"TRADE": {"n": 0, "success": 0, "failure": 0},
           "NO_TRADE": {"n": 0, "correct_rejection": 0,
                        "missed_opportunity": 0},
           "ABSTAIN": {"n": 0, "correct_abstention": 0,
                       "false_abstention": 0}}
    for o in rows:
        ot = str((o.get("outcome_type") if isinstance(o, dict)
                  else o["outcome_type"]) or "").upper()
        fr = float((o.get("future_return") if isinstance(o, dict)
                    else o["future_return"]) or 0.0)
        bucket = out.get(ot)
        if bucket is None:
            continue
        bucket["n"] += 1
        if ot == "TRADE":
            if fr > 0:
                bucket["success"] += 1
            else:
                bucket["failure"] += 1
        elif ot == "NO_TRADE":
            if fr <= 0:
                bucket["correct_rejection"] += 1
            if fr > 0.02:
                bucket["missed_opportunity"] += 1
        elif ot == "ABSTAIN":
            if fr <= 0:
                bucket["correct_abstention"] += 1
            if fr > 0.02:
                bucket["false_abstention"] += 1
    return out


def outcome_cohort(decision_cohort_date, horizons=OUTCOME_HORIZONS,
                   today=None) -> dict:
    """Outcome Cohort：成熟基准日（P0-4）——
        5D_matured_asof = cohort + 5 个自然日；20D/60D 同理。"""
    from datetime import timedelta
    today = today or datetime.now().strftime("%Y-%m-%d")
    days = {"5D": 5, "20D": 20, "60D": 60}
    cohort = datetime.strptime(str(decision_cohort_date)[:10], "%Y-%m-%d")
    return {
        "decision_cohort_date": str(decision_cohort_date)[:10],
        **{f"{h}_matured_asof":
           (cohort + timedelta(days=days[h])).strftime("%Y-%m-%d")
           for h in horizons},
        "fully_matured": all(
            (cohort + timedelta(days=days[h])).strftime("%Y-%m-%d")
            <= today for h in horizons),
    }
