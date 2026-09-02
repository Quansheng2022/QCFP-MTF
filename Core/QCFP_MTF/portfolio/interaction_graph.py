# coding: utf-8
"""Portfolio Interaction Graph（QCFP-MTF 2.8：87 号组合交互图）

节点：Stock / Sector / Theme / Factor / Wave / Institutional
边：Correlation / Beta / Common Factor / Industry / Theme /
    Liquidity / Institutional Exposure

发现"表面持有 5 只股票，实际只持有 1 个主题风险"：
    Nominal Exposure vs Effective Exposure
"""


def build_interaction_graph(positions, corr_matrix=None,
                            corr_threshold=0.7) -> dict:
    """构建组合交互图。

    positions：[{stock_code, sector, theme, factor, beta, weight,
                 institutional_state}]
    返回节点/边/簇 + 名义 vs 有效暴露。
    """
    nodes = []
    for p in positions:
        nodes.append({"id": p.get("stock_code"), "type": "stock",
                      "sector": p.get("sector", ""),
                      "theme": p.get("theme", ""),
                      "factor": p.get("factor", ""),
                      "beta": p.get("beta", 1.0),
                      "weight": p.get("weight", 0.0),
                      "institutional": p.get("institutional_state", "")})
    edges = []
    codes = [p.get("stock_code") for p in positions]
    for i, a in enumerate(codes):
        for j, b in enumerate(codes):
            if i >= j:
                continue
            pa, pb = positions[i], positions[j]
            rel = []
            if pa.get("sector") and pa.get("sector") == pb.get("sector"):
                rel.append("INDUSTRY")
            if pa.get("theme") and pa.get("theme") == pb.get("theme"):
                rel.append("THEME")
            if pa.get("factor") and pa.get("factor") == pb.get("factor"):
                rel.append("COMMON_FACTOR")
            if corr_matrix:
                c = corr_matrix.get(a, {}).get(b)
                if c is not None and abs(float(c)) >= corr_threshold:
                    rel.append(f"CORR={float(c):.2f}")
            if rel:
                edges.append({"source": a, "target": b,
                              "relations": rel})
    # 簇：通过边连接的股票同簇
    clusters = []
    assigned = set()
    for edge in edges:
        s, t = edge["source"], edge["target"]
        merged = None
        for cl in clusters:
            if s in cl or t in cl:
                merged = cl
                break
        if merged is None:
            merged = set()
            clusters.append(merged)
        merged.add(s)
        merged.add(t)
    for p in positions:
        if p.get("stock_code") not in assigned \
                and not any(p.get("stock_code") in cl for cl in clusters):
            clusters.append({p.get("stock_code")})
    nominal = sum(float(p.get("weight") or 0.0) for p in positions)
    # 有效暴露：最大簇的总权重
    weight_by_code = {p.get("stock_code"): float(p.get("weight") or 0.0)
                      for p in positions}
    max_cluster = max((sum(weight_by_code.get(c, 0.0) for c in cl)
                       for cl in clusters), default=0.0)
    return {
        "nodes": nodes,
        "edges": edges,
        "clusters": [sorted(cl) for cl in clusters],
        "nominal_exposure": round(nominal, 4),
        "effective_exposure": round(max_cluster, 4),
        "concentration_ratio": round(
            max_cluster / nominal, 4) if nominal else 0.0,
    }
