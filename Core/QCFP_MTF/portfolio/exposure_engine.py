# coding: utf-8
"""Correlation & Exposure Engine（QCFP-MTF 2.8：33 号组合暴露引擎）

防止"看起来分散，实际上高度集中"：
    Position → Factor Exposure → Industry Exposure → Correlation →
    Portfolio Risk

输出：
    Industry Exposure / Beta Exposure / Factor Exposure / Theme Exposure /
    Correlation Cluster / Effective Number of Bets
"""

import numpy as np


def effective_number_of_bets(weights) -> float:
    """有效下注数 ENB = 1 / Σw²（等权 N 只 = N，单只 = 1）。"""
    w = np.asarray([float(x) for x in weights if float(x) > 0], float)
    if len(w) == 0:
        return 0.0
    w = w / w.sum()
    return round(1.0 / float(np.sum(w ** 2)), 2)


def group_exposure(positions, key) -> dict:
    """按行业/主题/因子分组暴露（仓位占比归一化）。"""
    out = {}
    total = sum(float(p.get("weight") or 0.0) for p in positions)
    for p in positions:
        g = p.get(key) or "unknown"
        out[g] = out.get(g, 0.0) + float(p.get("weight") or 0.0)
    if total > 0:
        out = {k: round(v / total, 4) for k, v in out.items()}
    return out


def beta_exposure(positions) -> dict:
    """加权 Beta + 离散度（高离散 = 单股 Beta 差异大）。"""
    betas = [float(p.get("beta") or 1.0) for p in positions]
    weights = [float(p.get("weight") or 0.0) for p in positions]
    w = np.array(weights)
    if w.sum() <= 0:
        return {"weighted_beta": None, "beta_dispersion": None}
    wb = float(np.dot(w / w.sum(), betas))
    return {"weighted_beta": round(wb, 3),
            "beta_dispersion": round(float(np.std(betas)), 3)}


def correlation_clusters(corr_matrix, threshold=0.7) -> list:
    """贪心相关性聚类：相关性 ≥ threshold 的股票归入同一簇。"""
    codes = list(corr_matrix.keys())
    clusters = []
    assigned = set()
    for i, a in enumerate(codes):
        if a in assigned:
            continue
        cluster = [a]
        for b in codes[i + 1:]:
            if b in assigned:
                continue
            if float(corr_matrix[a].get(b, 0.0)) >= threshold:
                cluster.append(b)
                assigned.add(b)
        assigned.add(a)
        clusters.append(sorted(cluster))
    return clusters


def exposure_report(positions, corr_matrix=None,
                    factor_keys=("factor_macro", "factor_theme"),
                    corr_threshold=0.7) -> dict:
    """完整组合暴露报告。"""
    weights = [float(p.get("weight") or 0.0) for p in positions]
    total_w = sum(weights)
    industry = group_exposure(positions, "sector")
    theme = group_exposure(positions, "theme")
    beta = beta_exposure(positions)
    enb = effective_number_of_bets(weights)
    factor = {}
    for fk in factor_keys:
        factor[fk] = group_exposure(positions, fk)
    clusters = correlation_clusters(corr_matrix, corr_threshold) \
        if corr_matrix else []
    # 集中度风险：单行业 >50% 或 ENB < 2 视为隐性集中
    max_industry = max(industry.values()) if industry else 0.0
    flags = []
    if max_industry >= 0.5:
        flags.append(f"INDUSTRY_CONCENTRATED({max_industry:.0%})")
    if enb < 2.0 and total_w > 0:
        flags.append(f"LOW_EFFECTIVE_BETS({enb})")
    if clusters and len(clusters) < len(weights):
        flags.append(f"CORRELATION_CLUSTER({len(clusters)}/{len(weights)})")
    return {
        "total_weight": round(total_w, 4),
        "industry_exposure": industry,
        "theme_exposure": theme,
        "beta_exposure": beta,
        "factor_exposure": factor,
        "effective_number_of_bets": enb,
        "correlation_clusters": clusters,
        "flags": flags,
    }


def exposure_to_md(report: dict) -> str:
    lines = [
        "# Correlation & Exposure Report",
        "",
        f"**有效下注数（ENB）：{report['effective_number_of_bets']}**　"
        f"总权重：{report['total_weight']:.0%}",
        "",
        "## 行业暴露",
        "",
        "| 行业 | 占比 |", "| --- | --- |",
    ]
    for k, v in sorted(report["industry_exposure"].items(),
                       key=lambda x: -x[1]):
        lines.append(f"| {k} | {v:.1%} |")
    lines += ["", "## Beta 暴露", "",
              f"- 加权 Beta：{report['beta_exposure'].get('weighted_beta')}",
              f"- Beta 离散度：{report['beta_exposure'].get('beta_dispersion')}",
              ""]
    if report["correlation_clusters"]:
        lines += ["## 相关性簇", ""]
        for i, c in enumerate(report["correlation_clusters"], 1):
            lines.append(f"- 簇{i}：{', '.join(c)}")
        lines += [""]
    if report["flags"]:
        lines += ["## 集中度标记", ""]
        lines += [f"- {f}" for f in report["flags"]]
        lines += [""]
    return "\n".join(lines)


def effective_risk_exposure(positions, corr_matrix=None) -> dict:
    """有效风险暴露（22 号）：
        名义暴露（Σw）→ 相关性调整后的等效风险暴露。

    等效暴露 = 名义 × sqrt(w̄'Σ w̄)（w̄ 为归一化权重）：
        全相关（Σ=1）→ 等效=名义（无分散）
        零相关（Σ=I）→ 等效=名义/√n（充分分散）
    并输出主题等效暴露（theme_exposure）。
    """
    weights = [float(p.get("weight") or 0.0) for p in positions]
    nominal = sum(weights)
    if nominal <= 0:
        return {"nominal_exposure": 0.0, "effective_risk_exposure": 0.0,
                "theme_equivalent_exposure": {}, "reduction_pct": 0.0}
    codes = [p.get("stock_code") for p in positions]
    if corr_matrix and len(codes) > 1:
        import numpy as np
        C = np.eye(len(codes))
        for i, a in enumerate(codes):
            for j, b in enumerate(codes):
                if i != j:
                    v = corr_matrix.get(a, {}).get(b)
                    if v is not None:
                        C[i, j] = float(v)
        w = np.array(weights) / nominal
        factor = float(np.sqrt(max(0.0, w @ C @ w)))
        effective = nominal * factor
    else:
        effective = nominal
    theme = group_exposure(positions, "theme")
    return {
        "nominal_exposure": round(nominal, 4),
        "effective_risk_exposure": round(effective, 4),
        "theme_equivalent_exposure": theme,
        "reduction_pct": round(1.0 - effective / nominal, 4),
    }
