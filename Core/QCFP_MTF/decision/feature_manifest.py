# coding: utf-8
"""Feature Production Manifest（QCFP-MTF 2.8：15 号生产特征清单）

代码存在 ≠ 系统正在使用；已测试 ≠ 已生产认证。

Feature 生命周期：
    DEFINED → WIRED → VALIDATED → CERTIFIED → ACTIVE →
    DEPRECATED → RETIRED

Production Manifest 只允许 ACTIVE；每次 DecisionSnapshot 记录本次
真正 ACTIVE 的 feature set。
"""

from dataclasses import asdict, dataclass, field


FEATURE_LIFECYCLE = ("DEFINED", "WIRED", "VALIDATED", "CERTIFIED",
                     "ACTIVE", "DEPRECATED", "RETIRED")


@dataclass(frozen=True)
class FeatureStatus:
    feature_id: str
    status: str = "DEFINED"

    def as_dict(self) -> dict:
        return asdict(self)


class FeatureManifest:
    def __init__(self):
        self.features = {}

    def register(self, feature_id, status="DEFINED") -> None:
        self.features[feature_id] = FeatureStatus(feature_id, status)

    def advance(self, feature_id, target) -> FeatureStatus:
        cur = self.features.get(feature_id)
        if not cur:
            raise ValueError(f"未知 feature {feature_id}")
        if target not in FEATURE_LIFECYCLE \
                or FEATURE_LIFECYCLE.index(target) < \
                FEATURE_LIFECYCLE.index(cur.status):
            raise ValueError(f"非法生命周期推进 {cur.status}→{target}")
        updated = FeatureStatus(feature_id, target)
        self.features[feature_id] = updated
        return updated

    def production_manifest(self) -> list:
        """Production Manifest：只允许 ACTIVE。"""
        return [fid for fid, f in self.features.items()
                if f.status == "ACTIVE"]

    def snapshot_feature_set(self) -> dict:
        """DecisionSnapshot 记录本次真正 ACTIVE 的 feature set。"""
        return {
            "active_features": self.production_manifest(),
            "total_features": len(self.features),
            "status_summary": {
                s: sum(1 for f in self.features.values()
                       if f.status == s)
                for s in FEATURE_LIFECYCLE},
        }
