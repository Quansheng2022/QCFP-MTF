# coding: utf-8
"""Participation Budget（QCFP-MTF 2.4：四层架构中间层）

    Institutional Permission（机构层面最多允许承担多少风险）
        ↓
    Participation Budget（当前市场环境下，允许拿多少钱参与探索）
        ↓
    Swing FSM（这笔交易目前处于什么生命周期）
        ↓
    Position Sizing（最终实际拿多少仓位）

模式：
    STAND   不参与（BLOCK / WATCH 无 Setup / 风险过高）
    OBSERVE 观察仓（WATCH + Setup + 低/中风险，上限 observe，探索性暴露）
    EXPLORE 试仓（TEST）
    TRADE   正式交易（ALLOW / STRONG_ALLOW）

关键语义：OBSERVE 是权限授予的"观察例外"——小预算、有 Setup、低风险，
不改变 Permission（仍为 WATCH），只是允许以观察仓参与，解决
"WATCH 一律空仓 → 2024 大波段 100% 错过"的矛盾。
"""

from dataclasses import dataclass

from ..config.settings import retail_settings


@dataclass(frozen=True)
class ParticipationBudget:
    mode: str        # STAND / OBSERVE / EXPLORE / TRADE
    cap: float       # 数值预算上限
    reason: str = ""


def evaluate_participation_budget(permission, market_context=None,
                                  risk_level=None, setup_type=None,
                                  settings=None,
                                  allow_observation=True) -> ParticipationBudget:
    cfg = retail_settings(settings).get("participation_budget", {})
    scale = float((cfg.get("market_scale") or {}).get(
        market_context, 1.0)) if market_context else 1.0
    observe_cap = float(cfg.get("observe", 0.05)) * scale
    test_cap = float(cfg.get("test", 0.10)) * scale
    allow_cap = float(cfg.get("allow", 0.50)) * scale
    strong_cap = float(cfg.get("strong", 0.70)) * scale
    if permission == "BLOCK":
        return ParticipationBudget("STAND", 0.0, "permission_block")
    if permission == "WATCH":
        if allow_observation \
                and setup_type not in (None, "NONE") \
                and risk_level in ("Low", "Medium"):
            return ParticipationBudget(
                "OBSERVE", round(observe_cap, 4),
                f"watch_observation@market_{market_context or 'none'}")
        return ParticipationBudget(
            "STAND", 0.0,
            "observation_disabled" if not allow_observation
            else "watch_no_setup_or_high_risk")
    if permission == "TEST":
        return ParticipationBudget("EXPLORE", round(test_cap, 4),
                                   f"test@market_{market_context or 'none'}")
    if permission == "ALLOW":
        return ParticipationBudget("TRADE", round(allow_cap, 4),
                                   f"allow@market_{market_context or 'none'}")
    if permission == "STRONG_ALLOW":
        return ParticipationBudget("TRADE", round(strong_cap, 4),
                                   f"strong_allow@market_{market_context or 'none'}")
    return ParticipationBudget("STAND", 0.0, "unknown_permission")
