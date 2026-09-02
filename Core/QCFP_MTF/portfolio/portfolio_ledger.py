# coding: utf-8
"""Portfolio Decision Ledger（QCFP-MTF 2.8：44 号组合级事实源）

单股票 Ledger 回答"为什么这只股票 3%"，组合 Ledger 回答
"为什么组合最终持有这些股票、为什么 A 没买、为什么 B 被卖"：
    Instrument Ledger → Portfolio Ledger（第二层）

记录：portfolio_decision_id / timestamp / gross / net / sector / theme /
    risk_budget / available_cash / liquidity_budget / turnover_budget /
    positions_before / positions_after / rejected_candidates /
    replacement_decisions
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PortfolioDecision:
    portfolio_decision_id: str
    timestamp: str
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    sector_exposure: dict = field(default_factory=dict)
    theme_exposure: dict = field(default_factory=dict)
    risk_budget: float = 0.0
    available_cash: float = 0.0
    liquidity_budget: float = 0.0
    turnover_budget: float = 0.0
    positions_before: dict = field(default_factory=dict)
    positions_after: dict = field(default_factory=dict)
    rejected_candidates: tuple = field(default_factory=tuple)
    replacement_decisions: tuple = field(default_factory=tuple)
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("rejected_candidates", "replacement_decisions", "reasons"):
            d[k] = list(d[k])
        return d


class PortfolioLedger:
    """组合级 Append-only 台账。"""

    def __init__(self):
        self.records = []

    def record(self, decision: PortfolioDecision) -> None:
        self.records.append(decision)

    def latest(self) -> PortfolioDecision:
        if not self.records:
            raise ValueError("PortfolioLedger 为空")
        return self.records[-1]

    def why_not_bought(self, stock_code) -> list:
        """为什么 A 没有买：查看最近记录中被拒绝的候选。"""
        out = []
        for r in self.records:
            for cand in r.rejected_candidates:
                if isinstance(cand, dict) and cand.get("stock_code") \
                        == stock_code:
                    out.append({"portfolio_decision_id":
                                r.portfolio_decision_id,
                                "reason": cand.get("reason", "")})
        return out

    def why_sold(self, stock_code) -> list:
        """为什么 B 被卖掉：查看持仓减少或替换记录。"""
        out = []
        for r in self.records:
            before = r.positions_before.get(stock_code, 0.0)
            after = r.positions_after.get(stock_code, 0.0)
            if after < before:
                out.append({"portfolio_decision_id": r.portfolio_decision_id,
                            "before": before, "after": after,
                            "reason": f"position reduced {before:.1%}→"
                                      f"{after:.1%}"})
            for rep in r.replacement_decisions:
                if isinstance(rep, dict) and rep.get("sold") == stock_code:
                    out.append({"portfolio_decision_id":
                                r.portfolio_decision_id,
                                "reason": rep.get("reason", "")})
        return out


def record_portfolio_decision(ledger: PortfolioLedger, decision_id,
                              positions_before, positions_after,
                              rejected=None, replacements=None,
                              **kw) -> PortfolioDecision:
    """便捷记录函数（自动填时间戳与组合汇总）。"""
    d = PortfolioDecision(
        portfolio_decision_id=decision_id,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        gross_exposure=sum(positions_after.values()),
        net_exposure=sum(positions_after.values()),
        positions_before=dict(positions_before),
        positions_after=dict(positions_after),
        rejected_candidates=tuple(rejected or ()),
        replacement_decisions=tuple(replacements or ()),
        **kw)
    ledger.record(d)
    return d
