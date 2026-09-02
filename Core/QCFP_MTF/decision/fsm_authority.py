# coding: utf-8
"""FSM State Authority（QCFP-MTF 2.8：8 号 FSM 唯一持仓状态解释器）

任何仓位变化都必须是 FSM 合法状态转移/状态的结果：
    - 目标增加  → 只能出现在 TESTING / BUILDING（建仓/加仓状态）
    - 目标为 0  → 只能停留在 FLAT / EXITING / COOLDOWN
    - 目标 > 0  → 必须停留在风险承载状态（TESTING/BUILDING/HOLDING/TRIMMING）
    - 目标减少  → 风险降低方向，允许（无需强制状态跳变）

接入 record_snapshot：无法解释的目标变化 → 拒绝写入 Ledger。
"""


INCREASE_STATES = ("TESTING", "BUILDING")
ZERO_POSITION_STATES = ("FLAT", "EXITING", "COOLDOWN")
RISK_BEARING_STATES = ("TESTING", "BUILDING", "HOLDING", "TRIMMING")


class FSMStateAuthorityError(ValueError):
    pass


def assert_fsm_explains_target_change(prev_state, next_state, prev_pos,
                                      new_pos, reason="") -> bool:
    """校验目标变化可被 FSM 解释；违规 → FSMStateAuthorityError。"""
    prev_pos = float(prev_pos or 0.0)
    new_pos = float(new_pos or 0.0)
    nxt = str(next_state or "FLAT")
    prev = str(prev_state or "FLAT")
    delta = new_pos - prev_pos
    if delta > 1e-9 and nxt not in INCREASE_STATES:
        raise FSMStateAuthorityError(
            f"FSM: 目标增加 {prev_pos:.2f}→{new_pos:.2f} 但状态 "
            f"{prev}→{nxt} 非建仓/加仓状态（{INCREASE_STATES}）"
            f" reason={reason}")
    if new_pos <= 1e-9 and nxt not in ZERO_POSITION_STATES:
        raise FSMStateAuthorityError(
            f"FSM: 目标=0 但状态停留在 {nxt}（应在 "
            f"{ZERO_POSITION_STATES}）")
    if new_pos > 1e-9 and nxt not in RISK_BEARING_STATES:
        raise FSMStateAuthorityError(
            f"FSM: 目标={new_pos:.2f} > 0 但状态为 {nxt}（应在 "
            f"{RISK_BEARING_STATES}）")
    return True
