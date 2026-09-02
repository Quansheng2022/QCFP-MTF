# coding: utf-8
"""Ablation Matrix（QCFP-MTF 2.8：28 号标准化模块消融）

统一模块消融矩阵：
    Full / No Permission / No Wave / No FSM / No Risk / No Execution

统一比较：
    Return Alpha / Risk Alpha / MDD / Turnover / Loss Avoidance /
    MFE Capture / Capital Efficiency

并做增量检查：证明模块不是通过其他模块重复提供同一价值
（如 Wave+FSM 的增量是否高于 Wave Alone）。
"""

from .portfolio_counterfactual import variant_metrics


MATRIX_ROWS = ("Full", "No Permission", "No Wave", "No FSM", "No Risk",
               "No Execution")


def ablation_matrix(variants: dict, actual="Full") -> dict:
    """标准化消融矩阵。

    variants：{label: {"returns": [...], "turnover":..., "mfe_capture":...,
                        "mae":..., "capital_utilization":...}}
    输出每个变体相对 Actual 的 Return Alpha / Risk Alpha / Loss Avoidance /
    Turnover Delta / MFE Capture Delta / Capital Efficiency Delta。
    """
    rows = {}
    for label in variants:
        rows[label] = variant_metrics(
            variants[label]["returns"],
            turnover=variants[label].get("turnover"),
            mfe_capture=variants[label].get("mfe_capture"),
            mae=variants[label].get("mae"),
            capital_utilization=variants[label].get("capital_utilization"))
    base = rows[actual]
    deltas = {}
    for label in rows:
        if label == actual:
            continue
        r = rows[label]
        deltas[label] = {
            "return_alpha": round(
                base["annualized_return"] - r["annualized_return"], 4),
            "risk_alpha": round(base["mdd"] - r["mdd"], 4),
            "loss_avoidance_alpha": round(base["mdd"] - r["mdd"], 4),
            "mdd": round(r["mdd"], 4),
            "turnover_delta": round(r["turnover"] - base["turnover"], 4),
            "mfe_capture_delta": round(
                r["mfe_capture"] - base["mfe_capture"], 4),
            "capital_efficiency_delta": round(
                r["capital_utilization"] - base["capital_utilization"], 4),
        }
    return {"actual": actual, "rows": rows, "deltas": deltas}


def incremental_check(matrix: dict, pair=("No Wave", "No FSM")) -> dict:
    """增量检查：模块组合的边际价值是否高于单一模块。

    pair：去掉的两个模块（如 "No Wave"+"No FSM" 表示 Full−Wave−FSM）。
    若 Full 相对"仅去掉一个"的价值 > 去掉两个的价值，说明存在
    模块间增量重叠（重复提供同一价值）。
    """
    a, b = pair
    single = [matrix["deltas"].get(x) for x in (a, b)]
    both = matrix["deltas"].get(f"{a.replace('No ', '')}+"
                                f"{b.replace('No ', '')}")
    if both is None:
        both = matrix["deltas"].get("No Wave+FSM")
    if not single or both is None:
        return {"assessable": False}
    combined_single = max(s["loss_avoidance_alpha"] for s in single
                          if s is not None)
    overlap = combined_single - both.get("loss_avoidance_alpha", 0.0)
    return {
        "assessable": True,
        "best_single_loss_avoidance": round(combined_single, 4),
        "pair_loss_avoidance": round(both.get("loss_avoidance_alpha", 0.0),
                                     4),
        "incremental_overlap": round(overlap, 4),
        "duplicate_value_suspect": bool(overlap > 0.01),
    }


def matrix_to_md(matrix: dict) -> str:
    rows = matrix["rows"]
    lines = [
        "# Ablation Matrix",
        "",
        "| 变体 | 年化 | MDD | 换手 | MFE捕获 | 资本利用 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for label in rows:
        r = rows[label]
        lines.append(
            f"| {label} | {r['annualized_return']:+.1%} | {r['mdd']:.1%} | "
            f"{r['turnover']:.2f} | {r['mfe_capture']:.2f} | "
            f"{r['capital_utilization']:.0%} |")
    lines += ["", "## 相对 Actual 的边际价值", "",
              "| 变体 | Return Alpha | Risk Alpha | Loss Avoidance | "
              "Turnover Δ |", "| --- | --- | --- | --- | --- |"]
    for label, d in matrix["deltas"].items():
        lines.append(
            f"| {label} | {d['return_alpha']:+.2%} | "
            f"{d['risk_alpha']:+.2%} | {d['loss_avoidance_alpha']:+.2%} | "
            f"{d['turnover_delta']:+.2f} |")
    return "\n".join(lines)
