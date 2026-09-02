# coding: utf-8
"""MTF 战术状态机（FSM-2）

State(t+1) = Align(Structural(t+1), Stage(t+1), Trigger(t+1))
判定表与层级不可越权规则统一收口在 mtf_alignment.align_mtf。
"""

from .mtf_alignment import align_mtf


def next_mtf_state(current_state, structural, stage, trigger,
                   tactical_override: bool = False,
                   position_52w=None, max_52w_position: float = 0.15):
    """给定当前 MTF 状态与新事件，返回下一状态。

    实现说明：MTF 状态由三层当前输入决定（规格书 FSM-2 定义），
    不依赖历史状态；current_state 仅用于日志/校验上下文。
    """
    return align_mtf(structural, stage, trigger,
                     tactical_override=tactical_override,
                     position_52w=position_52w,
                     max_52w_position=max_52w_position)
