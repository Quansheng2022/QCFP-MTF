# coding: utf-8
"""Replay Accumulation（P0-5：从单日 100% 升级到长期连续 100%）

    daily_replay_eligible / exact / ineligible / exception / critical
    window_replay_eligible / exact / exact_rate
    replay_gap_days（有决策但无 Replay 事件 → REPLAY_GAP）
    Eligibility Drift（eligible rate < 100% → NOT_PROVEN）
"""


def replay_accumulation_stats(daily_rows) -> dict:
    """daily_rows：qcfp_runtime_evidence_daily 最新 revision 行列表。"""
    rows = list(daily_rows or [])
    daily = []
    total_eligible = 0
    total_exact = 0
    total_ineligible = 0
    total_exception = 0
    total_critical = 0
    gap_days = []
    for r in rows:
        if str(r.get("status") or "").upper() == "NOT_APPLICABLE":
            continue
        eligible = int(r.get("replay_eligible") or 0)
        exact = int(r.get("replay_exact") or 0)
        ineligible = int(r.get("n_ineligible") or 0)
        exception = int(r.get("n_replay_exception") or 0)
        critical = int(r.get("critical_replay_mismatch") or 0)
        decisions = int(r.get("actual_decisions") or 0)
        total_eligible += eligible
        total_exact += exact
        total_ineligible += ineligible
        total_exception += exception
        total_critical += critical
        daily.append({"trade_date": r.get("trade_date"),
                      "replay_eligible": eligible,
                      "replay_exact": exact,
                      "replay_ineligible": ineligible,
                      "replay_exception": exception,
                      "critical_replay_mismatch": critical})
        if decisions > 0 and eligible == 0:
            gap_days.append(r.get("trade_date"))
    return {
        "daily": daily,
        "window_replay_eligible": total_eligible,
        "window_replay_exact": total_exact,
        "window_replay_ineligible": total_ineligible,
        "window_replay_exception": total_exception,
        "window_critical_mismatch": total_critical,
        "window_exact_rate": round(
            total_exact / total_eligible, 4) if total_eligible else 0.0,
        "window_eligible_rate": round(
            total_eligible / max(1, total_eligible + total_ineligible), 4),
        "replay_gap_days": gap_days,
        "rule": "REPLAY_GAP：有决策但无 Replay → 不是 0 mismatch 可自证",
    }


def evaluate_replay_accumulation(daily_rows) -> dict:
    """长期 Replay Gate：eligible>0、eligible==exact、critical=0、
    gap=0、exception=0。"""
    stats = replay_accumulation_stats(daily_rows)
    reasons = []
    if stats["replay_gap_days"]:
        reasons.append("REPLAY_GAP:" + ",".join(stats["replay_gap_days"]))
    if stats["window_replay_eligible"] == 0:
        reasons.append("REPLAY_MISSING")
    if stats["window_replay_eligible"] != stats["window_replay_exact"]:
        reasons.append("REPLAY_NOT_EXACT")
    if stats["window_critical_mismatch"] > 0:
        reasons.append("CRITICAL_REPLAY_MISMATCH")
    if stats["window_replay_exception"] > 0:
        reasons.append("REPLAY_EXCEPTION")
    if stats["window_eligible_rate"] < 1.0:
        reasons.append("REPLAY_ELIGIBILITY_DRIFT")
    state = "REPLAY_ACCUMULATION_OK" if not reasons else \
        ("REPLAY_GAP" if any(r.startswith("REPLAY_GAP")
                             for r in reasons) else
         "REPLAY_ELIGIBILITY_DRIFT" if any(
             r.startswith("REPLAY_ELIGIBILITY") for r in reasons) else
         "REPLAY_NOT_PROVEN")
    return {"state": state, "reasons": reasons,
            "stats": stats,
            "ok": not reasons,
            "rule": "长期连续 100%；任何 gap/drift/exception → 不通过"}
