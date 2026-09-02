# coding: utf-8
"""Retail Position Sizing Engine（仓位尺寸，与 FSM 状态解耦）

RULE 05：Position Sizing 拥有数值仓位目标；FSM 只决定状态。
加法阶梯（禁止乘法加仓）：TESTING→10%、BUILDING→+build_step、TRIMMING→-trim_step。
默认值仅为工程占位，不视为回测验证参数。

2.8（P1-3/㉗ Progressive Position Sizing）：
    TEST → BUILD → CONFIRM → FULL 四级递进：
        TEST     观察仓（默认 2%）
        BUILD    确认后加仓（默认 +3%）
        CONFIRM  再确认后加仓（默认 +3%）
        FULL     完全确认（到达 max_position 前）
    加仓必须重过 Permission + Wave + Risk + Portfolio Governance
    （add_requalification），不满足 → 停在当前档。
"""

from ..config.settings import retail_settings


PROGRESSIVE_STAGES = ("TEST", "BUILD", "CONFIRM", "FULL")


def retail_target_position(fsm_state, current_position, settings) -> float:
    cfg = retail_settings(settings).get("fsm", {}).get("position", {})
    test_size = float(cfg.get("test", 0.10))
    build_step = float(cfg.get("build_step", 0.10))
    trim_step = float(cfg.get("trim_step", 0.15))
    max_position = float(cfg.get("max_position", 0.70))
    cur = float(current_position or 0.0)
    if fsm_state == "TESTING":
        return round(max(cur, test_size), 4)
    if fsm_state == "BUILDING":
        return round(min(cur + build_step, max_position), 4)
    if fsm_state == "HOLDING":
        return round(cur, 4)
    if fsm_state == "TRIMMING":
        return round(max(0.0, cur - trim_step), 4)
    return 0.0   # FLAT / EXITING / COOLDOWN


def risk_budget_target(risk_budget, stop_distance, permission_cap=0.70,
                       portfolio_cap=1.0, liquidity_cap=1.0) -> float:
    """风险预算分配（2.7）：目标仓位 = min(risk_budget / stop_distance, 各 cap)

    仓位不是因为"信号强"而变大，而是因为"单位风险收益比值得承担更多风险"。
    """
    if float(stop_distance or 0.0) <= 0:
        return 0.0
    risk_target = float(risk_budget or 0.0) / float(stop_distance)
    return round(min(risk_target, float(permission_cap), float(portfolio_cap),
                     float(liquidity_cap)), 4)


def progressive_position_sizes(settings) -> dict:
    """四级递进仓位档位（2.8）：
        TEST=0.02, BUILD=0.05, CONFIRM=0.08, FULL=0.12（上限由治理 cap 收敛）
    """
    cfg = retail_settings(settings).get("progressive", {})
    return {
        "TEST": round(float(cfg.get("test", 0.02)), 4),
        "BUILD": round(float(cfg.get("build", 0.05)), 4),
        "CONFIRM": round(float(cfg.get("confirm", 0.08)), 4),
        "FULL": round(float(cfg.get("full", 0.12)), 4),
    }


def progressive_target_position(stage, current_position, settings,
                                permission_cap=0.70) -> float:
    """按递进阶段返回目标仓位（只升不降、不超过 permission_cap）。

    stage 非法 → 返回 current_position（不改变仓位）。
    与 retail_target_position 的区别：后者由 FSM 驱动，本函数由
    "确认证据"驱动，二者可组合（FSM 允许 + 证据推进 → 才加仓）。
    """
    sizes = progressive_position_sizes(settings)
    cur = float(current_position or 0.0)
    if stage not in sizes:
        return round(cur, 4)
    target = max(cur, sizes[stage])
    cap = float(permission_cap or 0.70)
    return round(min(target, cap), 4)


def add_requalification(permission, wave_strength, risk_level,
                        portfolio_state, current_stage,
                        min_permission="ALLOW",
                        min_wave_strength=0.6,
                        allowed_risk=("Low", "Medium"),
                        allowed_portfolio=("NORMAL", "DEFENSIVE")) -> tuple:
    """加仓重过门（2.8）：每次递进加仓必须全部满足：
        Permission ≥ ALLOW + Wave ≥ 阈值 + Risk ≤ Medium +
        Portfolio 非 RISK_OFF/OVERHEATED + 当前未到 FULL
    返回 (allowed, reasons)。
    """
    from .permission_policy import permission_level
    reasons = []
    if permission_level(permission) < permission_level(min_permission):
        reasons.append(f"PERMISSION_BELOW_{min_permission}")
    if float(wave_strength or 0.0) < float(min_wave_strength):
        reasons.append(f"WAVE_BELOW_{min_wave_strength:.0%}")
    if risk_level not in allowed_risk:
        reasons.append("RISK_TOO_HIGH_FOR_ADD")
    if portfolio_state not in allowed_portfolio:
        reasons.append(f"PORTFOLIO_{portfolio_state}_BLOCKS_ADD")
    if current_stage == "FULL":
        reasons.append("ALREADY_FULL")
    return not reasons, tuple(reasons)


def next_progressive_stage(current_stage, requalified: bool,
                           has_new_confirmation: bool = True) -> str:
    """递进推进：TEST → BUILD → CONFIRM → FULL。
    要求（1）重过门通过（2）有新确认证据；否则停在当前档。
    """
    order = PROGRESSIVE_STAGES
    if current_stage not in order:
        return "TEST"
    if not requalified or not has_new_confirmation:
        return current_stage
    idx = order.index(current_stage)
    return order[min(idx + 1, len(order) - 1)]
