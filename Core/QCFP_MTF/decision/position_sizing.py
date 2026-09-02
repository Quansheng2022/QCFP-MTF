# coding: utf-8
"""仓位管理：Risk Level → 仓位上限，与 MTF 基础仓位取小（Risk 真正成为 Decision Gate）"""


def risk_cap(risk_level: str, settings) -> float:
    caps = settings.get("decision", {}).get("position_cap", {})
    return float(caps.get(risk_level, 1.0))


def base_position(mtf_regime: str, settings) -> float:
    base = settings.get("decision", {}).get("base_position", {})
    return float(base.get(mtf_regime, 0.0))


def effective_position(mtf_regime: str, risk_level: str, settings) -> float:
    """最终目标仓位 = min(MTF 基础仓位, Risk 上限)"""
    return effective_position_cqs(mtf_regime, risk_level, settings,
                                  catalyst_score=None, tactical_override=False)


def effective_position_cqs(mtf_regime: str, risk_level: str, settings,
                           catalyst_score=None, tactical_override: bool = False) -> float:
    """方案 B 动态仓位：
    - 常规路径：min(MTF 基础仓位, Risk 上限)
    - 战术试多（tactical_override=True）：min(CQS 观察仓, Risk 上限)
    """
    if tactical_override:
        from .catalyst_quality import observation_position
        score = catalyst_score if catalyst_score is not None else 0
        base = observation_position(score, settings)
    else:
        base = base_position(mtf_regime, settings)
    return min(base, risk_cap(risk_level, settings))
