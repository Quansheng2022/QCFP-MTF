# coding: utf-8
"""Counterfactual Portfolio Engine（QCFP-MTF 2.8：47 号组合反事实分析）

从单次决策反事实升级为组合级：
    Actual Portfolio vs No Permission vs No Wave vs No Risk vs
    No Portfolio Governance

比较：Return / MDD / Turnover / MFE Capture / MAE / Capital Utilization /
      Tail Loss
亮点：Permission 可能不直接增加收益，但 MDD -35% → -18%，
      这就是 Risk Alpha / Loss Avoidance Alpha。
"""

import numpy as np


def _mdd(returns):
    r = np.asarray([float(x) for x in returns], float)
    if len(r) == 0:
        return 0.0
    eq = np.cumprod(1 + r)
    return float((eq / np.maximum.accumulate(eq) - 1).min())


def _tail(returns, q=0.05):
    r = np.asarray([float(x) for x in returns], float)
    if len(r) == 0:
        return 0.0
    return float(np.quantile(r, q))


def variant_metrics(returns, turnover=None, mfe_capture=None, mae=None,
                    capital_utilization=None) -> dict:
    """单变体指标（P0-C 新 9 号）：统一走标准指标层——
    复利 total_return + CAGR（与 backtest.performance.evaluate 同口径），
    不再用 sum(return) / mean(return)×52。"""
    r = np.asarray([float(x) for x in returns], float)
    if len(r):
        total = float((1 + r).prod() - 1)
        ann = float((1 + total) ** (52.0 / len(r)) - 1)
    else:
        total, ann = 0.0, 0.0
    return {
        "total_return": round(total, 4),
        "annualized_return": round(ann, 4),
        "mdd": round(_mdd(r), 4),
        "turnover": round(float(turnover or 0.0), 4),
        "mfe_capture": round(float(mfe_capture or 0.0), 4),
        "mae": round(float(mae or 0.0), 4),
        "capital_utilization": round(float(capital_utilization or 0.0), 4),
        "tail_loss": round(_tail(r), 4),
    }


def portfolio_counterfactual(variants: dict) -> dict:
    """组合反事实对比。

    variants：{label: {"returns": [...], "turnover":..., "mfe_capture":...,
                        "mae":..., "capital_utilization":...}}
    第一个键视为 Actual。
    """
    labels = list(variants)
    actual = labels[0]
    rows = {}
    for label in labels:
        v = variants[label]
        rows[label] = variant_metrics(
            v["returns"], turnover=v.get("turnover"),
            mfe_capture=v.get("mfe_capture"), mae=v.get("mae"),
            capital_utilization=v.get("capital_utilization"))
    # 治理边际价值：各变体相对 Actual 的 MDD 变化（正 = Actual 更优）
    deltas = {}
    for label in labels[1:]:
        deltas[label] = {
            "return_delta": round(
                rows[actual]["annualized_return"]
                - rows[label]["annualized_return"], 4),
            "mdd_delta": round(
                rows[actual]["mdd"] - rows[label]["mdd"], 4),
            "loss_avoidance_alpha": round(
                rows[actual]["mdd"] - rows[label]["mdd"], 4),
            "turnover_delta": round(
                rows[label]["turnover"] - rows[actual]["turnover"], 4),
        }
    return {
        "actual": actual,
        "rows": rows,
        "deltas": deltas,
        "risk_alpha": {
            label: d["loss_avoidance_alpha"]
            for label, d in deltas.items()
            if d["loss_avoidance_alpha"] > 0},
    }


def counterfactual_to_md(report: dict) -> str:
    rows = report["rows"]
    labels = list(rows)
    lines = [
        "# Counterfactual Portfolio Analysis",
        "",
        "| 变体 | 年化 | MDD | 换手 | MFE捕获 | MAE | 资本利用 | Tail |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for label in labels:
        r = rows[label]
        lines.append(
            f"| {label} | {r['annualized_return']:+.1%} | "
            f"{r['mdd']:.1%} | {r['turnover']:.2f} | "
            f"{r['mfe_capture']:.2f} | {r['mae']:.1%} | "
            f"{r['capital_utilization']:.0%} | {r['tail_loss']:.1%} |")
    lines += ["", "## 治理边际价值（相对 Actual）", "",
              "| 变体 | Δ收益 | ΔMDD | Loss Avoidance Alpha |", 
              "| --- | --- | --- | --- |"]
    for label, d in report["deltas"].items():
        lines.append(
            f"| {label} | {d['return_delta']:+.2%} | "
            f"{d['mdd_delta']:+.2%} | {d['loss_avoidance_alpha']:+.2%} |")
    if report["risk_alpha"]:
        lines += ["", "## Risk Alpha（Loss Avoidance）", ""]
        for label, v in report["risk_alpha"].items():
            lines.append(f"- {label}：MDD 改善 {v:+.2%}")
    return "\n".join(lines)
