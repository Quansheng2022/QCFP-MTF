# coding: utf-8
"""Canonical Decision Engine（QCFP-MTF 2.3：唯一决策入口）

原则：所有最终决策只允许一个入口：

    decision = engine.evaluate(evidence, previous_state, previous_position, settings)

    Backtest / Shadow / Report / Live / Audit 全部调用它（或读取 Ledger）。
    不允许任何模块直接调用 FSM + Permission + Sizing 自行拼接。

DecisionConfig 用于 Ablation（每次只改变一个模块）：
    use_permission / use_soft_exit / use_hard_exit / use_daily
"""

from dataclasses import dataclass

from ..evidence.snapshot import assert_evidence_asof
from ..market.regime import regime_scale
from .decision_snapshot import (DecisionSnapshot, _input_fingerprint,
                                _reason_codes, _settings_hash)
from .governance import GovernanceViolation, finalize_target
from .governance_proof import GovernanceProof, prove
from ..governance.conflict import resolve_conflict
from .confidence import evaluate_confidence
from .action_gate import evaluate_action
from .hard_exit import ExitEvent, evaluate_exit_events
from .institutional_permission import evaluate_institutional_permission
from .participation_budget import ParticipationBudget, \
    evaluate_participation_budget
from .retail_position_fsm import (PERMISSION_CAP, TransitionInput,
                                  apply_permission_position_cap,
                                  assert_no_risk_increase,
                                  permission_fsm_base,
                                  state_position_consistent, transition_audit)
from .retail_position_sizing import retail_target_position
from .trade_quality import evaluate_trade_quality
from .versions import (DECISION_RULE_VERSION, MODEL_VERSION, SCHEMA_VERSION,
                       feature_manifest_hash)
from ..setup.swing_setup import evaluate_swing_setup


@dataclass(frozen=True)
class DecisionConfig:
    use_permission: bool = True
    use_soft_exit: bool = True
    use_hard_exit: bool = True
    use_daily: bool = True
    use_budget: bool = True
    use_market_scale: bool = True
    use_stop: bool = True
    use_observation: bool = True
    use_data_quality_gate: bool = True
    override_permission: str = None   # 仅 Ablation（Permutation）注入用
    use_regime_params: bool = True
    use_entry_quality: bool = False   # 2.8（14 号）：进场质量门（默认关闭，
                                      # 保证与 2.7 行为一致）
    use_feature_contracts: bool = True  # 2.8（6 号）：PIT/Feature Contract
                                        # 架构门（非法未来特征 → Abort）
    use_hard_quality_gate: bool = True  # 2.8（29 号）：数据质量硬门
                                        # BLOCK → Decision Abort


def _flatten_evidence(evidence: dict) -> dict:
    """DecisionEvidenceSnapshot（分层）→ 扁平 row；普通 row 原样返回"""
    if "quarterly" not in evidence and "decision_date" in evidence:
        return dict(evidence)
    row = {k: v for k, v in evidence.items() if not isinstance(v, dict)}
    for layer in ("quarterly", "monthly", "weekly", "daily", "risk",
                  "context", "universe", "flow"):
        for k, v in (evidence.get(layer) or {}).items():
            if k == "available_at":
                continue
            row[k] = v
    return row


def _filter_exit_event(ev, config: DecisionConfig) -> ExitEvent:
    if ev.kind == "NONE":
        return ev
    if ev.kind == "STOP_EXIT":
        # Stop 独立开关（Governance Ablation：Full−Stop）
        return ev if (config.use_hard_exit and config.use_stop) \
            else ExitEvent("NONE")
    if ev.hard:
        return ev if config.use_hard_exit else ExitEvent("NONE")
    return ev if config.use_soft_exit else ExitEvent("NONE")


