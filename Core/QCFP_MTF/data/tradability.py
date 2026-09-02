# coding: utf-8
"""Tradability Governance（QCFP-MTF 2.8：35 号可交易状态治理）

状态：SUSPENDED / HALTED / NO_LIQUIDITY / CORPORATE_ACTION_PENDING /
      DELISTING / NOT_TRADABLE / NORMAL

这些状态不判断"股票好不好"，只判断"目标仓位现实上能不能执行"，
最终进入 Execution/Liquidity Cap（不是新评分）。
"""


# 新 35 号：Tradability 唯一权威状态（Backtest/Execution/Portfolio/
# Report 只能读取同一状态）
TRADABILITY_STATES = ("NORMAL", "SUSPENDED", "HALTED", "NO_VOLUME",
                      "CORPORATE_ACTION_PENDING", "DELISTING",
                      "NOT_ELIGIBLE")


def tradability_authority(state: str) -> dict:
    """唯一可交易状态权威：所有消费者只读此对象。"""
    state = str(state or "NORMAL").upper()
    if state not in TRADABILITY_STATES:
        state = "NOT_ELIGIBLE"
    scale = {
        "NORMAL": 1.0,
        "SUSPENDED": 0.0,
        "HALTED": 0.0,
        "NO_VOLUME": 0.0,
        "CORPORATE_ACTION_PENDING": 0.3,
        "DELISTING": 0.0,
        "NOT_ELIGIBLE": 0.0,
    }[state]
    return {
        "state": state,
        "execution_cap_scale": scale,
        "tradable": scale > 0.0,
        "authority": "TRADABILITY_AUTHORITY",
        "rule": "Tradability 只能降低执行权限，"
                "不能增加 Alpha / Permission",
    }


def tradability_status(suspended=False, halted=False, no_liquidity=False,
                       corporate_action_pending=False,
                       delisting=False, not_tradable=False,
                       adv_amount=None, min_adv=1e6) -> dict:
    """可交易状态 + Execution/Liquidity Cap 缩放。"""
    reasons = []
    if delisting:
        state, cap_scale, tradable = "DELISTING", 0.0, False
        reasons.append("DELISTING")
    elif not_tradable:
        state, cap_scale, tradable = "NOT_ELIGIBLE", 0.0, False
        reasons.append("NOT_ELIGIBLE")
    elif suspended:
        state, cap_scale, tradable = "SUSPENDED", 0.0, False
        reasons.append("SUSPENDED")
    elif halted:
        state, cap_scale, tradable = "HALTED", 0.0, False
        reasons.append("HALTED")
    elif no_liquidity or (adv_amount is not None
                          and float(adv_amount) < float(min_adv)):
        state, cap_scale, tradable = "NO_VOLUME", 0.0, False
        reasons.append("NO_VOLUME")
    elif corporate_action_pending:
        state, cap_scale, tradable = "CORPORATE_ACTION_PENDING", 0.3, True
        reasons.append("CORPORATE_ACTION_PENDING")
    else:
        state, cap_scale, tradable = "NORMAL", 1.0, True
    # 新 35 号：统一走唯一权威状态
    authority = tradability_authority(state)
    return {"state": authority["state"], "tradable": authority["tradable"],
            "execution_cap_scale": authority["execution_cap_scale"],
            "reasons": reasons}


def tradability_to_target(target, tradability: dict) -> dict:
    """把可交易状态作用到目标仓位（Execution/Liquidity Cap）。"""
    t = float(target or 0.0)
    scaled = t * tradability["execution_cap_scale"]
    return {"original_target": round(t, 4),
            "tradable_target": round(scaled, 4),
            "state": tradability["state"],
            "blocked": not tradability["tradable"]}


def tradability_hard_gate(proposal_target, tradability: dict) -> dict:
    """新 23 号：Execution Hard Gate（Governance → Tradability → Execution）。

    Tradability 只能降低/阻止 Execution，绝不能提高机会评分。
    """
    r = tradability_to_target(proposal_target, tradability)
    return {
        "proposal_target": r["original_target"],
        "executable_target": r["tradable_target"],
        "tradability_state": r["state"],
        "blocked": r["blocked"],
        "gate": "TRADABILITY_HARD_GATE",
        "rule": "理论上应该买 ≠ 实际可以买；"
                "可交易状态只能降低/阻止 Execution",
    }
