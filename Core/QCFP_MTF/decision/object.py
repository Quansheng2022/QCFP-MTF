# coding: utf-8
"""Unified Decision Object（QCFP-MTF 2.8：统一决策对象）

11 号优先修改项：Live / Backtest / Replay / Shadow / Report / Audit
全部消费同一个不可变决策对象，禁止各自拼装：

    UnifiedDecision
    ├── snapshot       DecisionSnapshot（唯一决策链输出）
    ├── wave           WaveOpportunity（波段画像）
    ├── wave_stage     波段生命周期阶段（顶层暴露）
    ├── entry_quality  EntryQuality（进场质量）
    ├── exit_quality   ExitQuality（退出质量/原因）
    ├── time_in_trade  TimeInTrade（持仓时间治理）
    ├── constraints    Permission / Participation / Portfolio / Risk 约束
    ├── governed_target 经 Permission/Risk 后的中间目标
    ├── evidence       输入指纹 / 数据快照 / PIT 分级
    ├── confidence     DecisionConfidence
    └── version_hash   模型+规则+Schema+Feature+Settings+Input 复合指纹

不变性：frozen dataclass；任何消费方不得修改历史决策。
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field


CONSUMERS = ("LIVE", "BACKTEST", "REPLAY", "SHADOW", "REPORT", "AUDIT")


def composite_hash(parts: dict) -> str:
    """复合指纹：model/rule/schema/feature/settings/input 排序后 sha256。"""
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class UnifiedDecision:
    decision_id: str
    stock_code: str
    decision_date: str
    mode: str = "REPORT"          # LIVE/BACKTEST/REPLAY/SHADOW/REPORT/AUDIT
    snapshot: dict = field(default_factory=dict)
    wave: dict = field(default_factory=dict)
    wave_stage: str = ""
    entry_quality: dict = field(default_factory=dict)
    exit_quality: dict = field(default_factory=dict)
    time_in_trade: dict = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    governed_target: float = 0.0
    evidence: dict = field(default_factory=dict)
    confidence: dict = field(default_factory=dict)
    version_hash: str = ""
    decision_hash: str = ""
    consumers: tuple = field(default_factory=tuple)
    audit_chain: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["consumers"] = list(self.consumers)
        d["audit_chain"] = list(self.audit_chain)
        return d

    def decision_hash_value(self) -> str:
        """决策内容指纹（不含 mode/consumers，保证跨模式一致）。"""
        core = {k: v for k, v in self.as_dict().items()
                if k not in ("mode", "consumers", "decision_hash")}
        raw = json.dumps(core, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_unified_decision(snap, mode="REPORT", wave=None,
                           entry_quality=None, exit_quality=None,
                           time_in_trade=None, confidence=None,
                           constraints=None, consumers=None) -> UnifiedDecision:
    """从 DecisionSnapshot（必需）+ 各质量对象（可选）聚合统一决策对象。

    约束：snap 必须是含 target_position 的快照对象/字典；
    若传入 WaveOpportunity/EntryQuality 等 dataclass，自动 as_dict。
    """
    def _d(obj):
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        return asdict(obj)

    snap_d = _d(snap)
    wave_d = _d(wave)
    eq_d = _d(entry_quality)
    xq_d = _d(exit_quality)
    tit_d = _d(time_in_trade)
    conf_d = _d(confidence) or (snap_d.get("context") or {}).get(
        "confidence") or {}
    c = constraints or {}
    if not c:
        ctx = snap_d.get("context") or {}
        part = ctx.get("participation") or {}
        c = {
            "permission": snap_d.get("institutional_permission") or "",
            "permission_cap": snap_d.get("permission_cap") or "",
            "participation_mode": snap_d.get("participation_mode") or "",
            "participation_cap": snap_d.get("participation_cap") or 0.0,
            "target_position": snap_d.get("target_position") or 0.0,
            "previous_position": snap_d.get("previous_position") or 0.0,
            "portfolio_state": ctx.get("portfolio_state") or "NORMAL",
            "risk_level": ctx.get("market_context") or "",
            "exit_severity": snap_d.get("exit_severity") or 0,
        }
    version_hash = composite_hash({
        "model": snap_d.get("model_version") or "",
        "rule": snap_d.get("rule_version") or "",
        "schema": snap_d.get("schema_version") or "",
        "feature": snap_d.get("feature_manifest_hash") or "",
        "settings": snap_d.get("settings_hash") or "",
        "input": snap_d.get("input_fingerprint") or "",
        "data_snapshot": snap_d.get("data_snapshot_id") or "",
    })
    gp = ((snap_d.get("context") or {}).get("governance_proof") or {})
    governed_target = float(gp.get("governed_target")
                            if gp.get("governed_target") is not None
                            else (constraints or {}).get("governed_target")
                            or 0.0)
    evidence = {
        "input_fingerprint": snap_d.get("input_fingerprint") or "",
        "data_snapshot_id": snap_d.get("data_snapshot_id") or "",
        "data_version": snap_d.get("data_version") or "1.0",
        "pit_grade": snap_d.get("pit_grade") or "",
        "evidence_grade": snap_d.get("evidence_grade") or "",
    }
    obj = UnifiedDecision(
        decision_id=snap_d.get("decision_id")
        or f"{snap_d.get('stock_code')}_{snap_d.get('decision_date')}",
        stock_code=snap_d.get("stock_code") or "?",
        decision_date=snap_d.get("decision_date") or "?",
        mode=mode,
        snapshot=snap_d,
        wave=wave_d,
        wave_stage=wave_d.get("stage") or "",
        entry_quality=eq_d,
        exit_quality=xq_d,
        time_in_trade=tit_d,
        constraints=c,
        governed_target=round(governed_target, 4),
        evidence=evidence,
        confidence=conf_d,
        version_hash=version_hash,
        decision_hash="",
        consumers=tuple(consumers or (mode,)),
        audit_chain=(snap_d.get("decision_path") or (),))
    # decision_hash 依赖所有字段（含 version_hash），此处二次构造
    raw = json.dumps(
        {k: v for k, v in obj.as_dict().items()
         if k not in ("mode", "consumers", "decision_hash")},
        sort_keys=True, ensure_ascii=False, default=str)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return UnifiedDecision(
        decision_id=obj.decision_id, stock_code=obj.stock_code,
        decision_date=obj.decision_date, mode=obj.mode,
        snapshot=obj.snapshot, wave=obj.wave, wave_stage=obj.wave_stage,
        entry_quality=obj.entry_quality, exit_quality=obj.exit_quality,
        time_in_trade=obj.time_in_trade, constraints=obj.constraints,
        governed_target=obj.governed_target, evidence=obj.evidence,
        confidence=obj.confidence, version_hash=obj.version_hash,
        decision_hash=h, consumers=obj.consumers,
        audit_chain=obj.audit_chain)


def validate_unified_decision(obj: UnifiedDecision, required_mode=None) -> list:
    """一致性校验：返回违规清单（空 = 通过）。
    - snapshot 必须含 target_position/decision_id
    - version_hash 必须与快照身份字段一致
    - consumers 非空
    - 指定模式时，snapshot.context.action 可消费但不得改写
    """
    violations = []
    if not obj.snapshot:
        violations.append("SNAPSHOT_MISSING")
    if "target_position" not in (obj.snapshot or {}):
        violations.append("TARGET_POSITION_MISSING")
    if not obj.decision_id:
        violations.append("DECISION_ID_MISSING")
    if not obj.consumers:
        violations.append("NO_CONSUMERS")
    if required_mode and required_mode not in obj.consumers:
        violations.append(f"MODE_{required_mode}_NOT_IN_CONSUMERS")
    recomputed = composite_hash({
        "model": (obj.snapshot or {}).get("model_version") or "",
        "rule": (obj.snapshot or {}).get("rule_version") or "",
        "schema": (obj.snapshot or {}).get("schema_version") or "",
        "feature": (obj.snapshot or {}).get("feature_manifest_hash") or "",
        "settings": (obj.snapshot or {}).get("settings_hash") or "",
        "input": (obj.snapshot or {}).get("input_fingerprint") or "",
        "data_snapshot": (obj.snapshot or {}).get("data_snapshot_id") or "",
    })
    if recomputed != obj.version_hash:
        violations.append("VERSION_HASH_MISMATCH")
    return violations
