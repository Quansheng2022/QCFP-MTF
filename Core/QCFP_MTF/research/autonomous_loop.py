# coding: utf-8
"""Autonomous Research Loop（QCFP-MTF 2.8：50 号自主研究闭环）

发现 → 假设 → 沙箱 → PIT/OOS → Ablation → Stress → Certification →
Shadow → Production → Monitor → Decay → Challenger → Retire → Research

关键边界：AI/Research 只能"发现候选"，不能未经治理自动改变决策。
"""


LOOP_STAGES = ("DISCOVER", "HYPOTHESIS", "SANDBOX", "PIT_OOS", "ABLATION",
               "STRESS", "CERTIFICATION", "SHADOW", "PRODUCTION",
               "MONITOR", "DECAY", "CHALLENGER", "RETIRE", "RESEARCH")


def autonomous_research_loop(current_stage, checks: dict = None) -> dict:
    """闭环推进（只进不退；RETIRE 后回到 RESEARCH 开始新循环）。"""
    checks = checks or {}
    if current_stage not in LOOP_STAGES:
        return {"stage": current_stage, "blocked": True,
                "reason": f"未知阶段 {current_stage}"}
    idx = LOOP_STAGES.index(current_stage)
    # 关键门：进入 PRODUCTION 必须通过 Certification；进入 SHADOW 前须验证
    if current_stage == "CERTIFICATION" and not checks.get("certified"):
        return {"stage": current_stage, "blocked": True,
                "reason": "未认证，禁止进入 SHADOW"}
    if current_stage == "SHADOW" and not checks.get("shadow_ok"):
        return {"stage": current_stage, "blocked": True,
                "reason": "Shadow 未通过，禁止进入 PRODUCTION"}
    if current_stage == "DECAY" and not checks.get("decay_confirmed"):
        return {"stage": current_stage, "blocked": True,
                "reason": "衰减未确认，不进入 CHALLENGER"}
    next_stage = LOOP_STAGES[(idx + 1) % len(LOOP_STAGES)]
    return {"stage": next_stage, "blocked": False,
            "reason": f"{current_stage} → {next_stage}"}


class AutonomousResearchController:
    """自主研究闭环控制器（带治理守卫）。"""

    def __init__(self):
        self.current = "DISCOVER"
        self.history = []

    def advance(self, checks=None):
        r = autonomous_research_loop(self.current, checks)
        if not r["blocked"]:
            self.history.append(self.current)
            self.current = r["stage"]
        return r

    def summary(self) -> dict:
        return {"current_stage": self.current,
                "loop_cycles": self.history.count("RESEARCH"),
                "stages_visited": len(self.history),
                "governance_boundary": "AI 只能发现候选，"
                                       "不能未经治理改变决策"}
