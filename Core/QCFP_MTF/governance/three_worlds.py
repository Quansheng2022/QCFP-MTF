# coding: utf-8
"""Production Architecture 2.0（QCFP-MTF 2.8：30 号三态隔离）

Research / Shadow / Production 三个世界：
    Research  允许实验/新 Feature/参数优化，绝不能影响 Production
    Shadow    新版本与 Production 并行，比较 Decision/Risk/Position/
              Execution/Outcome 差异
    Production 只有 PIT/OOS/Ablation/Stress/Replay/Certification/
              Shadow 全过才允许进入

晋升路径：Research → Candidate → Shadow → Certified → Production
"""

from dataclasses import asdict, dataclass, field


WORLDS = ("RESEARCH", "SHADOW", "PRODUCTION")


@dataclass(frozen=True)
class WorldDecision:
    world: str
    action: str
    allowed: bool
    reason: str

    def as_dict(self) -> dict:
        return asdict(self)


def three_worlds_gate(world, action) -> WorldDecision:
    """三态门。

    RESEARCH：允许 experiment/feature/parameter_tune/train；
              禁止 production_decision/override_production。
    SHADOW：允许 parallel_run/compare；禁止 production_decision。
    PRODUCTION：只允许 certified_decision（读 Certified Policy）。
    """
    world = str(world or "").upper()
    action = str(action or "").upper()
    if world not in WORLDS:
        return WorldDecision(world, action, False,
                             f"未知世界 {world}")
    if world == "RESEARCH":
        allowed = action in ("EXPERIMENT", "FEATURE", "PARAMETER_TUNE",
                             "TRAIN", "HYPOTHESIS")
        return WorldDecision(world, action, allowed,
                             "RESEARCH 只允许实验" if allowed
                             else "RESEARCH 禁止影响 Production")
    if world == "SHADOW":
        allowed = action in ("PARALLEL_RUN", "COMPARE")
        return WorldDecision(world, action, allowed,
                             "SHADOW 并行运行" if allowed
                             else "SHADOW 禁止正式决策")
    allowed = action == "CERTIFIED_DECISION"
    return WorldDecision(world, action, allowed,
                         "PRODUCTION 只读 Certified" if allowed
                         else "PRODUCTION 禁止未认证动作")


def promote_to_production(checks: dict) -> tuple:
    """Research → Candidate → Shadow → Certified → Production。
    需要 pit/oos/ablation/stress/replay/certification/shadow 全过。"""
    required = ("pit", "oos", "ablation", "stress", "replay",
                "certification", "shadow")
    missing = [r for r in required if not checks.get(r)]
    return not missing, tuple(missing)


def shadow_comparison(production_metrics, shadow_metrics) -> dict:
    """Shadow 并行比较：Decision/Risk/Position/Execution/Outcome 差异。"""
    diffs = {}
    for key in ("decision", "risk", "position", "execution", "outcome"):
        p = float(production_metrics.get(key) or 0.0)
        s = float(shadow_metrics.get(key) or 0.0)
        diffs[key] = round(s - p, 4)
    max_diff = max((abs(v) for v in diffs.values()), default=0.0)
    return {"diffs": diffs, "max_difference": round(max_diff, 4),
            "acceptable": max_diff < 0.05}
