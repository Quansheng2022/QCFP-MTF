# coding: utf-8
"""Closed-loop Learning & Post-trade Attribution（QCFP-MTF 2.8：60 号）

每笔交易完成后回头问"这次到底谁判断对、谁判断错"：
    Wave / Entry / Exit / Risk / Portfolio / Execution 六模块归因

闭环学习严格受治理：
    Live Outcome → Research → Hypothesis → Backtest → OOS → Ablation →
    Certification → New Release
（生产只能写 Outcome，不能直接在线修改生产参数。）
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PostTradeAttribution:
    trade_id: str
    modules: dict
    outcome: float

    def as_dict(self) -> dict:
        return asdict(self)


def post_trade_attribution(trade: dict) -> PostTradeAttribution:
    """单笔交易六模块归因。

    trade 字段：
        net_return / mfe / mae / mfe_capture / entry_timing /
        exit_timing / wave_hit / risk_saved / portfolio_right /
        execution_cost
    """
    net = float(trade.get("net_return") or 0.0)
    mfe_capture = float(trade.get("mfe_capture") or 0.0)
    modules = {
        "wave": round(
            float(trade.get("wave_hit") or 0.0) * max(net, 0.0), 4),
        "entry": round(
            {"OPTIMAL": 0.4, "EARLY": 0.1, "ACCEPTABLE": 0.2,
             "LATE": -0.2}.get(trade.get("entry_timing"), 0.0)
            * abs(net), 4),
        "exit": round(
            {"normal": 0.0, "early": -0.2, "late": -0.15}.get(
                trade.get("exit_timing"), 0.0) * abs(net), 4),
        "risk": round(float(trade.get("risk_saved") or 0.0), 4),
        "portfolio": round(
            float(trade.get("portfolio_right") or 0.0) * abs(net), 4),
        "execution": round(
            -float(trade.get("execution_cost") or 0.0), 4),
    }
    return PostTradeAttribution(
        trade_id=trade.get("trade_id") or "?",
        modules=modules, outcome=round(net, 4))


def closed_loop_feedback(trade: dict, sandbox, hypothesis=None) -> dict:
    """闭环反馈（生产写 Outcome → 研究建 Hypothesis，禁止直改生产）。

    sandbox：learning.controlled_loop.ResearchSandbox。
    """
    attr = post_trade_attribution(trade)
    sandbox.write_outcome({"trade_id": attr.trade_id,
                           "net_return": attr.outcome,
                           "attribution": attr.modules,
                           "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    if hypothesis:
        from ..learning.controlled_loop import LearningProposal
        proposal = LearningProposal(
            candidate_version="candidate_auto", hypothesis=hypothesis)
        sandbox.create_candidate(proposal)
        promoted = False
        try:
            ok, _ = sandbox.promote(proposal)
            promoted = bool(ok)
        except Exception:
            promoted = False
        return {"attribution": attr.as_dict(),
                "hypothesis_created": True,
                "auto_promoted": promoted,
                "note": "生产只能写 Outcome；候选晋升必须过全部研究门"}
    return {"attribution": attr.as_dict(),
            "hypothesis_created": False,
            "auto_promoted": False}
