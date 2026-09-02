# coding: utf-8
"""Permission Opportunity Cost（QCFP-MTF 2.8：28 号权限价值审计）

Institutional Permission 拥有最高权力，必须被严格审计：
    Benefit：Avoided Loss / Avoided Drawdown / Prevented False Entry /
             Tail Risk Reduction
    Cost：Missed Return / Missed Wave / Entry Delay / Capture Loss

Net Permission Value = Benefit − Cost
（证明牺牲的 Opportunity Cost 是否换来了足够的 Risk Reduction。）
"""


def permission_value(benefit: dict, cost: dict) -> dict:
    """permission_value(benefit, cost)。

    benefit：{avoided_loss, avoided_drawdown, prevented_false_entry,
              tail_risk_reduction}
    cost：{missed_return, missed_wave, entry_delay, capture_loss}
    """
    b = sum(float(benefit.get(k) or 0.0)
            for k in ("avoided_loss", "avoided_drawdown",
                      "prevented_false_entry", "tail_risk_reduction"))
    c = sum(float(cost.get(k) or 0.0)
            for k in ("missed_return", "missed_wave", "entry_delay",
                      "capture_loss"))
    net = b - c
    return {
        "permission_benefit": {
            k: round(float(benefit.get(k) or 0.0), 4)
            for k in ("avoided_loss", "avoided_drawdown",
                      "prevented_false_entry", "tail_risk_reduction")},
        "permission_cost": {
            k: round(float(cost.get(k) or 0.0), 4)
            for k in ("missed_return", "missed_wave", "entry_delay",
                      "capture_loss")},
        "total_benefit": round(b, 4),
        "total_cost": round(c, 4),
        "net_permission_value": round(net, 4),
        "verdict": "JUSTIFIED" if net > 0 else
        "NEUTRAL" if abs(net) < 1e-9 else "REVIEW",
    }
