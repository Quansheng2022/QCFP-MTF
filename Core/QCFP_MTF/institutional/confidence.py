# coding: utf-8
"""Institutional Confidence（过滤器置信度 High/Medium/Low）"""


def institutional_confidence(state, persistence, chip_confidence=None,
                             data_quality=None) -> str:
    if state in ("UNKNOWN",) or data_quality == "D":
        return "Low"
    base = {"ACCUMULATION": 2, "ACCUMULATION_WEAK": 1, "RECOVERY": 1,
            "NEUTRAL": 1, "DISTRIBUTION": 1, "DISTRIBUTION_STRONG": 2,
            "CAPITULATION": 2}.get(state, 1)
    base += persistence
    if chip_confidence == "High":
        base += 1
    if base >= 4:
        return "High"
    if base >= 2:
        return "Medium"
    return "Low"
