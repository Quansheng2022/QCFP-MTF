# coding: utf-8
"""Replay Certification（QCFP-MTF 2.8：回放证书）

指纹链：
    input_hash → decision_hash → certificate_hash → ledger_hash

不变式：Live == Replay == Backtest == Ledger（同一决策身份下），
任何一环不一致 → status = REPLAY_MISMATCH，并给出 diff 明细。

    Live    模式实际产生的 UnifiedDecision/DecisionSnapshot
    Replay  同一输入重放 Engine 产生的对象
    Backtest 回测引擎在相同历史时点产生的对象
    Ledger  决策台账中的固化记录

指纹口径：四类对象（DecisionSnapshot / DecisionCertificate / Ledger Row /
回放快照）统一投影为"决策核心字段"（decision_core_fields）再哈希——
只包含**决策输出 + 版本身份**（permission/setup/exit/fsm/positions/reasons/
model/rule/schema），避免因展示字段（context / constraint_trace 等）不同
造成假阳性。

输入与设置漂移（input_fingerprint / settings_hash）不参与决策指纹，
而是作为链上的独立诊断信号：决策可验证但输入已漂移时，报告会同时展示
「决策链 VERIFIED + input/settings drift」，而不是误报决策不一致。
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ReplayCert:
    decision_id: str
    input_hash: str
    decision_hash: str
    certificate_hash: str
    ledger_hash: str
    chain: tuple
    status: str              # VERIFIED / REPLAY_MISMATCH
    reasons: tuple = field(default_factory=tuple)
    diffs: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["chain"] = list(self.chain)
        d["reasons"] = list(self.reasons)
        d["diffs"] = list(self.diffs)
        return d


def _norm_value(v):
    """归一化：tuple→list、JSON 字符串→list、None→''。"""
    if v is None:
        return ""
    if isinstance(v, tuple):
        return list(v)
    if isinstance(v, str) and v.startswith("[") and v.endswith("]"):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def _first(*values):
    """取第一个非 None 值（保留 0.0/False 等假值）。"""
    for v in values:
        if v is not None:
            return v
    return None


def decision_core_fields(obj) -> dict:
    """统一投影：DecisionSnapshot / DecisionCertificate / Ledger Row /
    dict 全部归一化为同一组决策核心字段。"""
    get = obj.get if isinstance(obj, dict) else \
        (lambda k: getattr(obj, k, None))
    # 证书/部分对象用 reason_codes 合并表示原因，归一化为 primary/secondary
    primary = get("primary_reason")
    secondary = _norm_value(get("secondary_reasons"))
    reason_codes = _norm_value(get("reason_codes"))
    if primary is None and reason_codes:
        primary = reason_codes[0]
        secondary = reason_codes[1:]
    return {
        "decision_id": get("decision_id"),
        "stock_code": _first(get("stock_code"), get("symbol")),
        "decision_date": _first(get("decision_date"), get("timestamp")),
        "permission": get("institutional_permission"),
        "setup": _first(get("setup_type"), get("setup")),
        "exit_event": _first(get("exit_event_kind"), get("exit_event")),
        "prev_fsm": _first(get("prev_fsm_state"), get("previous_fsm"),
                           get("previous_fsm_state")),
        "next_fsm": _first(get("next_fsm_state"), get("next_fsm")),
        "previous_position": get("previous_position"),
        "final_target": _first(get("target_position"), get("final_target")),
        "participation_mode": get("participation_mode"),
        "participation_cap": get("participation_cap"),
        "primary_reason": primary,
        "secondary_reasons": secondary or [],
        "model_version": get("model_version"),
        "rule_version": get("rule_version"),
        "schema_version": get("schema_version"),
    }


def decision_fingerprint(obj) -> str:
    """决策核心字段指纹（跨对象类型可比）。"""
    raw = json.dumps(decision_core_fields(obj), sort_keys=True,
                     ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def ledger_fingerprint(ledger_row: dict) -> str:
    """台账行指纹 = 决策核心字段指纹（与快照/证书同口径）。"""
    return decision_fingerprint(ledger_row)


def _fingerprint_parts(obj, input_fields=None) -> str:
    data = obj if isinstance(obj, dict) else asdict(obj)
    if input_fields:
        payload = {k: data.get(k) for k in input_fields
                   if data.get(k) not in (None, "")}
    else:
        payload = data
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def certify_replay(decision_id, input_snapshot, replay_snapshot,
                   backtest_snapshot=None, ledger_row=None,
                   input_fields=None, certificate=None) -> ReplayCert:
    """跨模式一致性认证。

    参数：
        input_snapshot     Live 决策快照（模式基准）
        replay_snapshot    重放同一输入得到的快照
        backtest_snapshot  回测同历史时点快照（可选）
        ledger_row         台账行 dict（可选）
        certificate        证书对象（可选）
    """
    input_hash = _fingerprint_parts(input_snapshot, input_fields) \
        if input_fields else ""
    decision_hash = decision_fingerprint(replay_snapshot)
    cert_hash = decision_fingerprint(certificate) \
        if certificate is not None else ""
    ledger_h = ledger_fingerprint(ledger_row) if ledger_row else ""
    chain = (f"input:{input_hash}", f"decision:{decision_hash}")
    if cert_hash:
        chain += (f"certificate:{cert_hash}",)
    if ledger_h:
        chain += (f"ledger:{ledger_h}",)

    reasons, diffs = [], []
    live_hash = decision_fingerprint(input_snapshot)
    if live_hash != decision_hash:
        reasons.append("LIVE_VS_REPLAY_MISMATCH")
        diffs.append(f"live={live_hash} replay={decision_hash}")
    if backtest_snapshot is not None \
            and decision_fingerprint(backtest_snapshot) != decision_hash:
        reasons.append("REPLAY_VS_BACKTEST_MISMATCH")
        diffs.append(f"replay={decision_hash} "
                     f"backtest={decision_fingerprint(backtest_snapshot)}")
    if ledger_row and ledger_h and ledger_h != decision_hash:
        reasons.append("REPLAY_VS_LEDGER_MISMATCH")
        diffs.append(f"replay={decision_hash} ledger={ledger_h}")
    if certificate is not None and cert_hash and cert_hash != decision_hash:
        reasons.append("REPLAY_VS_CERTIFICATE_MISMATCH")
        diffs.append(f"replay={decision_hash} certificate={cert_hash}")
    status = "VERIFIED" if not reasons else "REPLAY_MISMATCH"
    return ReplayCert(
        decision_id=decision_id, input_hash=input_hash,
        decision_hash=decision_hash, certificate_hash=cert_hash,
        ledger_hash=ledger_h, chain=chain, status=status,
        reasons=tuple(reasons), diffs=tuple(diffs))


def certify_and_safety(cert: ReplayCert, checks: dict = None) -> dict:
    """回放证书 + 安全状态映射（20 号增量）：
        REPLAY_MISMATCH → replay_failure=True → HALTED（禁止新决策）
        VERIFIED        → 保持原安全状态
    返回 {cert, safety_status, triggered}。
    """
    from ..safety.kill_switch import evaluate_safety
    merged = dict(checks or {})
    if cert.status == "REPLAY_MISMATCH":
        merged["replay_failure"] = True
    st = evaluate_safety(merged)
    return {"cert": cert.as_dict(),
            "safety_status": st["status"],
            "triggered": st["triggered"]}
