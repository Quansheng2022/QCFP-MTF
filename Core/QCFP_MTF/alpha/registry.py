# coding: utf-8
"""Alpha Source Registry（QCFP-MTF 2.8：81 号 Alpha 来源注册表）

明确每个 Alpha 来源及其依赖关系，防止"模块看似独立、实际同源"：
    alpha_id / source / hypothesis / feature_dependencies /
    market_regime / expected_holding_period / risk_dependencies /
    validation_status / production_status

回答："QCFP_MTF 的 Alpha 到底来自哪里？"
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class AlphaSource:
    alpha_id: str
    source: str
    hypothesis: str = ""
    feature_dependencies: tuple = field(default_factory=tuple)
    market_regime: str = ""
    expected_holding_period: str = ""
    risk_dependencies: tuple = field(default_factory=tuple)
    validation_status: str = "research"     # research/validated/production
    production_status: str = "inactive"     # inactive/active/retired

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("feature_dependencies", "risk_dependencies"):
            d[k] = list(d[k])
        return d


class AlphaRegistry:
    def __init__(self):
        self.sources = {}

    def register(self, source: AlphaSource) -> None:
        self.sources[source.alpha_id] = source

    def get(self, alpha_id) -> AlphaSource:
        return self.sources.get(alpha_id)

    def active_alpha_count(self) -> int:
        return sum(1 for s in self.sources.values()
                   if s.production_status == "active")

    def dependencies_of(self, alpha_id) -> set:
        s = self.get(alpha_id)
        if not s:
            return set()
        return set(s.feature_dependencies) | set(s.risk_dependencies)

    def shared_dependency_report(self) -> dict:
        """共享依赖检测：多个 Alpha 依赖同一变量 → 潜在重复下注。"""
        dep_usage = {}
        for s in self.sources.values():
            for d in set(s.feature_dependencies) | set(s.risk_dependencies):
                dep_usage.setdefault(d, []).append(s.alpha_id)
        shared = {d: ids for d, ids in dep_usage.items() if len(ids) > 1}
        return {
            "n_alpha_sources": len(self.sources),
            "n_active": self.active_alpha_count(),
            "shared_dependencies": shared,
            "duplicate_risk_suspect": bool(shared),
        }
