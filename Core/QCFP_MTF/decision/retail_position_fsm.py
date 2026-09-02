# coding: utf-8
"""Retail Position FSM（正式接口，QCFP-MTF 2.2）

状态：FLAT → TESTING → BUILDING → HOLDING → TRIMMING → EXITING → COOLDOWN

冻结的转移规则（第一版，禁止状态跳跃）：
    FLAT      --ALLOW+Setup--> TESTING    --BLOCK/High--> FLAT
    TESTING   --Breakout+Perm--> BUILDING --Risk/Breakdown--> EXITING
    BUILDING  --Confirmation--> HOLDING   --Dist/High--> TRIMMING --Breakdown--> EXITING
    HOLDING   --Normal--> HOLDING         --Dist/High--> TRIMMING --Breakdown--> EXITING
    TRIMMING  --Recovery--> HOLDING       --Breakdown--> EXITING
    EXITING   --pos=0--> COOLDOWN
    COOLDOWN  --complete--> FLAT

优先级（最高→最低）：HARD_EXIT > Institutional Permission > MTF > Weekly > Daily。
Hard Exit 无条件 EXITING/COOLDOWN，不能被 BULLISH/ALLOW/BREAKOUT 覆盖。

2.2 收口（V31）：
    - Exit Event 是 FSM 的唯一退出输入（Exit Event Engine 单点计算，FSM 不再重算）；
    - Setup 同样由 Swing Setup Engine 单点计算后传入，FSM 不重复推导；
    - Permission × FSM 矩阵（permission_fsm_base）是**实际基准转移源**，
      transition() 先取矩阵基准，再叠加 Hard Exit / Lifecycle / Soft Exit /
      Setup / Risk 覆盖；每条生效规则记录为 rule_id（transition_audit）；
    - Permission = 风险增量上限：BLOCK/WATCH 下 target_position 不得高于 previous_position。
    - 状态-仓位一致性：0 仓位不得停留在 TESTING/BUILDING/HOLDING/TRIMMING
      （state_position_consistent），杜绝 TRIMMING→0 仓位后死锁。
    - 2.4 观察仓（Exploratory Exposure）：WATCH + ParticipationBudget(OBSERVE)
      允许 FLAT/COOLDOWN 进入 TESTING（观察），矩阵基准仍是 FLAT——
      观察例外是权限授予的（小预算 + Setup + 低/中风险），rule_id=participation_observe。
"""

from dataclasses import dataclass, field

from ..config.settings import retail_settings
from .hard_exit import ExitEvent, evaluate_exit_events
from .permission_policy import permission_state_violation
from .retail_position_sizing import retail_target_position


@dataclass
class RetailDecisionContext:
    institutional_permission: str = "WATCH"
    institutional_state: str = "NEUTRAL"
    mtf_regime: str = "BULLISH_WARNING"
    monthly_state: str = "Stable"
    weekly_signal: str = "Consolidation"
    daily_state: str = "DAILY_NEUTRAL"
    risk_level: str = "Medium"
    des_score: int = 0
    current_position: float = 0.0
    chase_filter: bool = False
    stop_triggered: bool = False
    hard_exit: bool = False
    exit_event: ExitEvent = None
    cooldown_remaining: int = 0
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row, settings=None) -> "RetailDecisionContext":
        _des = row.get("des_score")
        des = int(_des) if _des is not None and _des == _des else 0
        current_position = float(row.get("current_position") or 0.0)
        ev = evaluate_exit_events(
            des_score=des, weekly_signal=row.get("tactical_signal"),
            stop_triggered=row.get("stop_triggered"),
            risk_level=row.get("risk_level"),
            current_position=current_position, settings=settings)
        permission = row.get("institutional_permission", "WATCH")
        from ..setup.swing_setup import evaluate_swing_setup
        setup_type = evaluate_swing_setup(
            weekly_signal=row.get("tactical_signal"),
            daily_state=row.get("daily_state"),
            monthly_state=row.get("monthly_behavior_state"),
            permission=permission)
        return cls(
            institutional_permission=permission,
            institutional_state=row.get("institutional_state", "NEUTRAL"),
            mtf_regime=row.get("mtf_regime") or "BULLISH_WARNING",
            monthly_state=row.get("monthly_behavior_state") or "Stable",
            weekly_signal=row.get("tactical_signal") or "Consolidation",
            daily_state=row.get("daily_state") or "DAILY_NEUTRAL",
            risk_level=row.get("risk_level") or "Medium",
            des_score=des,
            current_position=current_position,
            chase_filter=bool(row.get("chase_filter")),
            stop_triggered=bool(row.get("stop_triggered")),
            hard_exit=ev.hard,
            exit_event=ev,
            cooldown_remaining=int(row.get("cooldown_remaining") or 0),
            extra={"setup_type": setup_type},
        )


