# coding: utf-8
"""Opportunity Competition Engine（QCFP-MTF 2.8：46 号机会竞争机制）

机会 A / B / C 可能都在争夺同一份风险预算（同一主题/行业/相关性簇）：
    Opportunity → Exposure Cluster → Risk Competition → Shared Budget

规则：同一簇内 A+B+C ≤ Theme Risk Budget（不能各自拿 8%）。
输出每个簇的预算上限与每只股票的允许权重。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class CompetitionResult:
    clusters: dict                 # cluster -> {stocks, weights, budget, allocated}
    over_budget: tuple             # 超预算的簇
    allowed_weights: dict          # stock -> 允许权重
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["over_budget"] = list(self.over_budget)
        d["reasons"] = list(self.reasons)
        return d


def _cluster_key(opp, cluster_by):
    """机会 → 簇键（显式 cluster 或 theme/sector）。"""
    return opp.get("cluster") or opp.get(cluster_by) or "other"


def opportunity_competition(opportunities, cluster_by="theme",
                            theme_budget=0.15,
                            max_single_weight=0.08,
                            per_cluster_override=None) -> CompetitionResult:
    """机会竞争分配。

    opportunities：[{stock_code, weight, theme/sector/cluster}]
    theme_budget：单簇（主题）风险预算上限
    max_single_weight：单股上限
    """
    clusters = {}
    for opp in opportunities:
        key = _cluster_key(opp, cluster_by)
        cl = clusters.setdefault(key, {"stocks": [], "weights": []})
        cl["stocks"].append(opp["stock_code"])
        cl["weights"].append(float(opp.get("weight") or 0.0))
    over = []
    allowed = {}
    reasons = []
    for key, cl in clusters.items():
        budget = float(per_cluster_override or {}).get(key, theme_budget) \
            if per_cluster_override else float(theme_budget)
        total = sum(cl["weights"])
        cl["budget"] = round(budget, 4)
        cl["total_weight"] = round(total, 4)
        if total > budget:
            over.append(key)
            reasons.append(f"CLUSTER_OVER_BUDGET({key}):{total:.2f}>{budget:.2f}")
        # 允许权重 = 每只 min(原权重, 单股上限)，簇内按比例压缩到预算
        scale = min(1.0, budget / total) if total > 0 else 1.0
        for stock, w in zip(cl["stocks"], cl["weights"]):
            allowed[stock] = round(
                min(w * scale, float(max_single_weight)), 4)
    return CompetitionResult(
        clusters=clusters, over_budget=tuple(over),
        allowed_weights=allowed, reasons=tuple(reasons))
