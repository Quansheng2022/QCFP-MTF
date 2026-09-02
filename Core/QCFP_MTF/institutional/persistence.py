# coding: utf-8
"""Institutional Persistence（连续 F↑ 季度数，0~4）"""


def institutional_persistence(f_state, prev_f_state=None, streak=None) -> int:
    if streak is not None:
        return max(0, min(4, int(streak)))
    if f_state == "F↑":
        return 2 if prev_f_state == "F↑" else 1
    return 0