STATES = ["FLAT", "TESTING", "BUILDING", "HOLDING", "TRIMMING", "EXITING", "COOLDOWN"]

# Permission × FSM 状态矩阵（V31 冻结，覆盖全部 7 个状态；Hard Exit/Lifecycle
# 独立于此矩阵，优先级更高；输出=基准目标状态，Risk/Setup 覆盖叠加其上）
PERMISSION_FSM_MATRIX = {
    "BLOCK": {"FLAT": "FLAT", "TESTING": "TRIMMING",
              "BUILDING": "TRIMMING", "HOLDING": "TRIMMING",
              "TRIMMING": "TRIMMING", "EXITING": "EXITING",
              "COOLDOWN": "COOLDOWN"},
    "WATCH": {"FLAT": "FLAT", "TESTING": "TESTING",
              "BUILDING": "BUILDING", "HOLDING": "HOLDING",
              "TRIMMING": "HOLDING", "EXITING": "EXITING",
              "COOLDOWN": "COOLDOWN"},
    "TEST": {"FLAT": "TESTING", "TESTING": "TESTING",
             "BUILDING": "BUILDING", "HOLDING": "HOLDING",
             "TRIMMING": "HOLDING", "EXITING": "EXITING",
             "COOLDOWN": "COOLDOWN"},
    "ALLOW": {"FLAT": "TESTING", "TESTING": "BUILDING",
              "BUILDING": "BUILDING", "HOLDING": "HOLDING",
              "TRIMMING": "HOLDING", "EXITING": "EXITING",
              "COOLDOWN": "COOLDOWN"},
    "STRONG_ALLOW": {"FLAT": "TESTING", "TESTING": "BUILDING",
                     "BUILDING": "BUILDING", "HOLDING": "HOLDING",
                     "TRIMMING": "HOLDING", "EXITING": "EXITING",
                     "COOLDOWN": "COOLDOWN"},
}

# Permission Ceiling（交易上限）：机构权限允许的最高风险承载状态
# （HOLDING 作为"维持既有仓位"在 WATCH+ 下允许；BLOCK 为特殊 De-risk 状态）
PERMISSION_CAP = {
    "BLOCK": "FLAT",
    "WATCH": "TESTING",
    "TEST": "TESTING",
    "ALLOW": "BUILDING",
    "STRONG_ALLOW": "HOLDING",
}
STATE_RANK = {"FLAT": 0, "COOLDOWN": 0, "EXITING": 0, "TESTING": 1,
              "TRIMMING": 1, "BUILDING": 2, "HOLDING": 3}


def permission_cap_exceeded(permission: str, state: str) -> bool:
    """状态级权限违规（V31 语义，与矩阵/政策一致）

    BLOCK：TESTING/BUILDING/HOLDING 均为违规（维持被禁止，必须去风险）；
    WATCH+：维持既有风险被允许，状态本身不构成违规——
            违规由 target 增量不变量 / 状态-仓位一致性判定。
    （旧 "WATCH+BUILDING 越权" 与矩阵"维持合法"的矛盾已消除）
    """
    if permission == "BLOCK":
        return state in ("TESTING", "BUILDING", "HOLDING")
    return False


