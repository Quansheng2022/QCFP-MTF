# coding: utf-8
"""Swing Setup Engine（波段机会识别）

职责：Q/M/W/D 信号 → setup_type（NONE / BREAKOUT / PULLBACK / ACCUMULATION / RECOVERY）。
FSM 不自己推导 Setup（RULE 08：Setup ≠ Position State）。
"""


def evaluate_swing_setup(weekly_signal=None, daily_state=None,
                         monthly_state=None, permission=None) -> str:
    weekly = weekly_signal or "Consolidation"
    daily = daily_state or "DAILY_NEUTRAL"
    if weekly == "Breakout" and daily in ("DAILY_BREAKOUT", "DAILY_PULLBACK"):
        return "BREAKOUT"
    if weekly == "Pullback" and daily == "DAILY_PULLBACK":
        return "PULLBACK"
    if daily == "DAILY_ACCUMULATION":
        return "ACCUMULATION"
    if permission == "TEST" and weekly == "Breakout":
        return "RECOVERY"
    return "NONE"
