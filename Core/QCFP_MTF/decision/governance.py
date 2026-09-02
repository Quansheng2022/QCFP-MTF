# coding: utf-8
"""Governance Validator（QCFP-MTF 2.5：统一仓位治理器）

所有仓位最终必须经过一道门，禁止 FSM / Permission / Budget / Sizing
各自绕过：

    Institutional Permission
        ↓
    Participation Budget
        ↓
    FSM
        ↓
    Sizing
        ↓
    Governance Validator  ← 本模块
        ↓
    Final Target

不变量：
    I1  HardExit（severity==3）→ final_target == 0
    I2  BLOCK → final_target == 0
    I3  WATCH（非 OBSERVE）→ final_target ≤ previous_position
    I4  FinalTarget ≤ ParticipationCap（观察仓例外：target ≤ 观察上限）
    I5  ParticipationCap ≤ Institutional Risk Envelope（权限状态上限）
    I6  target>0 时不得停留在无风险状态（由 state_position_consistent 保证）
"""


class GovernanceViolation(ValueError):
    pass


def add_risk_gate(permission, setup_type, risk_level, fsm_state,
                  trade_quality, position, permission_cap,
                  min_tradable=40) -> tuple:
    """ADD_RISK_GATE（2.6）：加仓资格，全部满足才允许新增风险

    Permission >= TEST 且 Setup 有效 且 Risk<=Medium 且 FSM∈{TESTING,BUILDING}
    且 TQS>=门槛 且 Position<Permission Cap。
    任一失败 → 禁止加仓（不一定要求卖出）。
    返回 (allowed, reasons)
    """
    from .permission_policy import permission_level
    reasons = []
    if permission_level(permission) < permission_level("TEST"):
        reasons.append("PERMISSION_BELOW_TEST")
    if setup_type in (None, "NONE"):
        reasons.append("SETUP_ABSENT")
    if risk_level not in ("Low", "Medium"):
        reasons.append("RISK_TOO_HIGH")
    if fsm_state not in ("TESTING", "BUILDING"):
        reasons.append("FSM_NOT_ACCUMULATING")
    if float(trade_quality or 0) < float(min_tradable):
        reasons.append("TRADE_QUALITY_LOW")
    if float(position or 0) >= float(permission_cap or 1.0) - 1e-9:
        reasons.append("POSITION_AT_CAP")
    return not reasons, tuple(reasons)


def reentry_gate(cooldown_remaining, institutional_state, setup_type,
                 risk_level, permission) -> tuple:
    """RE-ENTRY GATE（2.6）：卖出后快速买回防护

    冷却结束 + Institutional 重新确认 + Setup 重新确认 + Risk 允许 +
    Permission>=WATCH，全部满足才允许 TESTING 再入场。
    返回 (allowed, reasons)
    """
    from .permission_policy import permission_level
    reasons = []
    if int(cooldown_remaining or 0) > 0:
        reasons.append("COOLDOWN_ACTIVE")
    if institutional_state in (None, "", "DISTRIBUTION",
                               "DISTRIBUTION_STRONG", "CAPITULATION"):
        reasons.append("INSTITUTIONAL_NOT_CONFIRMED")
    if setup_type in (None, "NONE"):
        reasons.append("SETUP_ABSENT")
    if risk_level not in ("Low", "Medium"):
        reasons.append("RISK_TOO_HIGH")
    if permission_level(permission) < permission_level("WATCH"):
        reasons.append("PERMISSION_BELOW_WATCH")
    return not reasons, tuple(reasons)


def assert_position_governance(permission, participation_mode, budget_cap,
                               previous_position, target, exit_severity=0,
                               setup_type=None, risk_level=None) -> None:
    """统一仓位治理断言：违反任何一条即抛 GovernanceViolation"""
    target = float(target or 0.0)
    prev = float(previous_position or 0.0)
    cap = float(budget_cap or 0.0)
    # I1 HardExit → 0
    if int(exit_severity or 0) >= 3 and target > 1e-9:
        raise GovernanceViolation(
            f"I1: HardExit(severity={exit_severity}) 但 target={target}")
    # I2 BLOCK → 新仓 0；既有仓位允许逐步去风险（target < previous，见 G-008）
    if permission == "BLOCK" and target > max(prev, 1e-9) + 1e-9:
        raise GovernanceViolation(f"I2: BLOCK 但 target={target}")
    # I3 WATCH 非观察 → ≤ previous
    if permission == "WATCH" and participation_mode != "OBSERVE" \
            and target > prev + 1e-9:
        raise GovernanceViolation(
            f"I3: WATCH({participation_mode}) target={target} > previous={prev}")
    # I4 FinalTarget ≤ ParticipationCap（观察仓只约束新增暴露：
    #    既有仓位维持 ≤ max(previous, 观察上限)）
    if participation_mode == "OBSERVE":
        if target > max(prev, cap) + 1e-9:
            raise GovernanceViolation(
                f"I4: OBSERVE target={target} > max(previous={prev},"
                f" cap={cap})")
    elif target > max(prev, cap) + 1e-9 and cap < 1.0:
        raise GovernanceViolation(
            f"I4: target={target} > max(previous={prev}, cap={cap})")
    # I5 Budget ≤ 权限风险包络：OBSERVE 只在 WATCH 下合法；EXPLORE/TRADE 只在高权限
    if participation_mode == "OBSERVE" and permission not in ("WATCH",):
        raise GovernanceViolation(
            f"I5: OBSERVE 与权限 {permission} 不匹配")
    if participation_mode == "EXPLORE" and permission not in ("TEST", "ALLOW",
                                                              "STRONG_ALLOW"):
        raise GovernanceViolation(
            f"I5: EXPLORE 与权限 {permission} 不匹配")
    if participation_mode == "TRADE" and permission not in ("ALLOW",
                                                            "STRONG_ALLOW"):
        raise GovernanceViolation(
            f"I5: TRADE 与权限 {permission} 不匹配")
    return None


