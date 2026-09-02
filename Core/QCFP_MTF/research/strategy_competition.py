# coding: utf-8
"""Strategy Competition / Champion-Challenger（QCFP-MTF 2.8：48 号策略竞争）

让多个策略持续竞争（不是固定一个 QCFP_MTF）：
    Champion / Challenger / Experimental / Retired

持续比较：Return / Sharpe / MDD / Turnover / Capacity / Robustness /
Decision Quality
"""


def strategy_competition(strategies: dict) -> dict:
    """strategies：{name: {sharpe, return, mdd, turnover, capacity,
    robustness, decision_quality}}"""
    rows = []
    for name, m in strategies.items():
        score = (float(m.get("sharpe") or 0.0) * 0.30
                 + float(m.get("return") or 0.0) * 0.20
                 - abs(float(m.get("mdd") or 0.0)) * 0.15
                 - float(m.get("turnover") or 0.0) * 0.05
                 + float(m.get("capacity") or 0.0) * 0.10
                 + float(m.get("robustness") or 0.0) * 0.10
                 + float(m.get("decision_quality") or 0.0) * 0.10)
        rows.append({"name": name, "score": round(score, 4),
                     **{k: round(float(v), 4)
                        for k, v in m.items()}})
    rows.sort(key=lambda r: -r["score"])
    if not rows:
        return {"rows": [], "champion": None}
    champion = rows[0]["name"]
    return {
        "rows": rows,
        "champion": champion,
        "challengers": [r["name"] for r in rows[1:]],
        "promotion_candidate": rows[0]["name"],
        "retired_candidates": [r["name"] for r in rows
                               if r.get("robustness", 1.0) < 0.3],
    }