def assert_permission_bound(permission: str, state: str) -> None:
    """越权即抛错（供测试/审计）"""
    if permission_cap_exceeded(permission, state):
        raise PermissionError(
            f"PermissionViolation: {permission} 不允许状态 {state}"
            f"（BLOCK 必须处于 FLAT/TRIMMING/EXITING/COOLDOWN）")


def permission_fsm_base(permission: str, state: str) -> str:
    """权限基准状态（矩阵查表；非法输入返回原状态）"""
    return PERMISSION_FSM_MATRIX.get(permission, {}).get(state, state)


@dataclass(frozen=True)
class TransitionInput:
    """FSM 转移输入（领域对象已计算完成，FSM 不接收原始 row 重算）"""
    permission: str
    exit_event: ExitEvent
    setup_type: str
    risk_level: str
    weekly_signal: str
    daily_state: str
    monthly_state: str
    previous_state: str
    previous_position: float
    chase_filter: bool = False
    cooldown_remaining: int = 0
    participation_mode: str = "STAND"


def permission_risk_increase_allowed(permission: str, previous_position: float,
                                     target_position: float) -> bool:
    """BLOCK / WATCH 是风险增量上限：target 不得高于 previous（维持/减仓允许）"""
    if permission in ("BLOCK", "WATCH"):
        return float(target_position) <= float(previous_position or 0.0) + 1e-9
    return True


def assert_no_risk_increase(permission: str, previous_position: float,
                            target_position: float) -> None:
    """越权即抛错（供测试/审计）：BLOCK/WATCH 不允许未经授权的风险增加"""
    if not permission_risk_increase_allowed(permission, previous_position,
                                            target_position):
        raise PermissionError(
            f"RiskIncreaseViolation: {permission} 不允许仓位从 "
            f"{previous_position} 增至 {target_position}")


def apply_permission_position_cap(permission: str, target_position: float,
                                  previous_position: float) -> float:
    """BLOCK / WATCH 下将 target 封顶为 previous（维持既有仓位，不新增风险）"""
    if permission in ("BLOCK", "WATCH"):
        return round(min(float(target_position), float(previous_position or 0.0)), 4)
    return target_position


def _setup_ok(setup_type, daily_state) -> bool:
    if setup_type is not None:
        return setup_type != "NONE"
    return daily_state in ("DAILY_BREAKOUT", "DAILY_PULLBACK",
                           "DAILY_ACCUMULATION")


def state_position_consistent(fsm_state: str, target_position: float) -> str:
    """状态-仓位一致性（V31）：0 仓位不得停留在风险承载/减仓状态

    TESTING/BUILDING/HOLDING + target=0 → FLAT；
    TRIMMING + target=0 → EXITING（→ COOLDOWN → FLAT），避免死锁。
    """
    if float(target_position or 0.0) > 1e-9:
        return fsm_state
    if fsm_state in ("TESTING", "BUILDING", "HOLDING"):
        return "FLAT"
    if fsm_state == "TRIMMING":
        return "EXITING"
    return fsm_state


