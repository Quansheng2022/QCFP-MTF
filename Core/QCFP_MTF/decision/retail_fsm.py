# coding: utf-8
"""薄转发：Retail Position FSM（正式实现见 decision.retail_position_fsm）

QCFP-MTF 2.2 收口：FSM 唯一事实源 = retail_position_fsm.py。
本模块仅为兼容旧调用（state, row, settings → 新 Context 引擎）。
"""

from .retail_position_fsm import (RetailDecisionContext, build_fsm_timeline,
                                  chase_filter,
                                  next_state as _next_state)


def next_state(state, row, settings):
    """旧接口兼容：dict row → RetailDecisionContext → 新 FSM"""
    ctx = RetailDecisionContext.from_row(row, settings)
    return _next_state(state, ctx)


__all__ = ["next_state", "chase_filter", "build_fsm_timeline",
           "RetailDecisionContext"]
