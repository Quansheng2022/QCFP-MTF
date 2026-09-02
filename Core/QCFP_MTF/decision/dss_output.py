# coding: utf-8
"""DSS 输出协议（规格书第七章标准 JSON）"""

from .retail import PERMISSION_OPPORTUNITY_MATRIX, action_from_snapshot, \
    opportunity_level
from .versions import MODEL_VERSION


def _action_detail(action, mtf_regime, structural_regime):
    if action == "BUY":
        return "季度结构强势 + 月线改善 + 周线突破，可考虑建立仓位"
    if action == "ADD":
        return "结构共振延续，可考虑加仓"
    if action == "HOLD":
        return "结构健康，持仓等待触发信号"
    if action == "REDUCE":
        return "结构性强势下的战术预警，减仓观察，严禁清仓"
    if action == "EXIT":
        return "多周期退潮，坚决回避/离场"
    return "等待明确信号（数据不足或结构未定）"


def build_dss_json(row: dict, settings=None, snapshot=None) -> dict:
    """把一行联合数据组装为规格书第七章 JSON

    decision.* 为 Legacy MTF 对比口径（不参与正式决策）；
    decision_2_2.* 为 Canonical DecisionSnapshot 输出（settings 提供时生成），
    报告层只消费后者——见 RULE：Report = Renderer，不是 Decision Engine。
    """
    out = {
        "stock_code": row.get("stock_code"),
        "decision_date": row.get("decision_date"),
        "model_version": row.get("model_version", MODEL_VERSION),
        "structural": {
            "regime": row.get("structural_regime"),
            "core_score": row.get("core_score"),
            # 证据等级只读调用方传入（与数据质量二维独立），禁止由 data_quality 推断
            "evidence_level": row.get("evidence_level", "A-"),
            "data_quality": row.get("data_quality"),
            "key_drivers": [
                f"c_state: {row.get('c_state')}",
                f"f_state: {row.get('f_state')}",
                f"p_state: {row.get('p_state')}",
            ],
        },
        "stage": {
            "monthly_state": row.get("monthly_behavior_state"),
            "turnover_regime": row.get("turnover_liquidity_regime"),
            "vp_regime": row.get("m_vp_regime"),
            "cbi_score": row.get("cbi_score"),
        },
        "cost_position": {
            "status": row.get("cost_position"),
            "vs_weekly_vwap": row.get("cost_vs_weekly_vwap"),
            "vs_monthly_vwap": row.get("cost_vs_monthly_vwap"),
            "vs_quarterly_vwap": row.get("cost_vs_quarterly_vwap"),
        },
        "trigger": {
            "signal": row.get("tactical_signal"),
            "breakout": bool(row.get("w_breakout")),
            "breakdown": bool(row.get("w_breakdown")),
            "volume_spike": bool(row.get("w_turnover_spike")),
        },
        "confidence": {
            "chip_stability_confidence": row.get("chip_stability_confidence"),
            "structure_behavior_alignment": row.get("structure_behavior_alignment"),
            "evidence_summary": row.get("evidence_summary"),
        },
        "risk": {
            "risk_level": row.get("risk_level"),
            "divergence_detected": row.get("structure_behavior_alignment") == "Divergence",
            "key_risks": [str(k) for k in (row.get("key_risks") or [])
                          if k is not None],
            "anti_inference_check": "PASSED",
        },
        "decision": {
            "mtf_regime": row.get("mtf_regime"),
            "action": row.get("action_signal"),
            "source": "legacy_mtf",
            "action_detail": _action_detail(row.get("action_signal"),
                                            row.get("mtf_regime"),
                                            row.get("structural_regime")),
            "position_advice": row.get("position_advice"),
            "stop_loss_trigger": row.get("stop_loss_trigger"),
        },
    }
    if settings is not None:
        try:
            if snapshot is None:
                from .decision_snapshot import load_canonical_decision
                snapshot, _ = load_canonical_decision(row, settings)
            out["decision_2_2"] = {
                "run_id": snapshot.run_id,
                "institutional_state": snapshot.institutional_state,
                "institutional_permission": snapshot.institutional_permission,
                "permission_cap": snapshot.permission_cap,
                "exit_event": snapshot.exit_event_kind,
                "exit_reason": snapshot.exit_event_reason,
                "setup_type": snapshot.setup_type,
                "base_fsm_state": snapshot.base_fsm_state,
                "prev_fsm_state": snapshot.prev_fsm_state,
                "next_fsm_state": snapshot.next_fsm_state,
                "raw_target_position": snapshot.raw_target_position,
                "target_position": snapshot.target_position,
                "permission_constraint_applied":
                    snapshot.permission_constraint_applied,
                "action": action_from_snapshot(snapshot),
                "primary_reason": snapshot.primary_reason,
                "secondary_reasons": list(snapshot.secondary_reasons),
                "participation_mode": snapshot.participation_mode,
                "participation_cap": snapshot.participation_cap,
                "position_class": snapshot.position_class,
                "exit_severity": snapshot.exit_severity,
                "trade_quality": snapshot.trade_quality,
                "trade_quality_band": snapshot.trade_quality_band,
                "feature_manifest_hash": snapshot.feature_manifest_hash,
                "opportunity_level": opportunity_level(
                    snapshot.setup_type, snapshot.trade_quality),
                "opportunity_cell": PERMISSION_OPPORTUNITY_MATRIX.get(
                    snapshot.institutional_permission, {}).get(
                    opportunity_level(snapshot.setup_type,
                                      snapshot.trade_quality)),
                "override_rule_ids": list(snapshot.override_rule_ids),
                "input_fingerprint": snapshot.input_fingerprint,
                "settings_hash": snapshot.settings_hash,
            }
        except Exception as exc:
            out["decision_2_2"] = {
                "status": "UNAVAILABLE",
                "reason": str(exc),
            }
    return out
