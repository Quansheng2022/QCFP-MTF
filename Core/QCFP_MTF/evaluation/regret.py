# coding: utf-8
"""Regret Analysis（QCFP-MTF 2.8：98 号决策遗憾分析）

Decision Regret = Best Feasible Outcome − Actual Outcome
（必须基于当时可获得的信息，不是事后完美交易）。

维度：Entry / Exit / Sizing / No-Trade / Capital Allocation Regret。
"""


def regret(actual, best_feasible, label="decision") -> dict:
    """单维遗憾。"""
    a = float(actual or 0.0)
    b = float(best_feasible or 0.0)
    return {"dimension": label, "actual": round(a, 4),
            "best_feasible": round(b, 4),
            "regret": round(b - a, 4),
            "regret_free": abs(b - a) < 1e-9}


def regret_analysis(actual_exit, best_feasible_exit,
                    actual_entry=None, best_feasible_entry=None,
                    actual_size=None, best_feasible_size=None,
                    no_trade_regret=0.0,
                    allocation_regret=0.0) -> dict:
    """多维遗憾汇总。"""
    dims = [
        regret(actual_exit, best_feasible_exit, "exit"),
        regret(actual_entry, best_feasible_entry, "entry")
        if actual_entry is not None else None,
        regret(actual_size, best_feasible_size, "sizing")
        if actual_size is not None else None,
        regret(-no_trade_regret, 0.0, "no_trade")
        if no_trade_regret else None,
        regret(-allocation_regret, 0.0, "capital_allocation")
        if allocation_regret else None,
    ]
    dims = [d for d in dims if d is not None]
    total = sum(d["regret"] for d in dims)
    return {"dimensions": dims, "total_regret": round(total, 4),
            "quality_score": round(100 * max(0.0, 1.0 - total), 2)}
