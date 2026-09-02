# coding: utf-8
"""Exit Event Engine（Kill Switch + 软退出，QCFP-MTF 2.2）

RULE 06：Hard Risk Exit 覆盖所有普通看多信号（BULLISH / ALLOW / BREAKOUT 均不能覆盖）。
Exit Event 是 FSM 的唯一退出输入（单点计算）：FSM 不再自行重新解释 DES/Extreme/Stop。
"""

from dataclasses import dataclass

# Exit Severity（2.4 三级结构）：
#   L1 = 纪律性退出（软退出/破位，可再评估）→ is_exit=True, is_forced=False, is_hard=False
#   L2 = 风险性退出（止损/强制降杠杆，必须减仓）→ is_exit=True, is_forced=True, is_hard=False
#   L3 = 致命退出（DES 硬退出，无条件离场）→ is_exit=True, is_forced=True, is_hard=True
EXIT_SEVERITY = {
    "NONE": 0,
    "RISK_EXIT": 1,
    "BREAKDOWN": 1,
    "STOP_EXIT": 2,
    "FORCED_DELEVERAGE": 2,
    "HARD_EXIT": 3,
}


@dataclass(frozen=True)
class ExitEvent:
    """统一退出事件（可审计：EXIT 到底由谁触发）"""
    kind: str          # NONE / HARD_EXIT / STOP_EXIT / FORCED_DELEVERAGE
    reason: str = None

    @property
    def hard(self) -> bool:
        """无条件离场集合（L2+L3）：STOP/FORCED/HARD 都强制退出（FSM 最高优先级用）"""
        return self.kind in ("HARD_EXIT", "STOP_EXIT", "FORCED_DELEVERAGE")

    @property
    def is_exit(self) -> bool:
        """是否退出事件（L1+L2+L3，含软退出）"""
        return self.kind != "NONE"

    @property
    def is_forced(self) -> bool:
        """是否强制退出（L2+L3：止损/降杠杆/致命）"""
        return self.kind in ("STOP_EXIT", "FORCED_DELEVERAGE", "HARD_EXIT")

    @property
    def is_hard(self) -> bool:
        """是否致命退出（L3：仅 HARD_EXIT，DES 硬退出）"""
        return self.kind == "HARD_EXIT"

    @property
    def severity(self) -> int:
        """退出严重度：L1 纪律性 / L2 风险性 / L3 致命"""
        return EXIT_SEVERITY.get(self.kind, 0)


def evaluate_exit_events(des_score=0, weekly_signal=None, stop_triggered=False,
                         risk_level=None, current_position=0.0,
                         settings=None) -> ExitEvent:
    """统一评估退出事件（FSM 不再自行重新解释 DES/Extreme/Stop）

    优先级（最高→最低）：
        HARD_EXIT（DES≥阈值）→ FORCED_DELEVERAGE（Extreme）
        → STOP_EXIT（止损）→ FORCED_DELEVERAGE（周线破位+持仓）
        → RISK_EXIT（DES≥软阈值，5 起）→ BREAKDOWN（周线破位、空仓）
        → NONE
    """
    threshold = int((settings or {}).get("risk", {}).get("hard_exit", {})
                    .get("des_threshold", 7))
    soft_threshold = int((settings or {}).get("risk", {}).get("hard_exit", {})
                         .get("soft_des_threshold", 5))
    if (des_score or 0) >= threshold:
        return ExitEvent("HARD_EXIT", "des_ge_threshold")
    if risk_level == "Extreme":
        return ExitEvent("FORCED_DELEVERAGE", "extreme_risk")
    if stop_triggered:
        return ExitEvent("STOP_EXIT", "stop_triggered")
    if weekly_signal == "Breakdown" and (current_position or 0.0) > 0:
        return ExitEvent("FORCED_DELEVERAGE", "weekly_breakdown_with_position")
    if (des_score or 0) >= soft_threshold:
        return ExitEvent("RISK_EXIT", "des_ge_soft_threshold")
    if weekly_signal == "Breakdown":
        return ExitEvent("BREAKDOWN", "weekly_breakdown")
    return ExitEvent("NONE")


def evaluate_hard_exit(des_score=0, weekly_signal=None, stop_triggered=False,
                       risk_level=None, current_position=0.0,
                       settings=None) -> tuple:
    """返回 (hard_exit: bool, reason: str|None)

    触发条件：DES≥threshold / Extreme 风险 / 止损触发 /
    周线破位（仅当已有持仓，避免空仓被无端拉入 COOLDOWN）。
    兼容旧接口；硬退出语义由 ExitEvent.hard 统一给出。
    """
    ev = evaluate_exit_events(des_score=des_score, weekly_signal=weekly_signal,
                              stop_triggered=stop_triggered, risk_level=risk_level,
                              current_position=current_position, settings=settings)
    return ev.hard, ev.reason
