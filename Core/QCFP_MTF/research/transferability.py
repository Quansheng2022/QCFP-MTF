# coding: utf-8
"""Transferability / Market-Portability Validation（QCFP-MTF 2.8：49 号）

判断策略是否具有跨市场可迁移性：
    训练市场 → 测试不同板块/市值/流动性/市场

把 Alpha 分类为：
    Market-General / Market-Specific / Sector-Specific / Stock-Specific
"""


def transferability_validation(performance_by_market: dict,
                               mechanism_structural=True) -> dict:
    """performance_by_market：{market: {sharpe, n_trades}}"""
    markets = list(performance_by_market)
    if not markets:
        return {"classification": "UNKNOWN", "transferable": False}
    sharpe_by_market = {m: float(p.get("sharpe") or 0.0)
                        for m, p in performance_by_market.items()}
    positive = [s for s in sharpe_by_market.values() if s > 0.5]
    if len(markets) >= 3 and len(positive) / len(markets) >= 0.67 \
            and mechanism_structural:
        classification = "Market-General"
        transferable = True
    elif len(markets) >= 2 and len(positive) / len(markets) >= 0.5:
        classification = "Sector-Specific"
        transferable = True
    elif len(markets) == 1 and positive:
        classification = "Market-Specific"
        transferable = False
    else:
        classification = "Stock-Specific"
        transferable = False
    return {"markets_tested": markets,
            "sharpe_by_market": {k: round(v, 4)
                                 for k, v in sharpe_by_market.items()},
            "classification": classification,
            "transferable": transferable,
            "note": "结构性机制（如 Institutional Permission）更可迁移；"
                    "市场特有资金指标不可迁移"}
