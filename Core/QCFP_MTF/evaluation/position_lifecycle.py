# coding: utf-8
"""Position Lifecycle Analytics（QCFP-MTF 2.8：15 号持仓生命周期分析）

把每一次完整交易生命周期结构化：
    Entry → Initial Risk → Add → Hold → Trim → Exit → Cooldown

每阶段记录：Price / Target / Position / Risk Budget / MFE / MAE /
P&L / Holding Days / Reason / Decision Hash

回答"哪个阶段最容易犯错"（如 Exit 54% → 优先优化 Exit/Trimming）。
"""


LIFECYCLE_STAGES = ("ENTRY", "INITIAL_RISK", "ADD", "HOLD", "TRIM",
                    "EXIT", "COOLDOWN")


def position_lifecycle(stage_records) -> dict:
    """stage_records：[{stage, price, target, position, risk_budget,
    mfe, mae, pnl, holding_days, reason, decision_hash}]"""
    stages = {}
    for r in stage_records:
        s = str(r.get("stage") or "HOLD").upper()
        stages[s] = {
            "price": r.get("price"),
            "target": r.get("target"),
            "position": r.get("position"),
            "risk_budget": r.get("risk_budget"),
            "mfe": r.get("mfe"),
            "mae": r.get("mae"),
            "pnl": r.get("pnl"),
            "holding_days": r.get("holding_days"),
            "reason": r.get("reason", ""),
            "decision_hash": r.get("decision_hash", ""),
        }
    return {"stages": stages,
            "complete": all(s in stages for s in
                            ("ENTRY", "HOLD", "EXIT"))}


def stage_quality_stats(trades) -> dict:
    """跨交易统计各阶段质量（哪个阶段最容易犯错）。

    trades：[{stages: {stage: {pnl, ...}}, outcome}]
    """
    from collections import defaultdict
    per_stage = defaultdict(list)
    for t in trades:
        stages = t.get("stages") or {}
        for stage, data in stages.items():
            if data.get("pnl") is not None:
                per_stage[stage].append(float(data["pnl"]))
    out = {}
    for stage, pnls in per_stage.items():
        if not pnls:
            continue
        wins = sum(1 for p in pnls if p > 0)
        out[stage] = {
            "n": len(pnls),
            "win_rate": round(wins / len(pnls), 4),
            "mean_pnl": round(sum(pnls) / len(pnls), 4),
        }
    return out
