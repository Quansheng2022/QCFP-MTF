# coding: utf-8
"""Strategy Kill Criteria（QCFP-MTF 2.8：96 号策略终止标准）

与 Risk Hard Exit（个股/市场退出）不同，Strategy Kill 指
整个策略版本不再有资格产生交易：
    PIT integrity failure / Ledger integrity failure /
    Repeated replay mismatch / Severe governance breach /
    Persistent OOS deterioration / Execution assumptions invalid /
    Certification expired
状态：PRODUCTION → SUSPENDED（不能继续交易等人工慢慢调查）。

验收标准：明确区分 Trade Exit / Strategy Suspend / System Halt，
三者不能混为一谈。
"""


STRATEGY_KILL_CRITERIA = (
    "pit_integrity_failure", "ledger_integrity_failure",
    "repeated_replay_mismatch", "severe_governance_breach",
    "persistent_oos_deterioration",
    "execution_assumptions_invalid", "certification_expired",
)


def strategy_kill_check(criteria: dict) -> dict:
    """criteria：{criterion: bool}；任一命中 → SUSPENDED。"""
    active = [c for c in STRATEGY_KILL_CRITERIA
              if criteria.get(c)]
    return {
        "active_criteria": active,
        "verdict": "SUSPENDED" if active else "PRODUCTION",
        "halt_new_decisions": bool(active),
        "rule": "策略级终止 ≠ 个股退出 ≠ 系统停机",
    }


def classify_control_event(event_kind: str) -> dict:
    """区分 Trade Exit / Strategy Suspend / System Halt。"""
    mapping = {
        "TRADE_EXIT": {"scope": "单只股票/仓位",
                       "action": "退出该仓位"},
        "STRATEGY_SUSPEND": {"scope": "整个策略版本",
                             "action": "停止产生新交易指令"},
        "SYSTEM_HALT": {"scope": "系统本身",
                        "action": "停止所有未验证输出并进入调查"},
    }
    info = mapping.get(str(event_kind).upper())
    if not info:
        return {"event_kind": event_kind, "classified": False,
                "note": "无法归入三类，责任边界不清"}
    return {"event_kind": event_kind, "classified": True, **info}


def strategy_not_stock_answer(criteria: dict) -> dict:
    """新 96 号：回答"什么时候不是股票错了，而是整个策略已经没有资格
    继续交易？"。"""
    active = [c for c in STRATEGY_KILL_CRITERIA
              if criteria.get(c)]
    if active:
        return {"strategy_level": True,
                "verdict": "STRATEGY_SUSPENDED",
                "active_criteria": active,
                "answer": "不是单只股票错了，而是整个 StrategyVersion "
                          "SUSPENDED（停止产生新决策）"}
    return {"strategy_level": False,
            "verdict": "STRATEGY_ACTIVE",
            "active_criteria": [],
            "answer": "策略仍可交易；个股退出由 Trade Exit 处理"}
