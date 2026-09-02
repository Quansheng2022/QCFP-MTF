# coding: utf-8
"""Release / Promotion Gate（QCFP-MTF 2.8：40 号生产晋升总闸门）

新版本不能因"Backtest Sharpe ↑"直接进生产，必须 13 步全过：
    Research → Unit Test → Invariant Test → PIT → OOS → Ablation →
    Cost Stress → Execution Stress → Regime Robustness → Replay →
    Shadow → Governance Review → PROMOTE

Release 状态阶梯：
    EXPERIMENTAL → VALIDATED → SHADOW → PRODUCTION → DEGRADED → HALTED
任一关键 Gate FAIL → NO PROMOTION。
"""

from dataclasses import asdict, dataclass, field


PROMOTION_STEPS = (
    "research", "unit_test", "invariant_test", "pit", "oos", "ablation",
    "cost_stress", "execution_stress", "regime_robustness", "replay",
    "shadow", "governance_review", "promote",
)

RELEASE_LADDER = (
    "EXPERIMENTAL", "VALIDATED", "SHADOW", "PRODUCTION",
    "DEGRADED", "HALTED",
)


class PromotionGateError(ValueError):
    pass


@dataclass(frozen=True)
class PromotionResult:
    version: str
    gates: dict
    passed: bool
    failed: tuple
    release_status: str

    def as_dict(self) -> dict:
        d = asdict(self)
        d["failed"] = list(self.failed)
        return d


def promotion_gate(version, checks: dict) -> PromotionResult:
    """13 步晋升门：全部通过 → PROMOTE，否则 NO PROMOTION。"""
    failed = [step for step in PROMOTION_STEPS if not checks.get(step)]
    passed = not failed
    status = "SHADOW" if passed else "EXPERIMENTAL"
    if passed and checks.get("governance_review") \
            and checks.get("shadow"):
        status = "PRODUCTION"
    return PromotionResult(
        version=version, gates=dict(checks), passed=passed,
        failed=tuple(failed), release_status=status)


def assert_promotion_gate(version, checks: dict) -> None:
    r = promotion_gate(version, checks)
    if not r.passed:
        raise PromotionGateError(
            f"PromotionGate: {version} NO PROMOTION（"
            f"未过：{', '.join(r.failed)}）")


def promote_release_status(current, target) -> str:
    """Release 状态阶梯推进（禁止回退/跳级降级需走 DEGRADED）。"""
    if target not in RELEASE_LADDER or current not in RELEASE_LADDER:
        raise PromotionGateError(f"非法 Release 状态 {current}→{target}")
    ci, ti = RELEASE_LADDER.index(current), RELEASE_LADDER.index(target)
    if ti < ci:
        raise PromotionGateError(
            f"禁止回退 Release 状态 {current}→{target}（降级须走 DEGRADED）")
    return target


def promotion_to_md(r: PromotionResult) -> str:
    lines = [
        f"# Promotion Gate　{r.version}",
        "",
        f"**结果：{'✅ PROMOTE' if r.passed else '❌ NO PROMOTION'}**　"
        f"Release：{r.release_status}",
        "",
        "| 步骤 | 状态 |", "| --- | --- |",
    ]
    for step in PROMOTION_STEPS:
        lines.append(f"| {step} | {'✅' if r.gates.get(step) else '❌'} |")
    if r.failed:
        lines += ["", f"未通过：{', '.join(r.failed)}"]
    return "\n".join(lines)
