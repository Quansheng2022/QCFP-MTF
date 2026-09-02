# coding: utf-8
"""Controlled Learning Loop（QCFP-MTF 2.7：学习而不污染）

生产系统只能 WRITE → Outcome/Evidence；
研究系统只能 READ → Evidence / CREATE → Candidate；
新模型必须通过 Ablation + OOS + Replay + Stability + Cost Stress + Shadow
+ Human/Governance Approval 才能进入 Production。
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LearningProposal:
    candidate_version: str
    hypothesis: str
    ablation_ok: bool = False
    oos_ok: bool = False
    replay_ok: bool = False
    stability_ok: bool = False
    cost_stress_ok: bool = False
    shadow_ok: bool = False
    approved: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


REQUIRED_GATES = ("ablation_ok", "oos_ok", "replay_ok", "stability_ok",
                  "cost_stress_ok", "shadow_ok", "approved")


def validate_proposal(p: LearningProposal) -> tuple:
    """候选模型晋升门：全部通过才允许进入 Production"""
    failed = [g for g in REQUIRED_GATES if not getattr(p, g)]
    return not failed, tuple(failed)


class ResearchSandbox:
    """研究沙箱：生产写证据，研究读证据并创建候选（不直接改生产）"""

    def __init__(self):
        self.evidence = []
        self.candidates = []

    def write_outcome(self, outcome: dict) -> None:
        self.evidence.append(outcome)   # 生产 → 只写 Outcome/Evidence

    def read_evidence(self):
        return list(self.evidence)      # 研究 → 只读

    def create_candidate(self, proposal: LearningProposal) -> None:
        self.candidates.append(proposal)   # 研究 → 建候选，不写生产

    def promote(self, proposal: LearningProposal, lifecycle=None) -> tuple:
        ok, failed = validate_proposal(proposal)
        if not ok:
            return False, failed
        if lifecycle is not None:
            lifecycle.promote(proposal.candidate_version, "production")
        return True, ()
