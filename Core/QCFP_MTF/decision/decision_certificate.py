# coding: utf-8
"""Decision Certificate（QCFP-MTF 2.6：可审计决策证书）

把 DecisionSnapshot 固化为"可解释、可重建、可哈希"的证书：
    同样的输入 + 同样版本 + 同样的 previous state
    → 相同的 Decision Certificate → 相同的 certificate_hash

Certificate 是快照的投影（不再携带非审计字段），供 Report / Audit /
Replay / Live Shadow 统一消费。
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class DecisionCertificate:
    decision_id: str
    timestamp: str
    symbol: str
    institutional_state: str
    institutional_permission: str
    setup: str
    trigger: str
    trade_quality: float
    risk_level: str
    hard_exit: bool
    previous_fsm: str
    next_fsm: str
    previous_position: float
    raw_target: float
    governed_target: float
    final_target: float
    reason_codes: tuple
    decision_path: tuple
    model_version: str
    rule_version: str
    schema_version: str
    feature_manifest_hash: str
    settings_hash: str
    input_fingerprint: str
    governance_passed: bool
    constraint_trace: dict = None
    decision_graph: tuple = ()
    authority_chain: tuple = ()
    information_asof: str = ""
    data_quality_gate: str = ""
    pit_gate: str = ""
    ablation_mode: str = ""
    execution_assumption: str = "T+1 周收盘确认成交（Next Close，BASE 全额）"
    action: str = ""
    confidence_score: float = 0.0
    decision_date: str = ""          # 2.8：决策日（ReplayCert 投影需要）
    exit_event: str = ""             # 2.8：退出事件（ReplayCert 投影需要）
    participation_mode: str = ""     # 2.8：参与模式（ReplayCert 投影需要）
    participation_cap: float = 0.0   # 2.8：参与上限（ReplayCert 投影需要）

    def certificate_hash(self) -> str:
        raw = json.dumps(
            {k: (list(v) if isinstance(v, tuple) else v)
             for k, v in asdict(self).items()},
            sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reason_codes"] = list(self.reason_codes)
        d["decision_path"] = list(self.decision_path)
        d["decision_graph"] = list(self.decision_graph)
        d["authority_chain"] = list(self.authority_chain)
        d["constraint_chain"] = [
            f"{k}={v}" for k, v in (self.constraint_trace or {}).items()]
        d["certificate_hash"] = self.certificate_hash()
        return d


def build_certificate(snap, timestamp=None) -> DecisionCertificate:
    """DecisionSnapshot → DecisionCertificate（governance_passed 由
    Governance Proof 计算，禁止调用方设置；引擎内违规即抛错）"""
    raw_target = float(snap.raw_target_position or 0.0)
    final_target = float(snap.target_position or 0.0)
    permission_cap = float(snap.participation_cap or 0.0) \
        if snap.participation_mode in ("OBSERVE", "EXPLORE", "TRADE") \
        else 0.0
    constraint_trace = {
        "raw_target": round(raw_target, 4),
        "permission_cap": round(permission_cap, 4),
        "risk_cap": 0.0,
        "hard_exit": 0.0,
        "final_target": round(final_target, 4),
        "constraint_applied": bool(snap.permission_constraint_applied),
    }
    graph = (
        f"{snap.context.get('structural_regime') or '?'}"
        f"（C:{snap.institutional_state}）",
        f"Permission:{snap.institutional_permission}",
        f"Setup:{snap.setup_type or 'NONE'}",
        f"Exit:{snap.exit_event_kind}",
        f"FSM:{snap.prev_fsm_state}→{snap.next_fsm_state}",
        f"Target:{final_target}",
    )
    cfg = snap.context.get("config", {})
    authority_chain = (
        f"State:{snap.institutional_state}",
        f"Permission:{snap.institutional_permission}",
        f"Participation:{snap.participation_mode}"
        f"(cap {snap.participation_cap})",
    )
    return DecisionCertificate(
        decision_id=snap.decision_id,
        timestamp=timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        symbol=snap.stock_code,
        decision_date=snap.decision_date,
        institutional_state=snap.institutional_state,
        institutional_permission=snap.institutional_permission,
        setup=snap.setup_type or "",
        trigger=snap.context.get("daily_trigger", "") or "",
        exit_event=snap.exit_event_kind,
        trade_quality=float(snap.trade_quality or 0.0),
        risk_level=snap.context.get("market_context", "") or "",
        hard_exit=snap.exit_severity >= 3,
        previous_fsm=snap.prev_fsm_state,
        next_fsm=snap.next_fsm_state,
        previous_position=float(snap.previous_position or 0.0),
        raw_target=float(snap.raw_target_position or 0.0),
        governed_target=float(snap.target_position or 0.0),
        final_target=float(snap.target_position or 0.0),
        participation_mode=snap.participation_mode,
        participation_cap=float(snap.participation_cap or 0.0),
        reason_codes=(snap.primary_reason,) + tuple(snap.secondary_reasons),
        decision_path=tuple(snap.decision_path),
        model_version=snap.model_version,
        rule_version=snap.rule_version,
        schema_version=snap.schema_version,
        feature_manifest_hash=snap.feature_manifest_hash,
        settings_hash=snap.settings_hash,
        input_fingerprint=snap.input_fingerprint,
        governance_passed=(
            (snap.context.get("governance_proof") or {}).get("proof")
            == "PASS"),
        constraint_trace=constraint_trace,
        decision_graph=graph,
        authority_chain=authority_chain,
        information_asof=snap.decision_date,
        data_quality_gate=snap.context.get("data_quality") or "C",
        pit_gate=snap.pit_grade or "C",
        ablation_mode=f"perm={cfg.get('permission')},"
                      f"budget={cfg.get('budget')},"
                      f"daily={cfg.get('daily')},"
                      f"hard_exit={cfg.get('hard_exit')}",
        action=snap.context.get("action", ""),
        confidence_score=float(
            snap.context.get("confidence", {}).get("score") or 0.0),
    )


def serialize_certificate(cert: DecisionCertificate) -> str:
    return json.dumps(cert.as_dict(), ensure_ascii=False, indent=2, default=str)


def certificate_from_dict(d: dict) -> DecisionCertificate:
    return DecisionCertificate(
        decision_id=d["decision_id"], timestamp=d["timestamp"],
        symbol=d["symbol"], institutional_state=d["institutional_state"],
        institutional_permission=d["institutional_permission"],
        setup=d["setup"], trigger=d["trigger"],
        trade_quality=float(d["trade_quality"]),
        risk_level=d["risk_level"], hard_exit=bool(d["hard_exit"]),
        previous_fsm=d["previous_fsm"], next_fsm=d["next_fsm"],
        previous_position=float(d["previous_position"]),
        raw_target=float(d["raw_target"]),
        governed_target=float(d["governed_target"]),
        final_target=float(d["final_target"]),
        reason_codes=tuple(d["reason_codes"]),
        decision_path=tuple(d["decision_path"]),
        model_version=d["model_version"], rule_version=d["rule_version"],
        schema_version=d["schema_version"],
        feature_manifest_hash=d["feature_manifest_hash"],
        settings_hash=d["settings_hash"],
        input_fingerprint=d["input_fingerprint"],
        governance_passed=bool(d["governance_passed"]),
        constraint_trace=dict(d.get("constraint_trace") or {}),
        decision_graph=tuple(d.get("decision_graph") or ()),
        authority_chain=tuple(d.get("authority_chain") or ()),
        information_asof=d.get("information_asof", ""),
        data_quality_gate=d.get("data_quality_gate", ""),
        pit_gate=d.get("pit_gate", ""),
        ablation_mode=d.get("ablation_mode", ""),
        execution_assumption=d.get("execution_assumption",
                                   "T+1 周收盘确认成交"),
        action=d.get("action", ""),
        confidence_score=float(d.get("confidence_score") or 0.0),
        decision_date=d.get("decision_date", ""),
        exit_event=d.get("exit_event", ""),
        participation_mode=d.get("participation_mode", ""),
        participation_cap=float(d.get("participation_cap") or 0.0))


def certificate_from_json(text: str) -> DecisionCertificate:
    return certificate_from_dict(json.loads(text))
