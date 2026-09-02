# coding: utf-8
"""Benchmark / Challenger System（QCFP-MTF 2.8：29 号反自嗨基准）

防止"自己证明自己"：
    QCFP_MTF vs Baseline / Simple MA / Momentum / Buy&Hold /
    Wave-only / Permission-only / Challenger Model

比较 CAGR / MDD / Sharpe，证明复杂性换来了增量价值。
"""


def challenger_system(models: dict) -> dict:
    """models：{name: {cagr, mdd, sharpe}}（QCFP_MTF 必须在内）。

    返回排名 + QCFP 相对最优 Challenger 的增量。
    """
    rows = []
    for name, m in models.items():
        rows.append({"name": name,
                     "cagr": round(float(m.get("cagr") or 0.0), 4),
                     "mdd": round(float(m.get("mdd") or 0.0), 4),
                     "sharpe": round(float(m.get("sharpe") or 0.0), 4)})
    rows.sort(key=lambda r: -r["sharpe"])
    if "QCFP_MTF" not in models:
        return {"rows": rows, "error": "缺少 QCFP_MTF 模型"}
    qcfp = rows[[i for i, r in enumerate(rows)
                 if r["name"] == "QCFP_MTF"][0]]
    challengers = [r for r in rows if r["name"] != "QCFP_MTF"]
    best_challenger = challengers[0] if challengers else None
    return {
        "rows": rows,
        "qcfp_rank": [i for i, r in enumerate(rows)
                      if r["name"] == "QCFP_MTF"][0] + 1,
        "best_challenger": best_challenger,
        "sharpe_edge": round(
            qcfp["sharpe"] - (best_challenger["sharpe"]
                              if best_challenger else 0.0), 4),
        "mdd_advantage": round(
            qcfp["mdd"] - (best_challenger["mdd"]
                           if best_challenger else 0.0), 4),
        "verdict": "BEATS_CHALLENGERS" if qcfp["sharpe"] >
        (best_challenger["sharpe"] if best_challenger else 0.0)
        else "CHALLENGED",
    }
