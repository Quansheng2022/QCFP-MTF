# coding: utf-8
"""Institutional Divergence（背离 → 权限降级条件）"""


def institutional_divergence(structure_alignment=None, divergence_flags=None) -> bool:
    """结构-行为背离 / CPD/FPD/CFD 背离任一命中即为 True"""
    if divergence_flags is not None:
        return bool(divergence_flags)
    return structure_alignment == "Divergence"