def governance_matrix_ok(permission, setup_type, risk_level,
                         target, previous_position=None) -> tuple:
    """机器可执行越权矩阵（审查表落代码）

    BLOCK → 渐进去风险（target ≤ previous_position，若有上下文）；
    WATCH 无 Setup / High+ → 0；WATCH+Setup+Low/Med → ≤Observe；
    TEST → ≤Explore；ALLOW → ≤Trade；STRONG_ALLOW → ≤Strong。
    返回 (ok, reasons)
    """
    t = float(target or 0.0)
    prev = float(previous_position or 0.0) \
        if previous_position is not None else None
    reasons = []
    if permission == "BLOCK":
        if prev is not None and t > prev + 1e-9:
            reasons.append("BLOCK_TARGET_ABOVE_PREVIOUS")
        elif prev is None and t > 1e-9:
            reasons.append("BLOCK_TARGET_NONZERO")
    elif permission == "WATCH":
        if setup_type in (None, "NONE") and t > 1e-9:
            reasons.append("WATCH_NO_SETUP")
        if risk_level not in ("Low", "Medium") and t > 1e-9:
            reasons.append("WATCH_HIGH_RISK")
        if t > 0.05 + 1e-9:
            reasons.append("WATCH_OVER_OBSERVE_CAP")
    elif permission == "TEST":
        if risk_level not in ("Low", "Medium") and t > 1e-9:
            reasons.append("TEST_HIGH_RISK")
        if t > 0.10 + 1e-9:
            reasons.append("TEST_OVER_EXPLORE_CAP")
    elif permission == "ALLOW":
        if t > 0.50 + 1e-9:
            reasons.append("ALLOW_OVER_TRADE_CAP")
    elif permission == "STRONG_ALLOW":
        if t > 0.70 + 1e-9:
            reasons.append("STRONG_OVER_CAP")
    return not reasons, tuple(reasons)


