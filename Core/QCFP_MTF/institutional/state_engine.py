# coding: utf-8
"""Institutional State Engine（C/F/P → 机构行为状态）"""


def institutional_state(c_state, f_state, p_state=None) -> str:
    """机构行为状态：ACCUMULATION / ACCUMULATION_WEAK / NEUTRAL / RECOVERY /
    DISTRIBUTION / DISTRIBUTION_STRONG / CAPITULATION / UNKNOWN"""
    if c_state is None or f_state is None:
        return "UNKNOWN"
    if c_state == "C↓" and f_state == "F↓":
        return "CAPITULATION" if p_state == "P↓" else "DISTRIBUTION_STRONG"
    if c_state == "C↓" and f_state in ("F→", "F↓"):
        return "DISTRIBUTION"
    if c_state in ("C→", "C↓") and f_state == "F↑":
        return "RECOVERY"
    if c_state in ("C↑", "C→") and f_state == "F↑":
        return "ACCUMULATION" if p_state == "P↑" else "ACCUMULATION_WEAK"
    if c_state == "C↑" and f_state == "F→":
        return "ACCUMULATION_WEAK"
    return "NEUTRAL"