def evaluate(evidence, previous_state, previous_position, settings,
             config=None, rule_version=None, model_version=None, run_id="",
             decision_id=None) -> DecisionSnapshot:
    """唯一决策链：Evidence(PIT) → Institutional → Exit → Setup → FSM →
    Sizing → Permission Cap → DecisionSnapshot"""
    cfg = config or DecisionConfig()
    rule_version = rule_version or DECISION_RULE_VERSION
    model_version = model_version or MODEL_VERSION
    row = _flatten_evidence(dict(evidence))
    # 2.8（29 号）：数据质量硬门禁——BLOCK 不允许产生 Trade Decision
    if cfg.use_hard_quality_gate:
        from ..data.quality import assert_data_quality_gate
        dq_checks = row.get("data_quality_checks") or {}
        if row.get("data_quality_gate") == "BLOCK" or dq_checks:
            assert_data_quality_gate(dq_checks)
    # 2.8（6 号）：Feature Contract 硬门——决策层出现非法/未来特征即中止
    if cfg.use_feature_contracts:
        from ..data.feature_contract import assert_decision_layer_features
        assert_decision_layer_features(
            {k: v for k, v in row.items() if v is not None},
            decision_time=row.get("decision_date"))
    # 0) PIT Evidence Contract（所有输入可用时间 <= 决策日）
    from ..evidence.snapshot import build_evidence_snapshot, grade_evidence
    ev_snap = build_evidence_snapshot(row)
    assert_evidence_asof(ev_snap)
    pit_grade, evidence_grade, grade_reasons = grade_evidence(row, settings)
    # 1) Institutional
    inst = evaluate_institutional_permission(
        c_state=row.get("c_state"), f_state=row.get("f_state"),
        p_state=row.get("p_state"),
        persistence=2 if row.get("f_state") == "F↑"
        and row.get("prev_f_state") == "F↑"
        else 1 if row.get("f_state") == "F↑" else 0,
        divergence=row.get("structure_behavior_alignment") == "Divergence",
        confidence=row.get("chip_stability_confidence") or "Medium",
        data_quality=row.get("data_quality") or "B", settings=settings)
    permission = inst.permission if cfg.use_permission else "STRONG_ALLOW"
    if cfg.override_permission:
        permission = cfg.override_permission
    # 2) Exit Events（按实验配置裁剪）
    ev = evaluate_exit_events(
        des_score=row.get("des_score") or 0,
        weekly_signal=row.get("tactical_signal"),
        stop_triggered=row.get("stop_triggered"),
        risk_level=row.get("risk_level"),
        current_position=previous_position, settings=settings)
    ev = _filter_exit_event(ev, cfg)
    # 3) Setup（Daily 关闭时中性化日线输入）
    daily_state = row.get("daily_state") if cfg.use_daily \
        else "DAILY_NEUTRAL"
    setup = evaluate_swing_setup(
        weekly_signal=row.get("tactical_signal"),
        daily_state=daily_state,
        monthly_state=row.get("monthly_behavior_state"),
        permission=permission)
    # 3b) Participation Budget（四层架构中间层）
    if cfg.use_budget:
        budget = evaluate_participation_budget(
            permission,
            market_context=row.get("market_context")
            if cfg.use_market_scale else None,
            risk_level=row.get("risk_level"), setup_type=setup,
            settings=settings, allow_observation=cfg.use_observation)
    else:
        if permission in ("ALLOW", "STRONG_ALLOW"):
            budget = ParticipationBudget("TRADE", 1.0, "budget_disabled")
        elif permission == "TEST":
            budget = ParticipationBudget("EXPLORE", 1.0, "budget_disabled")
        else:
            budget = ParticipationBudget("STAND", 0.0, "budget_disabled")
    # 3c) Market Regime（as-of）：优先 row.market_regime，否则由 market_context 映射
    regime = row.get("market_regime") or \
        {"risk_on": "Bull", "neutral": "Sideway", "risk_off": "Bear"}.get(
            row.get("market_context")) or "Sideway"
    # 3d) Wave Opportunity Evaluation（OPPORTUNITY Authority — 先于 FSM/Lifecycle）
    # Frozen Spec: INPUT → PERMISSION → OPPORTUNITY → LIFECYCLE → GOVERNANCE …
    # Wave 的“机会判定”（stage / allowed / max_entry_scale）必须先于 Lifecycle；
    # 之后只允许消费该机会结果，不允许在 LIFECYCLE 之后重新形成机会决策。
    # V1.3（P0 修复）：真实 ProposalAction 只有 FSM/Sizing 后才能知道，
    # 不得用 previous_position 预判未来 Action（prev>0 → HOLD）后拿假 HOLD
    # 查询 Wave policy。这里在 FSM 前完成单次 OPPORTUNITY authority 评估
    # （wave_to_canonical，保持 Frozen F01 一级证据的 token 精确比对），并
    # 用同一 Wave package 的 wave_stage_gate 展开全部 action 的 immutable
    # policy 事实（stage/permission/previous_position 均已知）；FSM 后按
    # 真实 ProposalAction 只做 lookup/apply，绝不重新评估 wave_stage/permission。
    wave_policy = None
    if row.get("wave_stage"):
        from ..wave.canonical import wave_to_canonical, wave_stage_gate
        ref = float(previous_position or 0.0)
        wave_opportunity = wave_to_canonical(
            row.get("wave_stage"), permission, ref, ref,
            proposed_action="ENTRY")
        pol = wave_opportunity["permission_policy"]
        stage = row.get("wave_stage")
        wave_policy = {}
        for act in ("ENTRY", "ADD", "HOLD", "REDUCE", "EXIT", "NO_TRADE"):
            gate = wave_stage_gate(stage, act)
            allowed = bool(gate["allowed"])
            reasons = []
            if not allowed:
                reasons.append(f"WAVE_STAGE_{stage}_BLOCKS_{act}")
            if not pol["new_risk_allowed"] and act in ("ENTRY", "ADD"):
                allowed = False
                reasons.append(f"PERMISSION_{permission}_BLOCKS_NEW_RISK")
            wave_policy[act] = {
                "stage": stage,
                "action": act,
                "allowed": allowed,
                "max_entry_scale": float(gate["max_entry_scale"]),
                "proposed_target": round(ref, 4),
                "permission_policy": pol,
                "blocked_reason": "; ".join(reasons),
            }
    # 4) FSM（矩阵基准 + 覆盖）
    t_input = TransitionInput(
        permission=permission, exit_event=ev, setup_type=setup,
        risk_level=row.get("risk_level") or "Medium",
        weekly_signal=row.get("tactical_signal") or "Consolidation",
        daily_state=daily_state,
        monthly_state=row.get("monthly_behavior_state") or "Stable",
        previous_state=previous_state,
        previous_position=float(previous_position or 0.0),
        chase_filter=bool(row.get("chase_filter")),
        cooldown_remaining=int(row.get("cooldown_remaining") or 0),
        participation_mode=budget.mode)
    nxt, rule_ids = transition_audit(t_input)
    base_state = permission_fsm_base(permission, previous_state)
    conflict = resolve_conflict(
        ev.kind, row.get("risk_level") or "Medium", permission, nxt,
        wave_strength=row.get("wave_strength"),
        setup_type=setup, daily_state=daily_state)
    # 5) Sizing + 状态-仓位一致性
    raw_target = retail_target_position(nxt, previous_position, settings)
    fsm_proposal_target = float(raw_target)   # 新 3 号：FSM Proposal 冻结
    # 5b) 消费已计算的 Wave policy 矩阵：真实 ProposalAction 由
    #     previous_position vs fsm_proposal_target 派生，再从 FSM 前
    #     预计算的 immutable policy 中选择对应分支（lookup/apply，
    #     不是 re-evaluate，禁止 FSM 后重新解释 wave_stage / permission）。
    wave_obj = None
    if wave_policy is not None:
        from .action_classifier import proposal_action
        wave_action = proposal_action(
            float(previous_position or 0.0), fsm_proposal_target)
        selected = wave_policy[wave_action]
        prev = float(previous_position or 0.0)
        if wave_action in ("ENTRY", "ADD"):
            if not selected["allowed"]:
                # Wave 门拒绝新增风险：不得新增风险，只能维持/降低
                # （禁止 ADD ≠ 强制 EXIT——不得把已有仓位乘成 0）
                wave_target = min(fsm_proposal_target, prev)
            else:
                # Wave 允许新增：按 max_entry_scale / permission 做确定性封顶
                scale = float(selected.get("max_entry_scale") or 0.0)
                wave_target = min(
                    fsm_proposal_target * scale,
                    float((selected.get("permission_policy") or {})
                          .get("max_target", 1.0)))
        elif wave_action == "NO_TRADE":
            wave_target = 0.0
        elif wave_action == "HOLD":
            # HOLD：维持既有仓位。Wave 不得制造 ADD，也不得用
            # permission max_target（增量风险上限）制造无理由 REDUCE/EXIT。
            wave_target = min(fsm_proposal_target, prev)
        elif wave_action == "REDUCE":
            # REDUCE：已经在降低风险（progressive derisk）。BLOCK.max_target=0
            # 是“禁止新增风险”的增量上限，不是“已有仓位绝对归零”上限；
            # 无独立 Immediate Exit Authority（Hard/Stop/Risk Exit）时，
            # Wave 不得把 REDUCE 升级成 EXIT。
            wave_target = min(fsm_proposal_target, prev)
        else:
            # EXIT：上游（Hard/Risk/Stop Exit 或 FSM）已授权退出，
            # Wave 不得阻止退出。
            wave_target = 0.0
        raw_target = wave_target
        wave_obj = dict(selected)
        wave_obj["proposed_target"] = round(float(raw_target), 4)
    nxt = state_position_consistent(nxt, raw_target)
    # 新 3 号：Wave 之后禁止再次调用 sizing 覆盖 WaveProposalTarget
    target = float(raw_target)
    # 6) Trade Quality（Proposal 级门：允许交易 ≠ 值得交易）
    tqs, tqs_band = evaluate_trade_quality(
        setup_type=setup, permission=permission,
        market_context=row.get("market_context"),
        c_state=row.get("c_state"), f_state=row.get("f_state"),
        p_state=row.get("p_state"), q_trend_score=row.get("q_trend_score"),
        q_position_52w=row.get("q_position_52w"),
        cbi_state=row.get("cbi_state"),
        catalyst_score=row.get("catalyst_score"),
        risk_level=row.get("risk_level"), des_score=row.get("des_score"))
    if cfg.use_regime_params:
        tqs += {"Bull": 4, "Sideway": 0, "Bear": -3,
                "HighVolatility": -4, "Crisis": -6}.get(regime, 0)
    from ..config.settings import retail_settings
    min_tradable = float(retail_settings(settings).get(
        "trade_quality", {}).get("min_tradable", 40))
    tqs_gated = False
    if cfg.use_permission and float(target) > 1e-9 \
            and tqs < min_tradable:
        target = 0.0
        tqs_gated = True
    dq = row.get("data_quality") or "B"
    # 6b) 唯一最终仓位产生点（Governance Hard Boundary：
    #      仅 governance.finalize_target 可产生最终仓位；其余模块只产生 Proposal）
    constraint_applied = tqs_gated
    if cfg.use_permission:
        from ..decision.stop_loss import stop_loss_buffer_pct
        from .governance_caps import caps_from_row
        risk_budget = retail_settings(settings).get(
            "position", {}).get("risk_budget") or None
        caps = caps_from_row(row)
        # 新 5 号：Production/Research Validation 缺 REQUIRED cap → 不新增风险
        from .governance_caps import caps_governance_check
        backtest_mode = (settings or {}).get("backtest", {}).get(
            "mode", "research_exploration")
        caps_check = caps_governance_check(row, mode=backtest_mode)
        if caps_check.get("unknown"):
            # PWC-1（第 7 项）：UNKNOWN Caps → No-New-Risk——
            # 空仓保持 0；已持仓允许维持/减仓；UNKNOWN 不制造市场退出。
            target = min(float(target),
                         float(previous_position or 0.0))
        fin = finalize_target(
            permission, budget.mode, budget.cap, target, previous_position,
            exit_severity=ev.severity, data_quality=dq,
            regime_risk_scale=(regime_scale(regime, settings, "risk_cap")
                               if cfg.use_regime_params else 1.0),
            use_data_quality_gate=cfg.use_data_quality_gate,
            portfolio_state=row.get("portfolio_state") or "NORMAL",
            stop_distance=stop_loss_buffer_pct(settings),
            risk_budget=risk_budget, **caps.to_kwargs())
        target = fin["target"]
        proof = fin["proof"]
        constraint_applied = constraint_applied or \
            abs(float(target) - float(proof.raw_target)) > 1e-9 or \
            fin["portfolio_gate_applied"]
        # P0-A（新 2 号）：BindingConstraint + ConstraintTrace 进入 Snapshot
        from .constraint_trace import binding_constraint
        binding = binding_constraint(fin["constraint_trace"])
        binding_constraint_name = binding.get("binding_constraint") \
            if isinstance(binding, dict) else binding
        trace = fin["constraint_trace"]
        caps_used = caps.all_caps()
    else:
        from .governance_proof import prove as _prove
        proof = _prove(
            permission, budget.mode, 1.0, 1.0, 1.0, float(raw_target),
            float(target), float(previous_position or 0.0), False, dq,
            governed_target=float(target))
        binding_constraint_name = ""
        trace = {}
        caps_used = {}
    if proof.proof != "PASS":
        from .governance import GovernanceViolation
        raise GovernanceViolation(
            f"engine: GovernanceProof FAIL {proof.violations}")
    confidence = evaluate_confidence(
        inst.state, permission, setup, row.get("risk_level"), dq, pit_grade,
        ev.severity)
    # 2.8（14 号）：进场质量门（use_entry_quality=True 时启用）
    entry_quality_obj = None
    if cfg.use_entry_quality:
        from .entry_quality import evaluate_entry_quality
        entry_quality_obj = evaluate_entry_quality(
            price_position_52w=row.get("q_position_52w"),
            confirmation=0.6 if setup not in (None, "NONE") else 0.3,
            volume_confirmation=row.get("weekly_volume_ratio"),
            weekly_volatility=row.get("weekly_volatility"),
            invalidation_distance=row.get("entry_invalidation_dist"),
            expected_mfe=row.get("expected_mfe"),
            expected_mae=row.get("expected_mae"),
            execution_cost=row.get("execution_cost"))
    action, action_reasons = evaluate_action(
        permission, nxt, setup, row.get("risk_level"), previous_position,
        budget.cap, hard_exit=ev.severity >= 3,
        entry_quality=entry_quality_obj,
        wave_strength=row.get("wave_strength"))
    # 2.8（15/16 号）：退出质量 / 持仓时间作为诊断输出（不改最终决策）
    from .exit_quality import evaluate_exit_quality
    exit_quality_obj = evaluate_exit_quality(
        profit_take_hit=bool(row.get("profit_take_hit")),
        trailing_stop_hit=bool(row.get("trailing_stop_hit")),
        stop_loss_hit=bool(row.get("stop_triggered")),
        des_score=int(row.get("des_score") or 0),
        signal_weakened=row.get("tactical_signal") in ("Breakdown", "Weaken"),
        time_exit=bool(row.get("time_exit")),
        regime_bearish=regime == "Bear",
        regime_crisis=regime == "Crisis",
        permission_downgraded=inst.downgraded,
        portfolio_risk_off=(row.get("portfolio_state") or "NORMAL")
        in ("RISK_OFF", "OVERHEATED"),
        hard_exit=ev.severity >= 3,
        max_severity_input=ev.severity)
    time_in_trade_obj = None
    if row.get("entry_date"):
        from .time_in_trade import evaluate_time_in_trade
        time_in_trade_obj = evaluate_time_in_trade(
            entry_date=row.get("entry_date"),
            decision_date=row.get("decision_date"),
            expected_holding_days=int(row.get("expected_holding_days") or 45),
            max_holding_days=int(row.get("max_holding_days") or 90),
            last_confirmation_date=row.get("last_confirmation_date"),
            progress_since_entry=row.get("progress_since_entry"))
    # 7) 原因码 / 审计身份
    primary_reason, secondary_reasons = _reason_codes(
        row, inst, ev, setup, previous_state, nxt, constraint_applied)
    if tqs_gated:
        primary_reason = "TRADE_QUALITY_LOW"
        secondary_reasons = tuple(
            dict.fromkeys(list(secondary_reasons) + [f"TQS_{tqs_band}"]))
    elif not cfg.use_permission and primary_reason == "NONE" \
            and nxt == previous_state:
        primary_reason = "CONFIG_OVERRIDE"
    position_class = ("OBSERVATION" if budget.mode == "OBSERVE"
                      and float(target) > 1e-9
                      else "RISK_BEARING" if float(target) > 1e-9 else "NONE")
    from .path_hash import decision_path_hash
    # PWC-1（第 1 项）：CanonicalAction 必须先于 PathHash 生成——
    # PathHash 必须覆盖最终材料状态（FinalTarget/Wave/Action/Release）。
    from .canonical_action import canonical_action
    canonical_action_val = canonical_action(previous_position, target)
    from .canonical_action import wave_proposal_monotonic
    monotonic = wave_proposal_monotonic(
        fsm_proposal_target,
        float(wave_obj.get("proposed_target") or 0.0)
        if wave_obj is not None else fsm_proposal_target,
        float(target))
    release_context = row.get("release_context") or {}
    release_id = release_context.get("release_id") or ""
    release_manifest_hash = release_context.get(
        "release_manifest_hash") or ""
    evidence_pack_hash = release_context.get("evidence_pack_hash") or ""
    production_manifest_hash = release_context.get(
        "production_manifest_hash") or ""
    data_snapshot_id = release_context.get("data_snapshot_id") or ""
    universe_snapshot_id = release_context.get("universe_snapshot_id") or ""
    path = ("evidence", "institutional", "exit_events", "setup",
            "participation_budget", "wave", "fsm", "sizing",
            "permission_cap", "trade_quality", "governance", "final_target")
    # PWC-1：Decision 参与能力清单（Participating Manifest）
    from ..governance.production_feature_manifest import \
        decision_participating_manifest
    _path_snap = type("_P", (), {"decision_path": path})()
    participating = decision_participating_manifest(_path_snap)
    participating_feature_hash = participating["participating_hash"]
    path_hash_input = {
        "input_fingerprint": _input_fingerprint(
            row, previous_state, previous_position, rule_version,
            model_version),
        "institutional_permission": permission,
        "wave_id": row.get("wave_id") or "",
        "wave_stage": row.get("wave_stage") or "",
        "wave_strength": float(row.get("wave_strength") or 0.0),
        "fsm_proposal_target": round(float(fsm_proposal_target), 4),
        "wave_proposal_target": float(
            wave_obj.get("proposed_target") or 0.0)
        if wave_obj is not None else float(fsm_proposal_target),
        "next_fsm_state": nxt,
        "governance_caps": caps_used,
        "binding_constraint": binding_constraint_name,
        "final_target": round(float(target), 4),
        "canonical_action": canonical_action_val,
        "model_version": model_version,
        "rule_version": rule_version,
        "schema_version": SCHEMA_VERSION,
        "release_id": release_id,
        "release_manifest_hash": release_manifest_hash,
        "evidence_pack_hash": evidence_pack_hash,
        "data_snapshot_id": data_snapshot_id,
        "universe_snapshot_id": universe_snapshot_id,
        "participating_feature_hash": participating_feature_hash,
    }
    path_hash_val = decision_path_hash(path_hash_input)
    return DecisionSnapshot(
        decision_id=decision_id or
        f"{row.get('stock_code')}_{row.get('decision_date')}",
        stock_code=row.get("stock_code") or "?",
        decision_date=row.get("decision_date") or "?",
        institutional_state=inst.state,
        institutional_permission=permission,
        permission_cap=PERMISSION_CAP.get(permission, "FLAT"),
        exit_event_kind=ev.kind, exit_event_reason=ev.reason or "",
        setup_type=setup,
        prev_fsm_state=previous_state, next_fsm_state=nxt,
        previous_position=round(float(previous_position or 0.0), 4),
        target_position=round(float(target), 4),
        decision_path=path, rule_version=rule_version,
        model_version=model_version,
        schema_version=SCHEMA_VERSION,
        base_fsm_state=base_state,
        raw_target_position=round(float(raw_target), 4),
        permission_constraint_applied=constraint_applied,
        override_rule_ids=rule_ids,
        input_fingerprint=_input_fingerprint(row, previous_state,
                                             previous_position, rule_version,
                                             model_version),
        settings_hash=_settings_hash(settings),
        institutional_pressure=int(inst.pressure),
        institutional_persistence=int(inst.persistence),
        institutional_reasons=tuple(inst.reasons),
        context={"structural_regime": row.get("structural_regime"),
                 "mtf_regime": row.get("mtf_regime"),
                 "market_context": row.get("market_context"),
                 "market_regime": regime,
                 "daily_trigger": daily_state,
                 "data_quality": row.get("data_quality"),
                 "participation": {"mode": budget.mode,
                                   "cap": round(float(budget.cap), 4),
                                   "reason": budget.reason},
                 "position_class": position_class,
                 "pit_grade": pit_grade,
                 "evidence_grade": evidence_grade,
                 "grade_reasons": grade_reasons,
                 "trace": {"institutional": tuple(inst.reasons) or ("base",),
                           "exit": ev.kind,
                           "setup": setup,
                           "participation": budget.mode,
                           "fsm": tuple(rule_ids),
                           "sizing_raw": round(float(raw_target), 4),
                           "permission_cap": round(float(target), 4),
                           "trade_quality": tqs,
                           "governance": "PASSED"},
                 "governance_proof": proof.as_dict(),
                 "conflict": conflict,
                 "confidence": confidence.as_dict(),
                 "action": action,
                 "action_reasons": action_reasons,
                 "decision_path_hash": path_hash_val,
                 "quality": {
                     "entry_quality":
                         entry_quality_obj.as_dict()
                         if entry_quality_obj is not None else None,
                     "exit_quality": exit_quality_obj.as_dict(),
                     "time_in_trade":
                         time_in_trade_obj.as_dict()
                         if time_in_trade_obj is not None else None,
                 },
                 "config": {"permission": cfg.use_permission,
                            "soft_exit": cfg.use_soft_exit,
                            "hard_exit": cfg.use_hard_exit,
                            "daily": cfg.use_daily,
                            "budget": cfg.use_budget},
                 "wave": wave_obj if wave_obj is not None else None,
                 "constraint_trace": trace,
                 "governance_caps": caps_used},
        primary_reason=primary_reason,
        secondary_reasons=secondary_reasons,
        run_id=run_id,
        participation_mode=budget.mode,
        participation_cap=round(float(budget.cap), 4),
        position_class=position_class,
        exit_severity=ev.severity,
        feature_manifest_hash=feature_manifest_hash(),
        trade_quality=tqs,
        trade_quality_band=tqs_band,
        pit_grade=pit_grade,
        evidence_grade=evidence_grade,
        binding_constraint=binding_constraint_name,
        constraint_trace=trace,
        governance_caps=caps_used,
        wave_id=row.get("wave_id") or "",
        wave_stage=row.get("wave_stage") or "",
        wave_strength=float(row.get("wave_strength") or 0.0),
        wave_action_allowed=bool(
            wave_obj.get("allowed")) if wave_obj is not None else False,
        wave_entry_scale=float(
            wave_obj.get("max_entry_scale")
            or 0.0) if wave_obj is not None else 0.0,
        wave_invalidation=row.get("wave_invalidation") or "",
        wave_proposal_target=float(
            wave_obj.get("proposed_target")
            or 0.0) if wave_obj is not None else 0.0,
        fsm_proposal_target=round(float(fsm_proposal_target), 4),
        canonical_action=canonical_action_val,
        release_id=release_id,
        release_manifest_hash=release_manifest_hash,
        evidence_pack_hash=evidence_pack_hash,
        data_snapshot_id=data_snapshot_id,
        universe_snapshot_id=universe_snapshot_id,
        production_manifest_hash=production_manifest_hash,
        participating_feature_hash=participating_feature_hash)
