# coding: utf-8
"""Drawdown Response Engine（QCFP-MTF 2.8：44 号回撤响应引擎）

不能等 MDD 达到最大值才处理：
    0–3%  → NORMAL
    3–5%  → CAUTION
    5–8%  → DEFENSIVE
    8%+   → SAFE_MODE

动态调整：新仓上限 / 加仓权限 / 总风险预算 / Wave 确认 / 退出阈值 / 现金比。
原则：亏损越大，系统承担的新风险越小（避免回撤期加码翻本）。
"""

from dataclasses import asdict, dataclass, field


def drawdown_state(drawdown_pct) -> str:
    """回撤 → 状态（NORMAL/CAUTION/DEFENSIVE/SAFE_MODE）。"""
    d = abs(float(drawdown_pct or 0.0))
    if d >= 0.08:
        return "SAFE_MODE"
    if d >= 0.05:
        return "DEFENSIVE"
    if d >= 0.03:
        return "CAUTION"
    return "NORMAL"


@dataclass(frozen=True)
class DrawdownResponse:
    drawdown_pct: float
    state: str
    new_entry_cap_scale: float
    add_allowed: bool
    risk_budget_scale: float
    require_wave_confirmation: bool
    exit_threshold_scale: float    # >1 = 退出更敏感
    cash_ratio_floor: float
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def drawdown_response(drawdown_pct) -> DrawdownResponse:
    """回撤响应：亏损越大 → 新风险越小、退出越敏感。"""
    state = drawdown_state(drawdown_pct)
    d = abs(float(drawdown_pct or 0.0))
    if state == "SAFE_MODE":
        resp = dict(new_entry_cap_scale=0.0, add_allowed=False,
                    risk_budget_scale=0.2, require_wave_confirmation=True,
                    exit_threshold_scale=1.3, cash_ratio_floor=0.7,
                    reason=("DD_8PCT_SAFE_MODE",))
    elif state == "DEFENSIVE":
        resp = dict(new_entry_cap_scale=0.3, add_allowed=False,
                    risk_budget_scale=0.5, require_wave_confirmation=True,
                    exit_threshold_scale=1.2, cash_ratio_floor=0.5,
                    reason=("DD_5PCT_DEFENSIVE",))
    elif state == "CAUTION":
        resp = dict(new_entry_cap_scale=0.6, add_allowed=True,
                    risk_budget_scale=0.7, require_wave_confirmation=True,
                    exit_threshold_scale=1.1, cash_ratio_floor=0.3,
                    reason=("DD_3PCT_CAUTION",))
    else:
        resp = dict(new_entry_cap_scale=1.0, add_allowed=True,
                    risk_budget_scale=1.0, require_wave_confirmation=False,
                    exit_threshold_scale=1.0, cash_ratio_floor=0.1,
                    reason=("DD_NORMAL",))
    return DrawdownResponse(
        drawdown_pct=round(d, 4), state=state,
        new_entry_cap_scale=resp["new_entry_cap_scale"],
        add_allowed=resp["add_allowed"],
        risk_budget_scale=resp["risk_budget_scale"],
        require_wave_confirmation=resp["require_wave_confirmation"],
        exit_threshold_scale=resp["exit_threshold_scale"],
        cash_ratio_floor=resp["cash_ratio_floor"],
        reasons=(resp["reason"],))


def apply_drawdown_gate(drawdown_pct, target, previous_position,
                        current_cash_ratio=0.5) -> dict:
    """回撤门：直接把回撤响应作用到目标仓位。"""
    r = drawdown_response(drawdown_pct)
    t = float(target or 0.0)
    prev = float(previous_position or 0.0)
    if not r.add_allowed and t > prev + 1e-9:
        t = min(t, prev)
    t = t * r.new_entry_cap_scale
    cash = max(float(current_cash_ratio or 0.0), r.cash_ratio_floor)
    return {"target": round(t, 4), "cash_ratio_floor": cash,
            "response": r.as_dict()}
