# coding: utf-8
"""Conflict Resolution Engine（QCFP-MTF 2.8：56 号信号冲突解决）

固定优先级（高→低）：
    Governance > Permission > Risk > Portfolio > Regime > Liquidity > FSM
    > Wave > Entry Signal（Decision Authority Hierarchy：上层可限制下层，
    下层不能推翻上层）

每次冲突输出 conflict_id / winning_rule / suppressed / reason，
避免"多个模块各自有理，最后却不可解释"。

2.8（56 号）：补 Governance / Portfolio / Liquidity 三层。
"""

CONFLICT_PRIORITY = ["GOVERNANCE_BLOCK", "HARD_EXIT", "RISK_BLOCK",
                     "INSTITUTIONAL_PERMISSION", "PORTFOLIO_BLOCK",
                     "REGIME_BLOCK", "LIQUIDITY_BLOCK", "FSM", "WAVE",
                     "SETUP",
                     "TECHNICAL_TRIGGER"]


def resolve_conflict(exit_event_kind="NONE", risk_level="Medium",
                     permission="WATCH", fsm_next="FLAT",
                     wave_strength=0.0, setup_type=None,
                     daily_state="DAILY_NEUTRAL",
                     governance_failed=False,
                     portfolio_state="NORMAL",
                     liquidity_flag="LIQUIDITY_OK",
                     market_regime="") -> dict:
    signals = {}
    if governance_failed:
        signals["GOVERNANCE_BLOCK"] = "GOVERNANCE_FAIL"
    if exit_event_kind not in (None, "NONE"):
        signals["HARD_EXIT"] = exit_event_kind
    if risk_level in ("High", "Extreme"):
        signals["RISK_BLOCK"] = risk_level
    if permission in ("BLOCK", "WATCH"):
        signals["INSTITUTIONAL_PERMISSION"] = permission
    if portfolio_state in ("RISK_OFF", "OVERHEATED", "CONCENTRATED"):
        signals["PORTFOLIO_BLOCK"] = portfolio_state
    if market_regime in ("Bear", "Crisis"):
        signals["REGIME_BLOCK"] = market_regime
    if liquidity_flag == "LIQUIDITY_LOW":
        signals["LIQUIDITY_BLOCK"] = liquidity_flag
    if fsm_next and fsm_next != "FLAT":
        signals["FSM"] = fsm_next
    if wave_strength is not None and float(wave_strength) >= 0.5:
        signals["WAVE"] = "STRONG"
    if setup_type not in (None, "NONE"):
        signals["SETUP"] = setup_type
    if daily_state in ("DAILY_BREAKOUT", "DAILY_ACCUMULATION"):
        signals["TECHNICAL_TRIGGER"] = daily_state
    order = {s: i for i, s in enumerate(CONFLICT_PRIORITY)}
    ranked = sorted(signals.items(), key=lambda kv: order.get(kv[0], 99))
    if not ranked:
        return {"conflict_id": None, "winning_rule": "NONE",
                "winning_value": None, "suppressed": [], "reason": ""}
    winning, wval = ranked[0]
    suppressed = [s for s, _ in ranked[1:]]
    return {
        "conflict_id": f"{winning}|{wval}",
        "winning_rule": winning,
        "winning_value": wval,
        "suppressed": suppressed,
        "reason": f"{winning} 优先于 {suppressed}" if suppressed
        else f"{winning} 无冲突",
    }
