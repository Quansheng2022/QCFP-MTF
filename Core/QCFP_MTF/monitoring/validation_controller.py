# coding: utf-8
"""Continuous Validation Controller（QCFP-MTF 2.8：70 号持续验证控制器）

把 Monitoring / Drift / OOS / Ablation / Replay / Stress / Release
统一为自动治理闭环：
    HEALTHY → WARNING → DEGRADED → REVIEW → HALTED

恢复流程（不能人工点"恢复交易"）：
    HALTED → Root Cause → Research → Validation → Certification →
    Shadow → PROMOTION
"""

from dataclasses import asdict, dataclass, field


CONTROLLER_STATES = ("HEALTHY", "WARNING", "DEGRADED", "REVIEW", "HALTED")


@dataclass(frozen=True)
class ControllerResult:
    state: str
    health_checks: dict
    recovery_required: bool
    recovery_steps: tuple
    triggered: tuple

    def as_dict(self) -> dict:
        d = asdict(self)
        d["recovery_steps"] = list(self.recovery_steps)
        d["triggered"] = list(self.triggered)
        return d


RECOVERY_STEPS = ("ROOT_CAUSE", "RESEARCH", "VALIDATION", "CERTIFICATION",
                  "SHADOW", "PROMOTION")


def validation_controller(checks: dict) -> ControllerResult:
    """checks：{system/model/data/wave/execution/risk: HEALTHY|WARNING|
    DEGRADED|FAIL} + 关键失败（ledger/replay/pit）。"""
    health = dict(checks)
    triggered = []
    worst = "HEALTHY"
    order = {s: i for i, s in enumerate(CONTROLLER_STATES)}
    for name, status in checks.items():
        if status not in ("HEALTHY",):
            triggered.append(f"{name}:{status}")
        s = "HALTED" if status in ("FAIL", "HALTED") else \
            "REVIEW" if status == "REVIEW" else \
            "DEGRADED" if status == "DEGRADED" else \
            "WARNING" if status == "WARNING" else "HEALTHY"
        if order[s] > order[worst]:
            worst = s
    # 关键失败：ledger/replay/pit → 直接 HALTED
    for critical in ("ledger", "replay", "pit"):
        if checks.get(critical) in ("FAIL", "HALTED"):
            worst = "HALTED"
            triggered.append(f"CRITICAL_{critical}")
    recovery_required = worst == "HALTED"
    return ControllerResult(
        state=worst, health_checks=health,
        recovery_required=recovery_required,
        recovery_steps=RECOVERY_STEPS if recovery_required else (),
        triggered=tuple(triggered))


def controller_to_md(r: ControllerResult) -> str:
    lines = [
        "# Continuous Validation Controller",
        "",
        f"**State：{r.state}**",
        "",
        "| 检查 | 状态 |", "| --- | --- |",
    ]
    for k, v in r.health_checks.items():
        lines.append(f"| {k} | {v} |")
    if r.recovery_required:
        lines += ["", "## 恢复流程（不可人工直接恢复交易）", ""]
        lines += [f"{i}. {s}" for i, s in enumerate(r.recovery_steps, 1)]
    return "\n".join(lines)
