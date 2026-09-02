# coding: utf-8
"""Research-to-Production Provenance（QCFP-MTF 2.8：90 号全链路溯源）

任何 Production Release 必须反向追踪：
    Production Version → Release ID → Certification → OOS → Ablation →
    Experiment → Hypothesis → Dataset → PIT Snapshot → Feature Version →
    Code Commit → Configuration

回答：
    用的哪个模型版本？为什么批准？依据哪次 OOS？数据是否 PIT？
    相对 Baseline 增加多少 Alpha？哪个 Governance Gate 批准？
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ResearchProvenance:
    production_version: str
    release_id: str
    certification: str = ""
    oos_result: dict = field(default_factory=dict)
    ablation_result: dict = field(default_factory=dict)
    experiment_id: str = ""
    hypothesis: str = ""
    dataset: str = ""
    pit_snapshot: str = ""
    feature_version: str = ""
    code_commit: str = ""
    configuration: dict = field(default_factory=dict)
    approved_by: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    def chain(self) -> list:
        return [
            ("production_version", self.production_version),
            ("release_id", self.release_id),
            ("certification", self.certification),
            ("oos_result", self.oos_result),
            ("ablation_result", self.ablation_result),
            ("experiment_id", self.experiment_id),
            ("hypothesis", self.hypothesis),
            ("dataset", self.dataset),
            ("pit_snapshot", self.pit_snapshot),
            ("feature_version", self.feature_version),
            ("code_commit", self.code_commit),
            ("configuration", self.configuration),
            ("approved_by", self.approved_by),
        ]


class ProvenanceError(ValueError):
    pass


def assert_provenance_complete(p: ResearchProvenance) -> None:
    """全链路完整性：任一关键环节缺失 → 生产溯源不成立。"""
    required = ("release_id", "certification", "oos_result",
                "ablation_result", "experiment_id", "hypothesis",
                "dataset", "pit_snapshot", "feature_version",
                "code_commit", "approved_by")
    missing = []
    for key in required:
        v = getattr(p, key)
        if not v or (isinstance(v, dict) and not v):
            missing.append(key)
    if missing:
        raise ProvenanceError(
            f"Provenance: {p.production_version} 溯源链缺失 "
            f"{missing}，禁止声称经过完整研究验证")


def provenance_to_md(p: ResearchProvenance) -> str:
    lines = [
        f"# Research-to-Production Provenance　{p.production_version}",
        "",
        "| 环节 | 内容 |", "| --- | --- |",
    ]
    for key, val in p.chain():
        if isinstance(val, dict):
            val = str(val)
        lines.append(f"| {key} | {val} |")
    return "\n".join(lines)
