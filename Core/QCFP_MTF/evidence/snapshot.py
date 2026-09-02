# coding: utf-8
"""DecisionEvidenceSnapshot（2.3：决策链入口的证据/PIT 面板）

PIT Evidence Contract：任何输入只有满足 available_at <= decision_time
才能进入 Decision Engine；本模块负责统一 Q/M/W/D/Flow/Universe 的 as-of 时间，
防止 Backtest / Shadow / Report 各自对时产生"看着正确但时间越界"的差异。
"""

import pandas as pd


class EvidenceContractError(ValueError):
    pass


PIT_ERROR = EvidenceContractError   # 2.6 别名：PIT 硬门错误类型


def build_evidence_snapshot(row: dict) -> dict:
    """从一行决策数据组装统一证据快照（带每层 as-of 时间戳）"""
    def _get(*keys):
        for k in keys:
            if row.get(k) is not None:
                return row.get(k)
        return None

    return {
        "decision_date": _get("decision_date", "date"),
        "quarterly": {
            "period_end": _get("period_end", "q_period_end"),
            "available_at": _get("structural_available_date",
                                 "q_available_date", "available_date"),
            "source": _get("q_source", "source") or "db",
            "revision": _get("q_revision", "revision") or "1",
            "restatement": _get("q_restatement", "restatement") or "none",
            "c_state": _get("c_state"), "f_state": _get("f_state"),
            "p_state": _get("p_state"),
            "prev_f_state": _get("prev_f_state"),
            "q_position_52w": _get("q_position_52w"),
        },
        "monthly": {
            "month_end": _get("month_end", "m_month_end"),
            "available_at": _get("m_available_date", "monthly_available_date"),
            "source": _get("m_source", "source") or "db",
            "revision": _get("m_revision", "revision") or "1",
            "restatement": _get("m_restatement", "restatement") or "none",
            "monthly_behavior_state": _get("monthly_behavior_state"),
        },
        "weekly": {
            "week_end": _get("week_end", "w_week_end"),
            "available_at": _get("w_available_date", "weekly_available_date"),
            "source": _get("w_source", "source") or "db",
            "revision": _get("w_revision", "revision") or "1",
            "restatement": _get("w_restatement", "restatement") or "none",
            "tactical_signal": _get("tactical_signal"),
        },
        "daily": {
            "trade_date": _get("daily_date", "trade_date", "d_trade_date"),
            "available_at": _get("d_available_date", "daily_available_date"),
            "source": _get("d_source", "source") or "db",
            "revision": _get("d_revision", "revision") or "1",
            "restatement": _get("d_restatement", "restatement") or "none",
            "daily_state": _get("daily_state"),
        },
        "flow": {
            "available_at": _get("flow_available_date"),
        },
        "universe": {
            "valid_from": _get("universe_valid_from"),
            "valid_to": _get("universe_valid_to"),
        },
        "risk": {
            "risk_level": _get("risk_level"),
            "des_score": _get("des_score"),
            "stop_triggered": _get("stop_triggered"),
        },
        "context": {
            "market_context": _get("market_context"),
            "data_quality": _get("data_quality"),
            "chip_stability_confidence": _get("chip_stability_confidence"),
            "structure_behavior_alignment":
                _get("structure_behavior_alignment"),
        },
    }


def assert_evidence_asof(evidence: dict) -> None:
    """PIT Evidence Contract：所有可用时间 <= 决策日，违反即抛错"""
    decision_date = evidence.get("decision_date")
    if not decision_date:
        return
    dd = pd.Timestamp(decision_date)
    bad = []
    for layer in ("quarterly", "monthly", "weekly", "daily", "flow"):
        meta = evidence.get(layer) or {}
        at = meta.get("available_at")
        if at and pd.Timestamp(at) > dd:
            bad.append(f"{layer}.available_at={at}")
    if bad:
        raise EvidenceContractError(
            f"PIT Evidence Contract 违反：可用时间晚于决策日 {decision_date}"
            f"：{'; '.join(bad)}")
    return None


def grade_evidence(row: dict, settings=None) -> tuple:
    """PIT / 证据分级（2.5：禁止写 Ledger 时硬编码）

    PIT：
        A  真实披露表存在且覆盖该 (stock, period_end)
        B  真实披露体系存在但该记录未覆盖（估算）
        C  无真实披露表，period_end+lag 估算
        D  无可用日期
    Evidence：由数据质量映射（A/B/C/D）
    返回 (pit_grade, evidence_grade, reasons)
    """
    from ..common.asof import load_disclosure_overrides
    overrides = load_disclosure_overrides()
    code, period = row.get("stock_code"), row.get("period_end")
    period = period or row.get("q_period_end")
    dq = row.get("data_quality") or "C"
    reasons = [f"dq={dq}"]
    if overrides:
        if code and period and (str(code).zfill(5), str(period)) in overrides:
            pit = "A"
            reasons.append("disclosure_override_matched")
        else:
            pit = "B"
            reasons.append("disclosure_override_unmatched")
    elif (row.get("available_date") or row.get("structural_available_date")
          or row.get("q_available_date")):
        pit = "C"
        reasons.append("estimated_period_end_lag")
    else:
        pit = "D"
        reasons.append("no_available_date")
    evidence = dq if dq in ("A", "B", "C", "D") else "C"
    return pit, evidence, tuple(reasons)
