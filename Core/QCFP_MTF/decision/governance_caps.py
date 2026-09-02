# coding: utf-8
"""GovernanceCaps（QCFP-MTF 2.8：新 2 号 Hard Caps 统一容器）

把 Portfolio / Liquidity / Execution / Sector / Theme / Drawdown /
Data Quality 等 hard caps 收敛成一个不可变容器，由唯一入口
finalize_target 消费：

    RawTarget
      ↓ Permission Cap
      ↓ Risk Cap
      ↓ Portfolio Cap
      ↓ Sector / Theme Cap
      ↓ Liquidity Cap
      ↓ Execution Cap
      ↓ Drawdown Cap
      ↓ Data Quality Cap
      ↓ FinalTarget

验收标准：每笔 DecisionSnapshot 拥有 ConstraintTrace + BindingConstraint，
且 FinalTarget <= 所有 hard caps。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceCaps:
    permission_cap: float = 1.0
    risk_cap: float = 1.0
    portfolio_cap: float = 1.0
    sector_cap: float = 1.0
    theme_cap: float = 1.0
    liquidity_cap: float = 1.0
    execution_cap: float = 1.0
    drawdown_cap: float = 1.0
    data_quality_cap: float = 1.0

    def to_kwargs(self) -> dict:
        """finalize_target 兼容 kwargs。"""
        return {
            "portfolio_cap": self.portfolio_cap,
            "sector_cap": self.sector_cap,
            "theme_cap": self.theme_cap,
            "liquidity_cap": self.liquidity_cap,
            "execution_cap": self.execution_cap,
            "drawdown_cap": self.drawdown_cap,
        }

    def all_caps(self) -> dict:
        return {
            "permission_cap": self.permission_cap,
            "risk_cap": self.risk_cap,
            "portfolio_cap": self.portfolio_cap,
            "sector_cap": self.sector_cap,
            "theme_cap": self.theme_cap,
            "liquidity_cap": self.liquidity_cap,
            "execution_cap": self.execution_cap,
            "drawdown_cap": self.drawdown_cap,
            "data_quality_cap": self.data_quality_cap,
        }


def caps_from_row(row: dict, defaults: GovernanceCaps = None) \
        -> GovernanceCaps:
    """从 Evidence/上下文读取各 hard cap（缺省 1.0）。"""
    d = defaults or GovernanceCaps()
    return GovernanceCaps(
        permission_cap=float(row.get("permission_cap")
                             if row.get("permission_cap") is not None
                             else d.permission_cap),
        risk_cap=float(row.get("risk_cap")
                       if row.get("risk_cap") is not None
                       else d.risk_cap),
        portfolio_cap=float(row.get("portfolio_cap")
                            if row.get("portfolio_cap") is not None
                            else d.portfolio_cap),
        sector_cap=float(row.get("sector_cap")
                         if row.get("sector_cap") is not None
                         else d.sector_cap),
        theme_cap=float(row.get("theme_cap")
                        if row.get("theme_cap") is not None
                        else d.theme_cap),
        liquidity_cap=float(row.get("liquidity_cap")
                            if row.get("liquidity_cap") is not None
                            else d.liquidity_cap),
        execution_cap=float(row.get("execution_cap")
                            if row.get("execution_cap") is not None
                            else d.execution_cap),
        drawdown_cap=float(row.get("drawdown_cap")
                           if row.get("drawdown_cap") is not None
                           else d.drawdown_cap),
        data_quality_cap=float(row.get("data_quality_cap")
                               if row.get("data_quality_cap") is not None
                               else d.data_quality_cap),
    )


# 新 5 号：Cap 分类——REQUIRED 缺失 → UNKNOWN → 不新增风险
REQUIRED_CAPS = ("portfolio_cap", "liquidity_cap", "execution_cap")
CONDITIONAL_REQUIRED_CAPS = ("sector_cap", "theme_cap", "drawdown_cap")
DERIVED_CAPS = ("permission_cap", "risk_cap", "data_quality_cap")


def caps_governance_check(row: dict,
                          mode="research_exploration") -> dict:
    """新 5 号：Production/Research Validation 下 REQUIRED cap 缺失
    → UNKNOWN → 不新增风险；Exploration 下 → ASSUMED 1.0 + NON_CERTIFIABLE。"""
    missing_required = [c for c in REQUIRED_CAPS
                        if row.get(c) is None]
    # MTR Closure（Sprint C）：NaN/非法数值 cap 同样视为 UNKNOWN——
    # 浮点 NaN 不是 None，必须显式识别，否则静默放行。
    for c in REQUIRED_CAPS + DERIVED_CAPS + CONDITIONAL_REQUIRED_CAPS:
        v = row.get(c)
        if v is not None:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                fv = float("nan")
            if fv != fv:   # NaN
                missing_required.append(c)
    missing_required = sorted(set(missing_required))
    unknown = bool(missing_required)
    if mode in ("production", "research_validation"):
        return {"mode": mode,
                "missing_required": missing_required,
                "unknown": unknown,
                "degrade": "NO_NEW_RISK" if unknown else "NORMAL",
                "certifiable": not unknown,
                "rule": "Production 缺 REQUIRED cap → UNKNOWN → 不新增风险"}
    return {"mode": mode,
            "missing_required": missing_required,
            "unknown": False,
            "degrade": "ASSUMED" if missing_required else "NORMAL",
            "certifiable": False if missing_required else True,
            "rule": "Exploration 缺 cap → ASSUMED 1.0 → NON_CERTIFIABLE"}


def assert_target_within_caps(target: float, caps: GovernanceCaps) -> dict:
    """验收标准：FinalTarget <= 所有 hard caps。"""
    t = float(target or 0.0)
    violations = [name for name, cap in caps.all_caps().items()
                  if (float(cap) != float(cap))        # NaN → UNKNOWN
                  or (float(cap) < 1.0 - 1e-9
                      and t > float(cap) + 1e-9)]
    unknown_caps = [name for name, cap in caps.all_caps().items()
                    if float(cap) != float(cap)]
    return {"target": t,
            "within_caps": not violations,
            "violations": violations,
            "unknown_caps": unknown_caps,
            "caps": caps.all_caps()}
