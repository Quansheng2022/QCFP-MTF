# coding: utf-8
"""Feature Registry（QCFP-MTF 2.8：12 号特征注册表）

每个 Feature 必须有完整元数据：
    feature_id / name / definition / source / source_table /
    source_column / calculation / frequency / available_at / lookback /
    PIT_grade / transform_version / owner / status

实现 Feature → Lineage → Decision，而不是黑箱 Wave=0.73。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class FeatureMeta:
    feature_id: str
    feature_name: str
    definition: str = ""
    source: str = ""
    source_table: str = ""
    source_column: str = ""
    calculation: str = ""
    frequency: str = ""
    available_at: str = ""
    lookback: str = ""
    pit_grade: str = "C"
    transform_version: str = ""
    owner: str = ""
    status: str = "research"

    def as_dict(self) -> dict:
        return asdict(self)


class FeatureRegistry:
    def __init__(self):
        self.features = {}

    def register(self, meta: FeatureMeta) -> None:
        self.features[meta.feature_id] = meta

    def get(self, feature_id) -> FeatureMeta:
        return self.features.get(feature_id)

    def by_status(self, status) -> list:
        return [f.feature_id for f in self.features.values()
                if f.status == status]

    def pit_grade_summary(self) -> dict:
        from collections import Counter
        return dict(Counter(f.pit_grade for f in self.features.values()))

    def registry_report(self) -> dict:
        return {
            "n_features": len(self.features),
            "features": {k: v.as_dict() for k, v in self.features.items()},
            "pit_grade_summary": self.pit_grade_summary(),
        }
