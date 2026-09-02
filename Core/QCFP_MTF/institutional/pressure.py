# coding: utf-8
"""Institutional Pressure（+2 强吸筹 ~ -2 强派发）"""


def institutional_pressure(c_state, f_state) -> int:
    s = {"C↑": 1, "C→": 0, "C↓": -1}.get(c_state, 0)
    s += {"F↑": 1, "F→": 0, "F↓": -1}.get(f_state, 0)
    return max(-2, min(2, s))
