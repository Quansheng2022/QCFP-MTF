# coding: utf-8
"""ExecutableTarget（Release 2：新 15 号）

正式链：UniverseSnapshot → PIT Evidence → Canonical Decision →
FinalTarget → TradabilitySnapshot → MarketSession → ExecutableTarget

Tradability 只能降低/阻止 Execution；Session 原则：
    after_close signal → 不允许假设当日收盘价已成交，
    必须明确下一可执行 session。
"""

from ..data.asof_contract import trading_session_contract
from ..data.tradability import tradability_authority


def executable_target_chain(final_target, tradability_state="NORMAL",
                            session="continuous_session",
                            available_time="", decision_time="",
                            execution_time="") -> dict:
    """FinalTarget → Tradability → MarketSession → ExecutableTarget。"""
    trad = tradability_authority(tradability_state)
    base = float(final_target or 0.0) * trad["execution_cap_scale"]
    session_cfg = trading_session_contract(available_time, decision_time,
                                           session)
    session_scale = 0.5 if session == "half_day" else 1.0
    executable = base * session_scale
    blocked = not trad["tradable"] or session == "suspension"
    return {
        "final_target": round(float(final_target or 0.0), 4),
        "tradability_state": trad["state"],
        "tradability_scale": trad["execution_cap_scale"],
        "session": session,
        "session_scale": session_scale,
        "next_session_required": session_cfg["next_tradable_session_required"],
        "executable_target": round(executable, 4),
        "blocked": blocked,
        "rule": "Tradability 只能降低/阻止 Execution，"
                "不能提高 Permission/Wave/FinalTarget",
    }