def finalize_target(permission, participation_mode, budget_cap, raw_target,
                    previous_position, exit_severity=0, data_quality="B",
                    regime_risk_scale=1.0, use_data_quality_gate=True,
                    portfolio_state="NORMAL", stop_distance=0.02,
                    risk_budget=None, portfolio_cap=1.0, liquidity_cap=1.0,
                    execution_cap=1.0, sector_cap=1.0, theme_cap=1.0,
                    drawdown_cap=1.0) -> dict:
    """唯一最终仓位产生点（2.7：所有非 Governance 模块只能产生 Proposal）

    Risk Target → Permission Cap → Portfolio Gate → Data Quality → Regime →
    Governance Proof → Final Target。P0-4：组合状态不仅限新仓，
    RISK_OFF/OVERHEATED 下既有仓位也触发 REDUCE 倾向（entry_cap=0 时
    target 压至 previous 的减仓档）。
    """
    from .governance_proof import prove
    from .permission_policy import PERMISSION_POSITION_CAP
    from ..portfolio.state_engine import state_constraints
    t = float(raw_target or 0.0)
    prev = float(previous_position or 0.0)
    risk_cap_val = t
    trace_steps = [("raw_target", t, t, "初始目标", "1.0")]
    # 1) Risk Budget 分配：目标仓位 = min(risk_budget / stop_distance, 其余 cap)
    if risk_budget is not None and float(stop_distance) > 0:
        risk_cap_val = float(risk_budget) / float(stop_distance)
        trace_steps.append(("risk_cap", t, min(t, risk_cap_val),
                            "RISK_LIMIT", "1.0"))
        t = min(t, risk_cap_val)
    # 2) Permission Cap（OBSERVE 例外：仅约束新增，维持 ≤ max(prev, cap)）
    if participation_mode == "OBSERVE":
        t = min(t, max(prev, float(budget_cap)))
    else:
        _before = t
        t = min(t, max(prev, float(budget_cap)))
        trace_steps.append(("budget_cap", _before, t, "PORTFOLIO_LIMIT",
                            "1.0"))
        _before = t
        t = min(t, max(prev, PERMISSION_POSITION_CAP.get(permission, 0.0)))
        trace_steps.append(
            ("permission_cap",
             _before, t,
             "PERMISSION_TEST" if permission == "TEST" else "PERMISSION_BLOCK"
             if permission == "BLOCK" else "PERMISSION_ALLOWED", "1.0"))
    # 2b) governed_target：经 Permission/Budget 上限后的中间目标
    governed = t
    # 3) Portfolio Gate（P0-4）：RISK_OFF/OVERHEATED 禁新增；DEFENSIVE/CONCENTRATED 降 Entry
    pg = state_constraints(portfolio_state)
    _before = t
    if not pg["add_allowed"] and t > prev + 1e-9:
        t = prev if prev > 0 else 0.0
        portfolio_gate_applied = True
    elif t > prev + 1e-9:
        t = min(t, max(prev, t * pg["entry_cap_scale"]))
        portfolio_gate_applied = pg["entry_cap_scale"] < 1.0
    else:
        portfolio_gate_applied = False
    trace_steps.append(("portfolio_gate", _before, t, "PORTFOLIO_LIMIT",
                        "1.0"))
    # 4) Data Quality（A 1.0 / B 0.8 / C 0.5 / D → 0）
    if use_data_quality_gate and t > 1e-9:
        _before = t
        scale = {"A": 1.0, "B": 0.8, "C": 0.5, "D": 0.0}.get(
            data_quality or "B", 0.5)
        t = round(t * scale, 4)
        if data_quality == "D":
            t = 0.0
        trace_steps.append(("data_quality", _before, t,
                            "DATA_DEGRADED" if data_quality in ("C", "D")
                            else "DATA_OK", "1.0"))
    # 5) Regime 风险上限缩放
    if float(regime_risk_scale) < 1.0 and t > 1e-9:
        _before = t
        t = round(t * float(regime_risk_scale), 4)
        trace_steps.append(("regime_cap", _before, t, "REGIME_BREAK", "1.0"))
    # 5b) 多层硬约束链（2.8/4/9）：Stock→Sector→Theme→Liquidity→
    #     Portfolio→Drawdown→Execution，全部 min 后不得突破
    # MTR Closure（Sprint C）：NaN/非法 cap → UNKNOWN → 不新增风险
    nan_caps = [name for name, cap in (
        ("portfolio", portfolio_cap), ("liquidity", liquidity_cap),
        ("execution", execution_cap), ("sector", sector_cap),
        ("theme", theme_cap), ("drawdown", drawdown_cap))
        if cap is not None and float(cap) != float(cap)]
    if nan_caps:
        trace_steps.append(("unknown_caps", t, min(t, prev),
                            f"UNKNOWN_CAPS:{','.join(nan_caps)}", "1.0"))
        t = min(t, prev)
    for cap_name, cap in (("portfolio", portfolio_cap),
                          ("liquidity", liquidity_cap),
                          ("execution", execution_cap),
                          ("sector", sector_cap),
                          ("theme", theme_cap),
                          ("drawdown", drawdown_cap)):
        c = float(cap if cap is not None else 1.0)
        if c < 1.0 - 1e-9 and t > c + 1e-9:
            trace_steps.append((f"{cap_name}_cap", t, c,
                                "PORTFOLIO_LIMIT" if cap_name == "portfolio"
                                else "LIQUIDITY_LIMIT"
                                if cap_name in ("liquidity", "execution")
                                else "PORTFOLIO_LIMIT", "1.0"))
            t = c
    # 6) Hard Exit / 数据质量 D 强制归零
    if int(exit_severity or 0) >= 3:
        trace_steps.append(("hard_exit", t, 0.0, "HARD_EXIT", "1.0"))
        t = 0.0
    # 7) Governance Proof（前置：FAIL 不得输出）
    proof = prove(
        permission, participation_mode,
        PERMISSION_POSITION_CAP.get(permission, 0.0), risk_cap_val,
        float(budget_cap), float(raw_target), t, prev,
        hard_exit=int(exit_severity or 0) >= 3, data_quality=data_quality,
        governed_target=governed, portfolio_cap=portfolio_cap,
        liquidity_cap=liquidity_cap, execution_cap=execution_cap,
        sector_cap=sector_cap, theme_cap=theme_cap,
        drawdown_cap=drawdown_cap)
    if proof.proof != "PASS":
        raise GovernanceViolation(
            f"finalize_target Proof FAIL: {proof.violations}")
    from .constraint_trace import build_constraint_trace
    constraint_trace = build_constraint_trace(trace_steps)
    return {"target": round(t, 4), "proof": proof,
            "portfolio_gate": pg,
            "portfolio_gate_applied": portfolio_gate_applied,
            "constraint_trace": constraint_trace}