def transition_audit(t: TransitionInput):
    """冻结的状态转移（V31：矩阵基准 + 事件覆盖），返回 (state, rule_ids)

    优先级：Hard Exit > Lifecycle（EXITING/COOLDOWN）> Permission × FSM 基准矩阵
            > Soft Exit / Permission 降级 / Setup / Risk 覆盖 > 状态-仓位一致性。
    """
    state = t.previous_state if t.previous_state in STATES else "FLAT"
    setup = t.setup_type
    rules = []
    # 1) Hard Exit（Exit Event Engine 唯一来源）> ALL
    if t.exit_event.hard:
        rules.append("hard_exit")
        return ("COOLDOWN" if state == "FLAT" else "EXITING"), tuple(rules)
    # 2) Lifecycle 状态流（独立于权限矩阵）
    if state == "EXITING":
        rules.append("lifecycle_exit")
        return "COOLDOWN", tuple(rules)
    if state == "COOLDOWN":
        if t.cooldown_remaining > 0:
            rules.append("cooldown")
            return "COOLDOWN", tuple(rules)
        if t.permission in ("ALLOW", "STRONG_ALLOW", "TEST") \
                and (_setup_ok(setup, t.daily_state) and (setup is None or
                      setup in ("BREAKOUT", "PULLBACK", "RECOVERY"))) \
                and t.risk_level in ("Low", "Medium") and not t.chase_filter:
            rules.append("cooldown_ready")
            return "TESTING", tuple(rules)
        if t.permission == "WATCH" and t.participation_mode == "OBSERVE" \
                and setup in ("BREAKOUT", "PULLBACK", "RECOVERY") \
                and t.risk_level in ("Low", "Medium") and not t.chase_filter:
            rules.append("cooldown_ready_observe")
            return "TESTING", tuple(rules)
        rules.append("cooldown_expired")
        return "FLAT", tuple(rules)
    # 3) 矩阵基准（Canonical Base State）
    base = permission_fsm_base(t.permission, state)
    final = base
    soft_exit = t.exit_event.kind in ("RISK_EXIT", "BREAKDOWN")
    if state == "TESTING":
        if soft_exit:
            rules.append("soft_exit")
            final = "EXITING"
        elif t.permission == "BLOCK":
            rules.append("permission_degrade_block")
            final = "TRIMMING"
        elif t.permission in ("ALLOW", "STRONG_ALLOW") \
                and (setup in ("BREAKOUT", "PULLBACK") or
                     t.daily_state == "DAILY_BREAKOUT") and not t.chase_filter:
            rules.append("setup_breakout")
            final = "BUILDING"
        elif base not in ("TESTING", "TRIMMING"):
            rules.append("setup_wait")
            final = "TESTING"
        else:
            rules.append("permission_base")
    elif state == "BUILDING":
        if soft_exit:
            rules.append("soft_exit")
            final = "EXITING"
        elif t.permission == "BLOCK":
            rules.append("permission_degrade_block")
            final = "TRIMMING"
        elif setup == "BREAKOUT" or t.weekly_signal == "Breakout" or (
                t.daily_state == "DAILY_BREAKOUT" and not t.chase_filter):
            rules.append("setup_breakout")
            final = "HOLDING"
        elif t.risk_level == "High" or t.daily_state == "DAILY_DISTRIBUTION":
            rules.append("risk_trim")
            final = "TRIMMING"
        else:
            rules.append("permission_base")
    elif state in ("HOLDING", "TRIMMING"):
        if soft_exit:
            rules.append("soft_exit")
            final = "EXITING"
        elif t.permission == "BLOCK":
            rules.append("permission_degrade_block")
            final = "TRIMMING"
        elif t.permission == "WATCH" and t.previous_position > 0 \
                and (t.risk_level == "High"
                     or t.daily_state == "DAILY_DISTRIBUTION"):
            rules.append("watch_risk_trim")
            final = "TRIMMING"
        elif t.risk_level == "High" or t.daily_state == "DAILY_DISTRIBUTION":
            rules.append("risk_trim")
            final = "TRIMMING"
        else:
            rules.append("permission_base")
    else:  # FLAT 及其他
        if t.permission == "BLOCK" or t.risk_level in ("High", "Extreme"):
            rules.append("permission_block")
            final = "FLAT"
        elif t.permission in ("ALLOW", "STRONG_ALLOW", "TEST") \
                and _setup_ok(setup, t.daily_state) \
                and t.risk_level in ("Low", "Medium") and not t.chase_filter:
            rules.append("setup_confirm")
            final = "TESTING"
        elif t.permission == "WATCH" and t.participation_mode == "OBSERVE" \
                and _setup_ok(setup, t.daily_state) \
                and t.risk_level in ("Low", "Medium") and not t.chase_filter:
            rules.append("participation_observe")
            final = "TESTING"
        elif base != "FLAT":
            rules.append("setup_wait")
            final = "FLAT"
        else:
            rules.append("permission_base")
    # 4) 状态-仓位一致性（transition 层：previous_position=0 的死状态归位）
    if final in ("BUILDING", "HOLDING") and t.previous_position == 0:
        rules.append("state_position_reset")
        final = "FLAT"
    return final, tuple(rules)


