# coding: utf-8
"""Portfolio Exposure Budget（QCFP-MTF 2.8：21 号组合暴露预算）

单股合规 ≠ 组合合规。组合级预算统一：
    Gross Exposure / Net Exposure / Sector / Theme / Single Stock /
    Liquidity / Risk Budget

约束链：
    Final Target ≤ Stock Cap ≤ Portfolio Cap ≤ Available Risk Budget

输出 portfolio_budget_cap()：组合可新增的最小硬上限，
供 finalize_target / 组合引擎消费（不改变 Permission，只压组合风险）。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class PortfolioBudget:
    gross_exposure: float
    net_exposure: float
    sector_exposure: dict
    theme_exposure: dict
    single_stock_cap: float
    liquidity_cap: float
    risk_budget: float
    available_new_risk: float
    flags: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["flags"] = list(self.flags)
        return d


def portfolio_budget(gross_exposure=0.0, net_exposure=None,
                     sector_exposure=None, theme_exposure=None,
                     single_stock_cap=0.10, liquidity_cap=1.0,
                     risk_budget=0.10, max_gross=0.70,
                     max_sector=0.25, max_theme=0.15) -> PortfolioBudget:
    """组合暴露预算汇总。

    参数：
        gross_exposure    当前总暴露（名义）
        sector_exposure   {行业: 占比}
        theme_exposure    {主题: 占比}
        risk_budget       总风险预算
    输出：
        available_new_risk = 各约束下可新增风险的最小值
        flags             超限标记
    """
    gross = float(gross_exposure or 0.0)
    net = float(net_exposure if net_exposure is not None else gross)
    sector = dict(sector_exposure or {})
    theme = dict(theme_exposure or {})
    flags = []
    caps = [max(0.0, float(max_gross) - gross)]
    over_sector = [s for s, v in sector.items()
                   if v > float(max_sector)]
    over_theme = [t for t, v in theme.items() if v > float(max_theme)]
    if over_sector:
        flags.append(f"SECTOR_OVER:{','.join(over_sector)}")
    if over_theme:
        flags.append(f"THEME_OVER:{','.join(over_theme)}")
    # 行业/主题超限 → 可新增风险收缩（按超限幅度折减）
    sector_scale = min(1.0, float(max_sector) / max(
        max(sector.values()), 1e-9)) if sector else 1.0
    theme_scale = min(1.0, float(max_theme) / max(
        max(theme.values()), 1e-9)) if theme else 1.0
    caps.append(max(0.0, float(risk_budget) * sector_scale * theme_scale))
    caps.append(max(0.0, float(liquidity_cap) - gross))
    available = min(caps)
    return PortfolioBudget(
        gross_exposure=round(gross, 4), net_exposure=round(net, 4),
        sector_exposure={k: round(v, 4) for k, v in sector.items()},
        theme_exposure={k: round(v, 4) for k, v in theme.items()},
        single_stock_cap=round(float(single_stock_cap), 4),
        liquidity_cap=round(float(liquidity_cap), 4),
        risk_budget=round(float(risk_budget), 4),
        available_new_risk=round(available, 4),
        flags=tuple(flags))


def portfolio_budget_cap(portfolio: PortfolioBudget,
                         single_stock_cap_input=None) -> float:
    """组合可新增硬上限 = min(单股上限, 流动性余量, 可用风险预算)。"""
    return round(min(
        float(single_stock_cap_input
              if single_stock_cap_input is not None
              else portfolio.single_stock_cap),
        portfolio.available_new_risk), 4)


def budget_to_md(b: PortfolioBudget) -> str:
    lines = [
        "# Portfolio Exposure Budget",
        "",
        f"**Gross：{b.gross_exposure:.0%}**　Net：{b.net_exposure:.0%}　"
        f"单股上限：{b.single_stock_cap:.0%}",
        "",
        f"**可用新增风险：{b.available_new_risk:.1%}**（Risk Budget "
        f"{b.risk_budget:.0%}，Liquidity Cap {b.liquidity_cap:.0%}）",
        "",
        "## 行业暴露",
        "",
        "| 行业 | 占比 |", "| --- | --- |",
    ]
    for k, v in sorted(b.sector_exposure.items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v:.1%} |")
    lines += ["", "## 主题暴露", "", "| 主题 | 占比 |", "| --- | --- |"]
    for k, v in sorted(b.theme_exposure.items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v:.1%} |")
    if b.flags:
        lines += ["", "## 超限标记", ""]
        lines += [f"- {f}" for f in b.flags]
    return "\n".join(lines)
