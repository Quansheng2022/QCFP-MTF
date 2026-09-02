# coding: utf-8
"""Alpha Discovery Pipeline（QCFP-MTF 2.8：41 号 Alpha 自动发现管线）

系统自动产生候选假设，但所有候选必须经过严格治理：
    Candidate Feature/Relationship → Hypothesis → Evidence →
    Expected Mechanism → Test → Result → Confidence → ALPHA_REGISTRY

重点：不是"让 AI 自动找到赚钱指标"，而是
"自动产生候选，但未经验证不能进入生产"。
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CandidateAlpha:
    candidate_id: str
    hypothesis: str
    features: tuple = field(default_factory=tuple)
    expected_mechanism: str = ""
    evidence_level: str = "L0_observation"
    test_result: dict = field(default_factory=dict)
    confidence: float = 0.0
    status: str = "candidate"     # candidate/validated/rejected/in_registry
    created_at: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d["features"] = list(self.features)
        return d


class AlphaDiscoveryPipeline:
    def __init__(self):
        self.candidates = {}

    def propose(self, candidate_id, hypothesis, features,
                expected_mechanism="") -> CandidateAlpha:
        if candidate_id in self.candidates:
            raise ValueError(f"候选 {candidate_id} 已存在")
        c = CandidateAlpha(
            candidate_id=candidate_id, hypothesis=hypothesis,
            features=tuple(features),
            expected_mechanism=expected_mechanism,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.candidates[candidate_id] = c
        return c

    def record_test(self, candidate_id, metrics, confidence,
                    evidence_level) -> CandidateAlpha:
        c = self.candidates.get(candidate_id)
        if not c:
            raise ValueError(f"未知候选 {candidate_id}")
        updated = CandidateAlpha(
            candidate_id=c.candidate_id, hypothesis=c.hypothesis,
            features=c.features,
            expected_mechanism=c.expected_mechanism,
            evidence_level=evidence_level, test_result=dict(metrics),
            confidence=round(float(confidence), 4),
            status="validated" if float(confidence) >= 0.6
            else "rejected",
            created_at=c.created_at)
        self.candidates[candidate_id] = updated
        return updated

    def promote_to_registry(self, candidate_id, registry=None) -> bool:
        c = self.candidates.get(candidate_id)
        if not c or c.status != "validated":
            return False
        if registry is not None:
            from ..alpha.registry import AlphaSource
            registry.register(AlphaSource(
                alpha_id=candidate_id, source="discovery_pipeline",
                hypothesis=c.hypothesis,
                feature_dependencies=c.features,
                validation_status="validated"))
        updated = CandidateAlpha(
            candidate_id=c.candidate_id, hypothesis=c.hypothesis,
            features=c.features,
            expected_mechanism=c.expected_mechanism,
            evidence_level=c.evidence_level, test_result=c.test_result,
            confidence=c.confidence, status="in_registry",
            created_at=c.created_at)
        self.candidates[candidate_id] = updated
        return True
