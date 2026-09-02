# coding: utf-8
"""Canonical Decision Snapshot（唯一决策链输出）

所有 action / card / report / shadow 都从本对象派生，禁止各模块各自作为最终决策源：
    Raw Evidence → Institutional → Exit Events → Setup → FSM → Sizing → Target
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .versions import (DECISION_RULE_VERSION, MODEL_VERSION, SCHEMA_VERSION,
                       feature_manifest_hash)


class LedgerRequiredError(RuntimeError):
    """正式模式（research_validation / production / audit）下，
    报告/审计禁止 FLAT/0 单点重算——必须存在 Decision Ledger 记录。"""


@dataclass(frozen=True)
class DecisionSnapshot:
    decision_id: str
    stock_code: str
    decision_date: str
    institutional_state: str
    institutional_permission: str
    permission_cap: str
    exit_event_kind: str
    exit_event_reason: str
    setup_type: str
    prev_fsm_state: str
    next_fsm_state: str
    previous_position: float
    target_position: float
    decision_path: tuple = field(default_factory=tuple)
    rule_version: str = DECISION_RULE_VERSION
    model_version: str = MODEL_VERSION
    schema_version: str = SCHEMA_VERSION
    base_fsm_state: str = ""
    raw_target_position: float = 0.0
    permission_constraint_applied: bool = False
    override_rule_ids: tuple = field(default_factory=tuple)
    input_fingerprint: str = ""
    settings_hash: str = ""
    institutional_pressure: int = 0
    institutional_persistence: int = 0
    institutional_reasons: tuple = field(default_factory=tuple)
    context: dict = field(default_factory=dict)
    primary_reason: str = ""
    secondary_reasons: tuple = field(default_factory=tuple)
    run_id: str = ""
    participation_mode: str = ""
    participation_cap: float = 0.0
    position_class: str = ""
    exit_severity: int = 0
    feature_manifest_hash: str = ""
    trade_quality: float = 0.0
    trade_quality_band: str = ""
    pit_grade: str = ""
    evidence_grade: str = ""
    data_snapshot_id: str = ""
    data_version: str = "1.0"
    # P0-A（新 2 号）：Hard Caps 约束链与绑定约束
    binding_constraint: str = ""
    constraint_trace: dict = field(default_factory=dict)
    governance_caps: dict = field(default_factory=dict)
    # P0-B（新 5 号）：Wave 机会核心字段（future-aware 字段永不进入）
    wave_id: str = ""
    wave_stage: str = ""
    wave_strength: float = 0.0
    wave_action_allowed: bool = False
    wave_entry_scale: float = 0.0
    wave_invalidation: str = ""
    wave_proposal_target: float = 0.0
    # Convergence：FSM Proposal 冻结 + CanonicalAction（Execution Intent）
    fsm_proposal_target: float = 0.0
    canonical_action: str = ""
    # Release 2（新 12 号）：身份链
    release_id: str = ""
    release_manifest_hash: str = ""
    evidence_pack_hash: str = ""
    universe_snapshot_id: str = ""
    production_manifest_hash: str = ""
    participating_feature_hash: str = ""

    def as_dict(self) -> dict:
        out = {k: (list(v) if k in ("decision_path", "override_rule_ids",
                                    "institutional_reasons") else v)
               for k, v in self.__dict__.items()}
        return out


def _input_fingerprint(row, prev_state, prev_pos, rule_version,
                       model_version) -> str:
    keys = ("stock_code", "decision_date", "c_state", "f_state", "p_state",
            "prev_f_state", "tactical_signal", "daily_state",
            "monthly_behavior_state", "risk_level", "des_score",
            "stop_triggered", "chase_filter", "chip_stability_confidence",
            "data_quality", "structure_behavior_alignment", "q_position_52w",
            "cooldown_remaining")
    payload = {k: row.get(k) for k in keys}
    payload.update({"prev_fsm_state": prev_state,
                    "previous_position": prev_pos,
                    "rule_version": rule_version,
                    "model_version": model_version})
    raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _settings_hash(settings) -> str:
    try:
        raw = json.dumps(settings, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    except Exception:
        return ""


def _reason_codes(row, inst, ev, setup, prev_state, nxt,
                  constraint_applied) -> tuple:
    """决策原因码（primary + secondary），让"拒绝/限制"可解释"""
    primary, secondary = "NONE", []
    if ev.kind in ("HARD_EXIT", "STOP_EXIT", "FORCED_DELEVERAGE"):
        primary = ev.kind
    elif ev.kind == "RISK_EXIT":
        primary = "RISK_EXIT"
    elif ev.kind == "BREAKDOWN":
        primary = "BREAKDOWN"
    elif inst.permission == "BLOCK":
        primary = "PERMISSION_BLOCK"
    elif nxt == "COOLDOWN":
        primary = "COOLDOWN"
    elif nxt == "FLAT" and prev_state == "FLAT":
        primary = "SETUP_ABSENT" if setup in (None, "NONE") \
            else "DAILY_TRIGGER_ABSENT"
    elif constraint_applied:
        primary = "POSITION_CAP"
    # 次级原因
    if constraint_applied:
        secondary.append("POSITION_CAP")
    if inst.state == "ACCUMULATION":
        secondary.append("INST_ACCUMULATION")
    elif inst.state == "ACCUMULATION_WEAK":
        secondary.append("INST_ACCUMULATION_WEAK")
    elif inst.state in ("DISTRIBUTION", "DISTRIBUTION_STRONG"):
        secondary.append("INST_DISTRIBUTION")
    elif inst.state == "CAPITULATION":
        secondary.append("INST_CAPITULATION")
    if row.get("f_state") == "F↓":
        secondary.append("FUND_FLOW_NEGATIVE")
    if row.get("c_state") == "C↓":
        secondary.append("CHIP_DECLINE")
    if row.get("p_state") == "P↓":
        secondary.append("PRICE_DECLINE")
    if (row.get("data_quality") or "") == "D":
        secondary.append("DATA_LOW_CONFIDENCE")
    if row.get("chase_filter"):
        secondary.append("CHASE_FILTER")
    # 去重保序
    seen, uniq = set(), []
    for c in secondary:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return primary, tuple(uniq)


def build_decision_snapshot(prev_fsm_state, previous_position, row, settings,
                            rule_version=DECISION_RULE_VERSION,
                            model_version=MODEL_VERSION,
                            run_id="",
                            decision_id=None) -> DecisionSnapshot:
    """兼容入口（2.3 起委托唯一决策引擎 engine.evaluate，禁止双编排）"""
    from .engine import DecisionConfig, evaluate
    return evaluate(dict(row), prev_fsm_state, previous_position, settings,
                    config=DecisionConfig(), rule_version=rule_version,
                    model_version=model_version, run_id=run_id,
                    decision_id=decision_id)


def _snapshot_from_dict(s: dict) -> DecisionSnapshot:
    """Snapshot 风格 dict（Ledger / Shadow JSON）→ 不可变 DecisionSnapshot"""
    return DecisionSnapshot(
        decision_id=s.get("decision_id"),
        stock_code=s.get("stock_code"),
        decision_date=s.get("decision_date"),
        institutional_state=s.get("institutional_state"),
        institutional_permission=s.get("institutional_permission"),
        permission_cap=s.get("permission_cap"),
        exit_event_kind=s.get("exit_event_kind"),
        exit_event_reason=s.get("exit_event_reason"),
        setup_type=s.get("setup_type"),
        prev_fsm_state=s.get("prev_fsm_state"),
        next_fsm_state=s.get("next_fsm_state"),
        previous_position=s.get("previous_position"),
        target_position=s.get("target_position"),
        decision_path=tuple(s.get("decision_path") or ()),
        rule_version=s.get("rule_version", DECISION_RULE_VERSION),
        model_version=s.get("model_version", MODEL_VERSION),
        schema_version=s.get("schema_version", SCHEMA_VERSION),
        base_fsm_state=s.get("base_fsm_state", ""),
        raw_target_position=s.get("raw_target_position", 0.0),
        permission_constraint_applied=bool(
            s.get("permission_constraint_applied")),
        override_rule_ids=tuple(s.get("override_rule_ids") or ()),
        input_fingerprint=s.get("input_fingerprint", ""),
        settings_hash=s.get("settings_hash", ""),
        institutional_pressure=int(s.get("institutional_pressure") or 0),
        institutional_persistence=int(s.get("institutional_persistence") or 0),
        institutional_reasons=tuple(s.get("institutional_reasons") or ()),
        context=dict(s.get("context") or {}),
        primary_reason=s.get("primary_reason", ""),
        secondary_reasons=tuple(s.get("secondary_reasons") or ()),
        run_id=s.get("run_id", ""),
        participation_mode=s.get("participation_mode", ""),
        participation_cap=float(s.get("participation_cap") or 0.0),
        position_class=s.get("position_class", ""),
        exit_severity=int(s.get("exit_severity") or 0),
        feature_manifest_hash=s.get("feature_manifest_hash", ""),
        trade_quality=float(s.get("trade_quality") or 0.0),
        trade_quality_band=s.get("trade_quality_band", ""),
        pit_grade=s.get("pit_grade", ""),
        evidence_grade=s.get("evidence_grade", ""),
        data_snapshot_id=s.get("data_snapshot_id", ""),
        data_version=s.get("data_version", "1.0"),
    )


def build_report_snapshot(row, settings, shadow_dir=None, run_id=None,
                          mode=None):
    """报告层唯一决策链入口（2.3 Ledger First）

    读取顺序（严格审计身份，settings_hash+model+rule 必须一致）：
      1) qcfp_decision_ledger（正式事实源）
      2) Stateful Shadow 文件（shadow_stateful_*.json）
      3) FLAT/0 单点推算（仅研究提示，非 Ledger 背书）
    正式模式（research_validation / production / audit）下第 3 步被禁止，
    抛 LedgerRequiredError——报告不得展示"重算出来的非正式决策"。
    返回 (DecisionSnapshot, source: str)。
    """
    code, date = row.get("stock_code"), row.get("decision_date")
    settings_hash = _settings_hash(settings)
    # 1) Decision Ledger（唯一决策事实源）
    try:
        from ..common.db import connect
        from .decision_ledger import load_ledger_snapshot
        conn = connect()
        try:
            s = load_ledger_snapshot(
                conn, code, date, settings_hash=settings_hash, run_id=run_id)
            if s:
                return _snapshot_from_dict(s), \
                    f"ledger:{s.get('run_id') or '?'}（正式事实源）"
        finally:
            conn.close()
    except Exception:
        pass
    # 2) Stateful Shadow 文件（严格 settings_hash/model/rule 匹配）
    if shadow_dir is None:
        from ..common.paths import get_report_root
        shadow_dir = get_report_root() / "shadow"
    shadow_dir = Path(shadow_dir)
    files = sorted(shadow_dir.glob("shadow_stateful_*.json"),
                   key=lambda p: p.stat().st_mtime)
    for f in reversed(files):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for s in data.get("snapshots", []):
            if s.get("stock_code") != code or s.get("decision_date") != date:
                continue
            if s.get("settings_hash") not in (None, "", settings_hash):
                continue
            if s.get("model_version") not in (None, "", MODEL_VERSION):
                continue
            if s.get("rule_version") not in (None, "", DECISION_RULE_VERSION):
                continue
            return _snapshot_from_dict(s), \
                f"shadow:{f.name}（settings_hash 已匹配）"
    # 3) 单点推算（非正式）
    if mode is None:
        mode = (settings or {}).get("backtest", {}).get(
            "mode", "research_exploration")
    if mode in ("research_validation", "production", "audit"):
        raise LedgerRequiredError(
            f"正式模式（{mode}）要求 qcfp_decision_ledger 存在 "
            f"{code}/{date} 的 ACTIVE 决策；禁止 FLAT/0 单点重算")
    snap = build_decision_snapshot("FLAT", 0.0, row, settings)
    return snap, \
        "NON_CANONICAL|point-in-time 推算（无 Ledger/Shadow 匹配，按 FLAT/0 起算）"


def load_canonical_decision(row, settings, shadow_dir=None, run_id=None,
                            mode=None):
    """2.5 唯一事实源加载器（正式语义）

    PRODUCTION / RESEARCH_VALIDATION / AUDIT：Ledger ONLY（缺失即抛错）；
    EXPLORATION：允许 Shadow/NON_CANONICAL fallback（必须带标记）。
    build_report_snapshot 为兼容别名（实现相同）。
    """
    return build_report_snapshot(row, settings, shadow_dir=shadow_dir,
                                 run_id=run_id, mode=mode)
