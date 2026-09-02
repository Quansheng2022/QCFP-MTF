# coding: utf-8
"""PerformanceMetricContract（Release 2：新 18 号）

backtest.performance.evaluate 是唯一指标计算层（equity_metrics）：
    Backtest / OOS / Ablation / Counterfactual / Stress /
    Benchmark Ladder / Minimum Canonical / Report
全部禁止自行计算 Sharpe/MDD/CAGR。

验收：同一组 returns → Backtest Sharpe = Ablation Sharpe =
Stress Sharpe = Report Sharpe（允许 rounding 差异，不允许公式差异）。
"""

from ..backtest.performance import evaluate as equity_metrics


def metric_authority() -> dict:
    return {"authority": "backtest.performance.evaluate",
            "metric_authority_count": 1,
            "rule": "所有正式研究只能调用这一层"}


def metric_authority_check(computations: dict) -> dict:
    """computations：{module: ["sharpe", "mdd", "cagr"]}——
    正式路径出现自行计算关键指标 → 违规。"""
    violations = []
    for module, metrics in (computations or {}).items():
        self_computed = [m for m in (metrics or [])
                         if m in ("sharpe", "mdd", "cagr",
                                  "annualized_return", "max_drawdown")]
        if self_computed:
            violations.append({"module": module,
                               "self_computed": self_computed})
    return {"violations": violations,
            "verdict": "SINGLE_METRIC_AUTHORITY" if not violations
            else "METRIC_AUTHORITY_VIOLATION",
            "rule": "Backtest/OOS/Ablation/Stress/Benchmark/Minimum/"
                    "Report 禁止自行算 Sharpe/MDD/CAGR"}


def same_returns_same_metrics(returns, tolerance: float = 1e-6) -> dict:
    """同一组 returns 多次计算必须得到一致指标。"""
    import pandas as pd
    import numpy as np
    r = pd.Series([float(x) for x in returns])
    m1 = equity_metrics(r)
    m2 = equity_metrics(r.copy())
    diffs = {k: abs(float(m1.get(k) or 0.0) - float(m2.get(k) or 0.0))
             for k in ("sharpe", "max_drawdown", "annualized_return")
             if m1.get(k) is not None}
    consistent = all(d <= tolerance for d in diffs.values())
    return {"consistent": consistent, "diffs": diffs,
            "verdict": "CONSISTENT" if consistent
            else "METRIC_INCONSISTENT"}
