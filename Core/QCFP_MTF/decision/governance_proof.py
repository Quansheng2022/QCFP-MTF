# coding: utf-8
"""Governance Proof Engine（QCFP-MTF 2.8：前置不可越权证明）

不是"Decision 之后发现问题"，而是：
    Governance Proof → PASS → 才允许输出正式 Decision。

proof 字段：permission / raw_target / governed_target / permission_cap /
           risk_cap / budget_cap / portfolio_cap / liquidity_cap /
           execution_cap / sector_cap / theme_cap / drawdown_cap /
           final_target / violations / proof(PASS|FAIL)

2.8（3/4/9 号）：proof 只能由 prove() 计算（禁止调用方设置），
并记录 raw→governed→final 全链与全部硬约束 cap。
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GovernanceProof:
    permission: str
    participation_mode: str
    raw_target: float
    permission_cap: float
    risk_cap: float
    budget_cap: float
    final_target: float
    governed_target: float = 0.0
    portfolio_cap: float = 1.0
    liquidity_cap: float = 1.0
    execution_cap: float = 1.0
    sector_cap: float = 1.0
    theme_cap: float = 1.0
    drawdown_cap: float = 1.0
    previous_position: float = 0.0
    hard_exit: bool = False
    data_quality: str = "B"
    violations: tuple = ()
    proof: str = "PASS"

    def as_dict(self) -> dict:
        d = asdict(self)
        d["violations"] = list(self.violations)
        return d


def prove(permission, participation_mode, permission_cap, risk_cap,
          budget_cap, raw_target, final_target, previous_position=0.0,
          hard_exit=False, data_quality="B", governed_target=None,
          portfolio_cap=1.0, liquidity_cap=1.0, execution_cap=1.0,
          sector_cap=1.0, theme_cap=1.0, drawdown_cap=1.0) -> GovernanceProof:
    """前置证明：任一违反 → proof=FAIL（引擎不得输出 Decision）"""
    violations = []
    t = float(final_target or 0.0)
    prev = float(previous_position or 0.0)
    if hard_exit and t > 1e-9:
        violations.append("HARD_EXIT_TARGET_NONZERO")
    if permission == "BLOCK" and t > max(prev, 1e-9) + 1e-9:
        violations.append("BLOCK_TARGET_NONZERO")
    if permission == "WATCH" and participation_mode != "OBSERVE" \
            and t > prev + 1e-9:
        violations.append("WATCH_NON_OBSERVE_RISK_INCREASE")
    if permission == "WATCH" and participation_mode == "OBSERVE" \
            and t > max(prev, budget_cap) + 1e-9:
        violations.append("OBSERVE_EXCEEDS_BUDGET")
    hard_caps = min(permission_cap, budget_cap, portfolio_cap,
                    liquidity_cap, execution_cap, sector_cap, theme_cap,
                    drawdown_cap)
    if t > max(prev, hard_caps) + 1e-9:
        violations.append("FINAL_EXCEEDS_CAPS")
    governed = round(float(governed_target if governed_target is not None
                           else t), 4)
    if governed > max(prev, min(permission_cap, budget_cap)) + 1e-9:
        violations.append("GOVERNED_EXCEEDS_PERMISSION_BUDGET")
    if data_quality == "D" and t > 1e-9:
        violations.append("DATA_QUALITY_D_TRADE")
    proof = "FAIL" if violations else "PASS"
    return GovernanceProof(
        permission=permission, participation_mode=participation_mode,
        raw_target=round(float(raw_target or 0.0), 4),
        permission_cap=round(float(permission_cap or 0.0), 4),
        risk_cap=round(float(risk_cap or 0.0), 4),
        budget_cap=round(float(budget_cap or 0.0), 4),
        governed_target=governed,
        portfolio_cap=round(float(portfolio_cap or 0.0), 4),
        liquidity_cap=round(float(liquidity_cap or 0.0), 4),
        execution_cap=round(float(execution_cap or 0.0), 4),
        sector_cap=round(float(sector_cap or 0.0), 4),
        theme_cap=round(float(theme_cap or 0.0), 4),
        drawdown_cap=round(float(drawdown_cap or 0.0), 4),
        final_target=round(t, 4), previous_position=round(prev, 4),
        hard_exit=bool(hard_exit), data_quality=data_quality or "B",
        violations=tuple(violations), proof=proof)
