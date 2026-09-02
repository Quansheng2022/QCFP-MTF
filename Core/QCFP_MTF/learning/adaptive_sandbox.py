# coding: utf-8
"""Adaptive Policy Sandbox（QCFP-MTF 2.8：69 号自适应策略沙箱）

允许系统学习，但禁止系统未经治理自行改变交易规则：
    Live Observation → Research Proposal → Sandbox → Backtest → OOS →
    Ablation → Stress → Replay → Release Gate → Production

生产系统只能读取 Certified Policy，不能读取 Experimental Policy。
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime


class SandboxGuardError(ValueError):
    pass


@dataclass(frozen=True)
class Policy:
    policy_id: str
    params: dict
    status: str = "experimental"     # experimental / candidate / certified
    created_at: str = ""
    certification_gates: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["certification_gates"] = list(self.certification_gates)
        return d


class AdaptiveSandbox:
    """生产只读 Certified；研究在沙箱内实验。"""

    def __init__(self):
        self.policies = {}

    def propose(self, policy_id, params) -> Policy:
        """研究 → 提出候选策略（experimental，生产不可读）。"""
        if policy_id in self.policies:
            raise SandboxGuardError(f"策略 {policy_id} 已存在")
        p = Policy(policy_id=policy_id, params=dict(params),
                   created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.policies[policy_id] = p
        return p

    def certify(self, policy_id, gates: dict) -> Policy:
        """候选 → Certified：必须通过全部研究门（backtest/oos/ablation/
        stress/replay/release_gate）。"""
        p = self.policies.get(policy_id)
        if not p:
            raise SandboxGuardError(f"未知策略 {policy_id}")
        required = ("backtest", "oos", "ablation", "stress", "replay",
                    "release_gate")
        missing = [g for g in required if not gates.get(g)]
        if missing:
            raise SandboxGuardError(
                f"Sandbox: {policy_id} 未通过研究门 {missing}，禁止 Certified")
        certified = Policy(
            policy_id=p.policy_id, params=p.params, status="certified",
            created_at=p.created_at,
            certification_gates=tuple(gates))
        self.policies[policy_id] = certified
        return certified

    def get_certified_policy(self, policy_id=None) -> Policy:
        """生产唯一入口：只能读 Certified 策略。"""
        if policy_id:
            p = self.policies.get(policy_id)
            if not p:
                raise SandboxGuardError(f"未知策略 {policy_id}")
            if p.status != "certified":
                raise SandboxGuardError(
                    f"Sandbox: {policy_id} 为 {p.status}，生产禁止读取")
            return p
        certified = [p for p in self.policies.values()
                     if p.status == "certified"]
        if not certified:
            raise SandboxGuardError("Sandbox: 无 Certified 策略可供生产")
        return sorted(certified, key=lambda x: x.created_at)[-1]
