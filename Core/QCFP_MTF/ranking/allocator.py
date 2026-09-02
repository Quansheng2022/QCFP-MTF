# coding: utf-8
"""Cross-Symbol Capital Allocation（QCFP-MTF 2.8：45 号跨股票一致性）

同一市场状态多只股票同时 ALLOW+ACTIVE+OPTIMAL 时，不能各自独立满配：
    Candidate Pool → Opportunity Ranking → Risk-adjusted Ranking →
    Capital Allocation

按机会分（risk-adjusted）贪婪分配：
    A(92) → 5% / B(87) → 4% / C(81) → 2% / D(76) → WATCH
受总预算与单股上限约束。
"""


def allocate_capital(ranked, total_budget=0.15, max_single=0.05,
                     min_alloc=0.0, watch_threshold=0.6,
                     permission_caps=None, risk_caps=None,
                     liquidity_caps=None) -> dict:
    """按排序分配资金。

    ranked：[{stock_code, score, tradable, ...}]（降序）
    permission_caps / risk_caps / liquidity_caps：{stock: cap}——
        每只股票的权限/风险/流动性上限，分配不得绕过
        （Position ≤ Permission ≤ Risk ≤ Liquidity）。
    返回 {allocations: {stock: weight}, watch: [codes], remaining}。
    """
    ranked = [r for r in ranked if r.get("tradable", True)]
    if not ranked:
        return {"allocations": {}, "watch": [], "remaining":
                round(float(total_budget), 4)}
    scores = [float(r.get("score") or 0.0) for r in ranked]
    total_score = sum(scores) or 1.0
    allocations = {}
    watch = []
    used = 0.0
    for r, s in zip(ranked, scores):
        weight = float(total_budget) * s / total_score
        weight = min(weight, float(max_single))
        code = r.get("stock_code")
        # 53 号：逐仓钳制 Position ≤ Permission ≤ Risk ≤ Liquidity
        cap = 1.0
        for caps in (permission_caps, risk_caps, liquidity_caps):
            c = (caps or {}).get(code)
            if c is not None:
                cap = min(cap, float(c))
        weight = min(weight, cap)
        if weight < float(min_alloc) or \
                (float(max_single) > 0 and s / (scores[0] or 1e-9)
                 < float(watch_threshold)):
            watch.append(r.get("stock_code"))
            continue
        room = float(total_budget) - used
        if weight > room:
            weight = room
        allocations[code] = round(weight, 4)
        used += weight
    return {"allocations": allocations, "watch": watch,
            "remaining": round(float(total_budget) - used, 4)}


def allocation_to_md(result: dict) -> str:
    lines = [
        "# Cross-Symbol Capital Allocation",
        "",
        "| 股票 | 分配 |", "| --- | --- |",
    ]
    for code, w in result["allocations"].items():
        lines.append(f"| {code} | {w:.1%} |")
    if result["watch"]:
        lines += ["", f"Watch（不分配）：{', '.join(result['watch'])}"]
    lines += ["", f"剩余预算：{result['remaining']:.1%}"]
    return "\n".join(lines)