def transition(t: TransitionInput) -> str:
    """冻结的状态转移（返回最终状态；审计规则见 transition_audit）"""
    return transition_audit(t)[0]


def chase_filter(row, settings) -> bool:
    """追高过滤：日线突破 + 52W 位置偏高 → 不追（等回踩）"""
    cfg = retail_settings(settings).get("fsm", {})
    threshold = float(cfg.get("chase_52w", 0.6))
    if row.get("daily_state") == "DAILY_BREAKOUT":
        pos = row.get("q_position_52w")
        if pos is not None and pos > threshold:
            return True
    return False


def next_state(state: str, ctx: RetailDecisionContext) -> str:
    """兼容接口：Context → TransitionInput → transition()

    canonical 路径（DecisionSnapshot / Shadow / from_row）已预计算 exit_event；
    仅当旧调用方直接构造 Context 且未传 exit_event 时，才按字段派生一次
    （保证旧测试/旧接口行为不变，但正式链路不存在重复计算）。
    """
    ev = ctx.exit_event
    if ev is None:
        ev = evaluate_exit_events(
            des_score=ctx.des_score, weekly_signal=ctx.weekly_signal,
            stop_triggered=ctx.stop_triggered, risk_level=ctx.risk_level,
            current_position=ctx.current_position, settings=None)
    return transition(TransitionInput(
        permission=ctx.institutional_permission,
        exit_event=ev,
        setup_type=ctx.extra.get("setup_type") if ctx.extra else None,
        risk_level=ctx.risk_level,
        weekly_signal=ctx.weekly_signal,
        daily_state=ctx.daily_state,
        monthly_state=ctx.monthly_state,
        previous_state=state,
        previous_position=ctx.current_position,
        chase_filter=ctx.chase_filter,
        cooldown_remaining=ctx.cooldown_remaining,
    ))


def build_fsm_timeline(rows, settings, cooldown_weeks=None):
    """按股票分组处理（跨股票状态隔离）；rows 为 dict 序列，输出 (state, cooldown) 序列

    V31：有状态重放——每只股票跟踪 previous_position，并用
    retail_target_position + state_position_consistent 保持状态-仓位一致。
    """
    cfg = retail_settings(settings).get("fsm", {})
    cd = int(cooldown_weeks or cfg.get("cooldown_weeks", 2))
    states, positions, remain, out = {}, {}, {}, []
    for r in rows:
        code = r.get("stock_code", "__single__")
        state = states.get(code, "FLAT")
        pos = positions.get(code, 0.0)
        remaining = remain.get(code, 0)
        if state == "COOLDOWN":
            remaining -= 1
            if remaining <= 0:
                state, remaining = "FLAT", 0
        ctx = RetailDecisionContext.from_row(
            {**dict(r), "current_position": pos}, settings)
        ctx.cooldown_remaining = remaining
        nxt = next_state(state, ctx)
        raw = retail_target_position(nxt, pos, settings)
        nxt = state_position_consistent(nxt, raw)
        pos = retail_target_position(nxt, pos, settings)
        if state != "COOLDOWN" and nxt == "COOLDOWN":
            remaining = cd
        states[code], positions[code], remain[code] = nxt, pos, remaining
        out.append((nxt, max(remaining, 0)))
    return out
