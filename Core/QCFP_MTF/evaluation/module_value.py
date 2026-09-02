# coding: utf-8
"""Module Value Attribution（QCFP-MTF 2.8：31 号模块价值归因）

证明每个模块到底有没有增量价值：
    Module Contribution Matrix
    （Return Δ / MDD Δ / Sharpe Δ / Turnover Δ / Decision Quality Δ）

Module Net Value = Incremental Alpha + Risk Reduction + Decision Quality
    + Capital Efficiency − Complexity Cost − Data Risk − Overfitting Risk
    − Maintenance Cost
"""


def module_value_attribution(modules: dict) -> dict:
    """modules：{name: {return_delta, mdd_delta, sharpe_delta,
    turnover_delta, decision_quality_delta}}（相对 Full−Module）。"""
    matrix = {}
    net_values = {}
    for name, m in modules.items():
        matrix[name] = {
            "return_delta": round(float(m.get("return_delta") or 0.0), 4),
            "mdd_delta": round(float(m.get("mdd_delta") or 0.0), 4),
            "sharpe_delta": round(float(m.get("sharpe_delta") or 0.0), 4),
            "turnover_delta": round(float(m.get("turnover_delta") or 0.0), 4),
            "decision_quality_delta": round(
                float(m.get("decision_quality_delta") or 0.0), 4),
        }
        v = matrix[name]
        net = (v["return_delta"] + v["decision_quality_delta"]
               + max(0.0, v["mdd_delta"]) - max(0.0, v["turnover_delta"])
               - float(m.get("complexity_cost") or 0.0)
               - float(m.get("data_risk") or 0.0)
               - float(m.get("overfitting_risk") or 0.0)
               - float(m.get("maintenance_cost") or 0.0))
        net_values[name] = round(net, 4)
    return {
        "matrix": matrix,
        "net_values": net_values,
        "positive_value_modules": [k for k, v in net_values.items()
                                   if v > 0],
        "candidates_for_retirement": [k for k, v in net_values.items()
                                      if v <= 0],
    }


def module_net_value(incremental_alpha, risk_reduction, decision_quality,
                     capital_efficiency, complexity_cost=0.0,
                     data_risk=0.0, overfitting_risk=0.0,
                     maintenance_cost=0.0) -> float:
    """Module Net Value（系统宪法公式）。"""
    return round(float(incremental_alpha) + float(risk_reduction)
                 + float(decision_quality) + float(capital_efficiency)
                 - float(complexity_cost) - float(data_risk)
                 - float(overfitting_risk) - float(maintenance_cost), 4)
