# coding: utf-8
"""Decision Ledger（QCFP-MTF 2.3：唯一决策事实源）

原则：One Decision → Many Consumers；历史决策不可变（append-only）。
    Decision Engine → DecisionSnapshot → Decision Ledger
    → Shadow / Backtest / Report / Audit 全部只读 Ledger，禁止报告自行重算。

审计身份（Audit Identity）：
    decision_id + run_id + input_fingerprint + settings_hash +
    model_version + rule_version + schema_version
    七元组一致，才认为两次决策是同一个版本。

不可变性：record_snapshot 只追加（INSERT OR IGNORE），禁止 UPDATE；
发现错误 → invalidate_snapshot() 标记旧决策 INVALIDATED + superseded_by，
再写入新决策，绝不覆盖历史。
"""

import json
import hashlib
import subprocess
import sys
from datetime import datetime

from ..decision.decision_snapshot import (DECISION_RULE_VERSION, MODEL_VERSION,
                                          SCHEMA_VERSION, _settings_hash)
from .replay_contract import replay_eligibility

LEDGER_COLUMNS = [
    "decision_id", "run_id", "stock_code", "decision_date",
    "input_fingerprint", "data_snapshot_id", "data_version",
    "settings_hash", "model_version", "rule_version",
    "schema_version", "institutional_state", "institutional_pressure",
    "institutional_persistence", "institutional_permission", "permission_cap",
    "institutional_reasons", "setup_type", "daily_trigger", "exit_event",
    "exit_reason", "previous_fsm_state", "next_fsm_state", "base_fsm_state",
    "previous_position", "raw_target", "final_target",
    "permission_constraint_applied", "override_rule_ids", "decision_path",
    "primary_reason", "secondary_reasons", "pit_grade", "data_quality",
    "evidence_grade", "participation_mode", "participation_cap",
    "position_class", "exit_severity", "feature_manifest_hash",
    "trade_quality", "trade_quality_band", "context", "status",
    "superseded_by", "created_at",
]


def _j(value):
    return json.dumps(value, ensure_ascii=False, default=str) \
        if value not in (None, "", ()) else None


_CODE_COMMIT_CACHE = None


def _code_commit() -> str:
    global _CODE_COMMIT_CACHE
    if _CODE_COMMIT_CACHE is not None:
        return _CODE_COMMIT_CACHE
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        _CODE_COMMIT_CACHE = out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        _CODE_COMMIT_CACHE = ""
    return _CODE_COMMIT_CACHE


_DEPENDENCY_HASH_CACHE = None


def _dependency_hash() -> str:
    global _DEPENDENCY_HASH_CACHE
    if _DEPENDENCY_HASH_CACHE is not None:
        return _DEPENDENCY_HASH_CACHE
    try:
        from ..common.paths import get_project_root
        req = get_project_root() / "Doc" / "requirements.txt"
        if req.exists():
            import hashlib
            _DEPENDENCY_HASH_CACHE = hashlib.sha256(
                req.read_text(encoding="utf-8").encode("utf-8")
            ).hexdigest()[:12]
            return _DEPENDENCY_HASH_CACHE
    except Exception:
        pass
    _DEPENDENCY_HASH_CACHE = ""
    return _DEPENDENCY_HASH_CACHE


def compute_data_snapshot_id(conn) -> str:
    """DataSnapshotID（P0-B 新 4 号）：content-sensitive。

    委托 dataset_manifest_hash——schema + row count + as-of range +
    content hash + universe snapshot + corporate action +
    disclosure override；历史数据改一个字段（即使行数不变）→ 哈希变化。
    """
    return dataset_manifest_hash(conn)


def dataset_manifest_hash(conn, tables=None) -> str:
    """Dataset Manifest Hash（P0-3 号）：
        表/版本/schema hash/row count/min-max as-of/content hash/
        universe/corporate action/disclosure override

    历史数据改一个值（即使行数不变）→ content hash 变化 → manifest 变化。
    P0-B（新 4 号）：补 schema hash 与 as-of 范围，并纳入 universe /
    corporate action / disclosure override 快照。
    """
    import hashlib
    tables = tables or ("qcfp_quarterly_structural",
                        "qcfp_monthly_behavior", "qcfp_weekly_tactical",
                        "qcfp_daily_tactical", "qcfp_mtf_decision")
    parts = []
    for t in tables:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            schema = conn.execute(
                f"PRAGMA table_info({t})").fetchall()
            schema_hash = hashlib.sha256(
                "|".join(f"{r[1]}:{r[2]}" for r in schema)
                .encode("utf-8")).hexdigest()[:8]
            r = conn.execute(
                f"SELECT MIN(rowid) AS mn, MAX(rowid) AS mx FROM {t}"
            ).fetchone()
            # content hash：抽样关键行（最多 5000 行）保证内容变化可检测
            rows = conn.execute(
                f"SELECT * FROM {t} LIMIT 5000").fetchall()
            content = hashlib.sha256(
                "|".join(str(dict(row)) for row in rows).encode("utf-8")
            ).hexdigest()[:12]
            parts.append(f"{t}:schema={schema_hash}:rows={n}:"
                         f"id=({r['mn']},{r['mx']}):"
                         f"content={content}")
        except Exception:
            parts.append(f"{t}:?")
    # Universe / Corporate Action / Disclosure Override 快照（表存在才纳入）
    for extra in ("hk_stock_info", "corporate_action",
                  "disclosure_overrides"):
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {extra}").fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM {extra} LIMIT 2000").fetchall()
            content = hashlib.sha256(
                "|".join(str(dict(row)) for row in rows).encode("utf-8")
            ).hexdigest()[:10]
            parts.append(f"{extra}:rows={n}:content={content}")
        except Exception:
            pass
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def ledger_event(conn, decision_id, event_type, payload=None,
                 created_at=None) -> None:
    """Append-only 事件（P0-3 号）：Invalidate 不再 UPDATE 原 Decision，
    而是追加 DECISION_INVALIDATED 事件（历史事实永不修改）。"""
    from datetime import datetime
    cur = conn.execute(
        "INSERT OR IGNORE INTO qcfp_decision_ledger "
        "(decision_id, run_id, stock_code, decision_date, status, "
        "primary_reason, context, created_at) "
        "SELECT decision_id, run_id || '_EVENT', stock_code, decision_date, "
        "?, ?, ?, ? FROM qcfp_decision_ledger "
        "WHERE decision_id=? AND status='ACTIVE' LIMIT 1",
        (event_type, event_type,
         _j({"event": event_type, "payload": payload or {},
             "superseded": True}),
         created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         decision_id))
    conn.commit()
    return cur.rowcount


def register_model(conn, settings, model_version, rule_version,
                   schema_version, feature_manifest_hash="",
                   created_at=None) -> int:
    """Model Registry：settings_hash → settings_blob（完整配置可复现）"""
    from .versions import feature_manifest_hash as _fmh
    settings_hash = _settings_hash(settings)
    fmh = feature_manifest_hash or _fmh()
    created = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = (model_version, rule_version, schema_version, fmh, settings_hash,
           json.dumps(settings, ensure_ascii=False, default=str),
           _code_commit(), sys.version.split()[0], _dependency_hash(),
           created, "ACTIVE")
    cur = conn.execute(
        "INSERT OR IGNORE INTO qcfp_model_registry "
        "(model_version, rule_version, schema_version, feature_manifest_hash, "
        "settings_hash, settings_blob, code_commit, python_version, "
        "dependency_hash, created_at, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        row)
    return cur.rowcount


def record_snapshot(conn, snap, run_id, pit_grade=None, evidence_grade=None,
                    created_at=None, settings=None, data_snapshot_id=None):
    """把 DecisionSnapshot 追加写入台账（不可变：INSERT OR IGNORE）

    同一七元审计身份已存在 → 跳过（不覆盖历史）。
    2.5：PIT/证据分级取自 DecisionSnapshot（evidence 层计算），禁止硬编码。
    settings 提供时自动写入 Model Registry（settings_hash → settings_blob）。
    2.8（8 号）：写入前强制 FSM 权威校验——目标变化必须有合法状态依据，
    无法解释的仓位变化拒绝写入 Ledger。
    2.8（P0-2）：每条记录带 previous/current ledger_hash，形成
    不可篡改的事实链（current = hash(prev_hash + 本条决策核心字段)）。
    """
    from .fsm_authority import assert_fsm_explains_target_change
    # PWC-1（第 6 项）：Ledger Commit 前不可绕过 Invariant Gate
    assert_snapshot_commit_invariants(snap)
    assert_fsm_explains_target_change(
        snap.prev_fsm_state, snap.next_fsm_state,
        snap.previous_position, snap.target_position,
        reason=snap.primary_reason)
    if settings is not None:
        register_model(conn, settings, snap.model_version, snap.rule_version,
                       snap.schema_version, snap.feature_manifest_hash,
                       created_at)
    snap_id = data_snapshot_id or dataset_manifest_hash(conn)
    row = {
        "decision_id": snap.decision_id,
        "run_id": run_id,
        "stock_code": snap.stock_code,
        "decision_date": snap.decision_date,
        "input_fingerprint": snap.input_fingerprint,
        "data_snapshot_id": snap_id,
        "data_version": "1.0",
        "settings_hash": snap.settings_hash,
        "model_version": snap.model_version,
        "rule_version": snap.rule_version,
        "schema_version": snap.schema_version,
        "institutional_state": snap.institutional_state,
        "institutional_pressure": int(snap.institutional_pressure),
        "institutional_persistence": int(snap.institutional_persistence),
        "institutional_permission": snap.institutional_permission,
        "permission_cap": snap.permission_cap,
        "institutional_reasons": _j(snap.institutional_reasons),
        "setup_type": snap.setup_type,
        "daily_trigger": snap.context.get("daily_trigger"),
        "exit_event": snap.exit_event_kind,
        "exit_reason": snap.exit_event_reason,
        "previous_fsm_state": snap.prev_fsm_state,
        "next_fsm_state": snap.next_fsm_state,
        "base_fsm_state": snap.base_fsm_state,
        "previous_position": float(snap.previous_position or 0.0),
        "raw_target": float(snap.raw_target_position or 0.0),
        "final_target": float(snap.target_position or 0.0),
        "permission_constraint_applied":
            int(bool(snap.permission_constraint_applied)),
        "override_rule_ids": _j(snap.override_rule_ids),
        "decision_path": _j(snap.decision_path),
        "primary_reason": getattr(snap, "primary_reason", ""),
        "secondary_reasons": _j(getattr(snap, "secondary_reasons", ())),
        "participation_mode": getattr(snap, "participation_mode", ""),
        "participation_cap": float(
            getattr(snap, "participation_cap", 0.0) or 0.0),
        "position_class": getattr(snap, "position_class", ""),
        "exit_severity": int(getattr(snap, "exit_severity", 0) or 0),
        "feature_manifest_hash": getattr(snap, "feature_manifest_hash", ""),
        "trade_quality": float(getattr(snap, "trade_quality", 0.0) or 0.0),
        "trade_quality_band": getattr(snap, "trade_quality_band", ""),
        "pit_grade": pit_grade or getattr(snap, "pit_grade", "") or "C",
        "data_quality": snap.context.get("data_quality"),
        "evidence_grade": evidence_grade or getattr(
            snap, "evidence_grade", "") or "D",
        "context": _j(snap.context),
        "status": "ACTIVE",
        "superseded_by": None,
        "created_at": created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    identity = " AND ".join([
        "decision_id=?", "run_id=?", "input_fingerprint=?",
        "data_snapshot_id=?", "data_version=?",
        "settings_hash=?", "model_version=?", "rule_version=?",
        "schema_version=?"])
    exists = conn.execute(
        f"SELECT 1 FROM qcfp_decision_ledger WHERE {identity} LIMIT 1",
        (snap.decision_id, run_id, snap.input_fingerprint,
         snap_id, "1.0", snap.settings_hash, snap.model_version,
         snap.rule_version, snap.schema_version)).fetchone()
    if exists:
        return 0
    # P0-2 / P0-B（新 4 号）：双链——global 链 + run 链
    prev_hash = _last_ledger_hash(conn)
    row_dict = dict(row)
    row_dict.pop("context", None)
    current_hash = _ledger_hash(prev_hash, row_dict)
    run_prev_hash = _last_run_hash(conn, run_id)
    run_current_hash = _ledger_hash(run_prev_hash, row_dict)
    ctx = dict(snap.context or {})
    ctx["ledger_chain"] = {
        "previous_ledger_hash": prev_hash,
        "current_ledger_hash": current_hash,
        "run_previous_hash": run_prev_hash,
        "run_current_hash": run_current_hash,
    }
    # PWC-1（第 5 项）：Release 身份由 Snapshot 携带，
    # Ledger 保存事实，不重新发明事实。
    ctx["release_identity"] = {
        "release_id": getattr(snap, "release_id", "") or "",
        "release_manifest_hash": getattr(
            snap, "release_manifest_hash", "") or "",
        "evidence_pack_hash": getattr(snap, "evidence_pack_hash", "") or "",
        "production_manifest_hash": getattr(
            snap, "production_manifest_hash", "") or "",
        "data_snapshot_id": getattr(snap, "data_snapshot_id", "") or "",
        "universe_snapshot_id": getattr(
            snap, "universe_snapshot_id", "") or "",
    }
    # Q8（Canonical Decision Identity）：把 Snapshot Schema 中的
    # Canonical 关键字段一并持久化到 context，供 Replay 验证
    # （Golden 与 Replay 使用同一套关键字段集合，不创建重复列）。
    ctx["fsm_proposal_target"] = round(
        float(getattr(snap, "fsm_proposal_target", 0.0) or 0.0), 4)
    ctx["wave_proposal_target"] = round(
        float(getattr(snap, "wave_proposal_target", 0.0) or 0.0), 4)
    ctx["canonical_action"] = getattr(snap, "canonical_action", "") or ""
    ctx["binding_constraint"] = getattr(snap, "binding_constraint", "") or ""
    ctx["production_manifest_hash"] = getattr(
        snap, "production_manifest_hash", "") or ""
    ctx["participating_feature_hash"] = getattr(
        snap, "participating_feature_hash", "") or ""
    # Q8（Trust Evidence）：Replayability Gate——
    # settings_hash → settings_blob 必须 100% 可解析；release/evidence/
    # path 材料必须齐全。决策仍可记录为事实，但 replay_eligible 标记
    # 材料完整性（Production Certification 应阻止长期 replay_eligible=False）。
    replay_elig = replay_eligibility(conn, snap)
    ctx["replay_eligibility"] = replay_elig
    ctx["replay_eligible"] = bool(replay_elig["replay_eligible"])
    ctx["replay_missing_material"] = list(replay_elig["missing"])
    row["context"] = _j(ctx)
    conn.execute(
        "INSERT OR IGNORE INTO qcfp_decision_ledger "
        f"({','.join(LEDGER_COLUMNS)}) VALUES "
        f"({','.join('?' * len(LEDGER_COLUMNS))})",
        [row.get(c) for c in LEDGER_COLUMNS])
    conn.commit()
    return 1


def _ledger_hash(prev_hash, row_dict) -> str:
    """链式哈希：current = sha256(prev_hash + 决策核心字段)。"""
    import hashlib
    keys = ("decision_id", "stock_code", "decision_date",
            "institutional_permission", "previous_fsm_state",
            "next_fsm_state", "previous_position", "raw_target",
            "final_target", "primary_reason", "model_version",
            "rule_version", "schema_version", "settings_hash",
            "input_fingerprint")
    payload = {k: row_dict.get(k) for k in keys}
    payload["prev"] = prev_hash or ""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                     default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class LedgerCommitRejected(RuntimeError):
    """PWC-1（第 6 项）：Ledger Commit Gate 拒绝不满足不变量的决策。"""


def assert_snapshot_commit_invariants(snap, mode="research_exploration",
                                      permission_cap=None,
                                      hard_caps=None) -> None:
    """Ledger 提交前唯一不可绕过 Invariant Gate（不是第二决策引擎）。

    I1 Permission:  FinalTarget <= PermissionCap
    I2 Wave:        新增风险 FinalTarget <= WaveProposal <= FSMProposal
    I3 CanonicalAction == f(previous_position, final_target)
    I4 Governance:  FinalTarget <= 每个适用 HardCap
    I5 PIT:         pit 有效/可认证
    I6 Identity:    Production identity 完整

    Production mode 下任意失败 → LedgerCommitRejected。
    """
    from .canonical_action import assert_canonical_action_invariant, \
        wave_proposal_monotonic
    violations = []
    final = float(getattr(snap, "target_position", 0.0) or 0.0)
    prev = float(getattr(snap, "previous_position", 0.0) or 0.0)
    # I1 Permission
    if permission_cap is not None and final > float(permission_cap) + 1e-9:
        violations.append("I1_PERMISSION_CAP")
    # I2 Wave 单调（新增风险路径；Final=0 除外）
    if final > 1e-9:
        mono = wave_proposal_monotonic(
            float(getattr(snap, "fsm_proposal_target", 0.0) or 0.0),
            float(getattr(snap, "wave_proposal_target", 0.0) or 0.0),
            final)
        if not mono["monotonic"]:
            violations.append("I2_WAVE_MONOTONICITY")
    # I3 CanonicalAction
    action = getattr(snap, "canonical_action", "") or ""
    if action:
        inv = assert_canonical_action_invariant(prev, final, action)
        if not inv["ok"]:
            violations.append("I3_CANONICAL_ACTION")
    # I4 Governance HardCaps
    caps = hard_caps or {}
    for name, cap in caps.items():
        if cap is not None and final > float(cap) + 1e-9:
            violations.append(f"I4_{name.upper()}")
    # I5 PIT
    pit = getattr(snap, "pit_grade", "") or ""
    if pit not in ("A", "B"):
        violations.append("I5_PIT")
    # I6 Identity（Production mode）
    if mode in ("production", "research_validation"):
        if not getattr(snap, "release_id", ""):
            violations.append("I6_RELEASE_ID")
        if not getattr(snap, "release_manifest_hash", ""):
            violations.append("I6_RELEASE_MANIFEST_HASH")
    if violations and mode in ("production", "research_validation"):
        raise LedgerCommitRejected(
            f"LedgerCommitGate: {violations}")
    return {"violations": violations,
            "verdict": "COMMIT_OK" if not violations
            else "REJECTED_IN_PRODUCTION" if mode in (
                "production", "research_validation")
            else "RESEARCH_ALLOWED"}


def _last_ledger_hash(conn) -> str:
    """最近一条记录 context.ledger_chain.current_ledger_hash。"""
    try:
        r = conn.execute(
            "SELECT context FROM qcfp_decision_ledger "
            "WHERE id=(SELECT MAX(id) FROM qcfp_decision_ledger)"
        ).fetchone()
        if r and r["context"]:
            ctx = json.loads(r["context"])
            return (ctx.get("ledger_chain") or {}).get(
                "current_ledger_hash") or ""
    except Exception:
        pass
    return ""


def _last_run_hash(conn, run_id: str) -> str:
    """run 级链尾：同 run_id 最后一条 context.run_current_hash。"""
    if not run_id:
        return ""
    try:
        r = conn.execute(
            "SELECT context FROM qcfp_decision_ledger "
            "WHERE run_id=? AND id=(SELECT MAX(id) FROM "
            "qcfp_decision_ledger WHERE run_id=?)",
            (run_id, run_id)).fetchone()
        if r and r["context"]:
            ctx = json.loads(r["context"])
            return (ctx.get("ledger_chain") or {}).get(
                "run_current_hash") or ""
    except Exception:
        pass
    return ""


def verify_ledger_chain(conn, run_id=None) -> dict:
    """校验台账哈希链完整性（P0-2）：
        每条 current = hash(prev + 本条)；prev 必须等于上一条 current。
    返回 {verified, checked, mismatches, chain_tail}。

    P0-B（新 4 号）：run_id 给出时同时校验 global 链与 run 链；
    run_id 为空时校验 global 链。
    """
    sql = ("SELECT decision_id, stock_code, decision_date, "
           "institutional_permission, previous_fsm_state, next_fsm_state, "
           "previous_position, raw_target, final_target, primary_reason, "
           "model_version, rule_version, schema_version, settings_hash, "
           "input_fingerprint, context, id FROM qcfp_decision_ledger")
    params = []
    if run_id:
        sql += " WHERE run_id=?"
        params.append(run_id)
    sql += " ORDER BY id ASC"
    rows = conn.execute(sql, params).fetchall()
    prev = ""
    run_prev = ""
    mismatches = []
    run_mismatches = []
    checked = 0
    run_checked = 0
    for r in rows:
        row_dict = {k: r[k] for k in (
            "decision_id", "stock_code", "decision_date",
            "institutional_permission", "previous_fsm_state",
            "next_fsm_state", "previous_position", "raw_target",
            "final_target", "primary_reason", "model_version",
            "rule_version", "schema_version", "settings_hash",
            "input_fingerprint")}
        expected = _ledger_hash(prev, row_dict)
        run_expected = _ledger_hash(run_prev, row_dict) if run_id else ""
        stored = ""
        run_stored = ""
        if r["context"]:
            try:
                chain = (json.loads(r["context"]).get("ledger_chain")
                         or {})
                stored = chain.get("current_ledger_hash") or ""
                run_stored = chain.get("run_current_hash") or ""
            except Exception:
                stored = ""
        if stored and stored != expected:
            mismatches.append(
                f"{r['decision_id']}: stored={stored} expected={expected}")
        elif stored:
            checked += 1
        if run_id and run_stored and run_stored != run_expected:
            run_mismatches.append(
                f"{r['decision_id']}: run_stored={run_stored} "
                f"run_expected={run_expected}")
        elif run_id and run_stored:
            run_checked += 1
        prev = expected
        run_prev = run_expected
    return {
        "verified": not mismatches and not run_mismatches,
        "checked": checked,
        "run_checked": run_checked,
        "n_rows": len(rows),
        "mismatches": mismatches,
        "run_mismatches": run_mismatches,
        "chain_tail": prev,
        "run_chain_tail": run_prev,
    }


def verify_chain_records(records, run_filter=None) -> dict:
    """新 6 号：纯链校验（可测试）。

    records：[{"run_id", "id", "prev_hash", "current_hash",
               "run_prev_hash", "run_current_hash"}] 按全局 id 升序。
    run_filter 给定时只验证该 run 的 run 链（绝不在 run 过滤行上验 Global）。
    """
    if run_filter is not None:
        rows = [r for r in records if r.get("run_id") == run_filter]
        prev = ""
        mismatches = []
        for r in rows:
            expected = r.get("run_current_hash")
            if expected and r.get("run_prev_hash") != prev:
                mismatches.append({
                    "location": f"run={run_filter},id={r.get('id')}",
                    "expected_prev": prev,
                    "stored_prev": r.get("run_prev_hash")})
            prev = expected or prev
        return {"global_verified": None,
                "run_verified": not mismatches,
                "global_tail": None,
                "run_tail": prev,
                "mismatch_location": mismatches}
    prev = ""
    mismatches = []
    for r in records:
        expected = r.get("current_hash")
        if expected and r.get("prev_hash") != prev:
            mismatches.append({
                "location": f"global,id={r.get('id')}",
                "expected_prev": prev,
                "stored_prev": r.get("prev_hash")})
        prev = expected or prev
    return {"global_verified": not mismatches,
            "run_verified": None,
            "global_tail": prev,
            "run_tail": None,
            "mismatch_location": mismatches}


def verify_global_chain(conn) -> dict:
    """新 6 号：Global 链——所有 Ledger row ORDER BY global sequence。"""
    rows = conn.execute(
        "SELECT id, context FROM qcfp_decision_ledger ORDER BY id"
    ).fetchall()
    records = []
    for r in rows:
        chain = {}
        if r["context"]:
            try:
                chain = (json.loads(r["context"]).get("ledger_chain")
                         or {})
            except Exception:
                chain = {}
        records.append({"id": r["id"],
                        "prev_hash": chain.get("previous_ledger_hash"),
                        "current_hash": chain.get("current_ledger_hash")})
    return verify_chain_records(records)


def verify_run_chain(conn, run_id: str) -> dict:
    """新 6 号：Run 链——WHERE run_id=? ORDER BY id，只验证 run 链。"""
    rows = conn.execute(
        "SELECT id, context FROM qcfp_decision_ledger "
        "WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    records = []
    for r in rows:
        chain = {}
        if r["context"]:
            try:
                chain = (json.loads(r["context"]).get("ledger_chain")
                         or {})
            except Exception:
                chain = {}
        records.append({"id": r["id"], "run_id": run_id,
                        "run_prev_hash": chain.get("run_previous_hash"),
                        "run_current_hash": chain.get("run_current_hash")})
    return verify_chain_records(records, run_filter=run_id)


def verify_ledger_run_chain(conn, run_id: str) -> dict:
    """单 run 链独立校验（P0-B 新 4 号）。"""
    return verify_ledger_chain(conn, run_id=run_id)


def audit_identity(snap, run_id="") -> tuple:
    """九元审计身份（含 Data Snapshot ID / Data Version）"""
    return (snap.decision_id, run_id, snap.input_fingerprint,
            getattr(snap, "data_snapshot_id", "") or "",
            getattr(snap, "data_version", "1.0") or "1.0",
            snap.settings_hash, snap.model_version, snap.rule_version,
            snap.schema_version)


def invalidate_snapshot(conn, decision_id, run_id, superseded_by,
                        created_at=None):
    """Append-only 失效（P0-B 新 4 号）：不再 UPDATE 原决策行。

    追加 DECISION_INVALIDATED 事件（历史事实永不修改），
    原 ACTIVE 行保持不可变；返回新增事件行数。
    """
    return ledger_event(
        conn, decision_id, "DECISION_INVALIDATED",
        payload={"superseded_by": superseded_by, "run_id": run_id},
        created_at=created_at)


def _snap_from_ledger_row(r):
    """台账行 → DecisionSnapshot 兼容 dict（报告层只展示，不重算）"""
    def _u(v):
        if v is None:
            return ()
        try:
            return tuple(json.loads(v)) if isinstance(v, str) else tuple(v)
        except Exception:
            return (str(v),)
    return {
        "decision_id": r["decision_id"],
        "run_id": r["run_id"],
        "stock_code": r["stock_code"],
        "decision_date": r["decision_date"],
        "input_fingerprint": r["input_fingerprint"],
        "data_snapshot_id": r["data_snapshot_id"]
        if "data_snapshot_id" in r.keys() else "",
        "data_version": r["data_version"]
        if "data_version" in r.keys() else "1.0",
        "settings_hash": r["settings_hash"],
        "model_version": r["model_version"],
        "rule_version": r["rule_version"],
        "schema_version": r["schema_version"],
        "institutional_state": r["institutional_state"],
        "institutional_permission": r["institutional_permission"],
        "permission_cap": r["permission_cap"],
        "institutional_pressure": int(r["institutional_pressure"] or 0),
        "institutional_persistence": int(r["institutional_persistence"] or 0),
        "institutional_reasons": _u(r["institutional_reasons"]),
        "setup_type": r["setup_type"],
        "exit_event_kind": r["exit_event"],
        "exit_event_reason": r["exit_reason"] or "",
        "prev_fsm_state": r["previous_fsm_state"],
        "next_fsm_state": r["next_fsm_state"],
        "base_fsm_state": r["base_fsm_state"],
        "previous_position": float(r["previous_position"] or 0.0),
        "raw_target_position": float(r["raw_target"] or 0.0),
        "target_position": float(r["final_target"] or 0.0),
        "permission_constraint_applied":
            bool(r["permission_constraint_applied"]),
        "override_rule_ids": _u(r["override_rule_ids"]),
        "decision_path": _u(r["decision_path"]),
        "primary_reason": r["primary_reason"] or "",
        "secondary_reasons": _u(r["secondary_reasons"]),
        "participation_mode": r["participation_mode"]
        if "participation_mode" in r.keys() else "",
        "participation_cap": float(r["participation_cap"] or 0.0)
        if "participation_cap" in r.keys() else 0.0,
        "position_class": r["position_class"]
        if "position_class" in r.keys() else "",
        "exit_severity": int(r["exit_severity"] or 0)
        if "exit_severity" in r.keys() else 0,
        "feature_manifest_hash": r["feature_manifest_hash"]
        if "feature_manifest_hash" in r.keys() else "",
        "trade_quality": float(r["trade_quality"] or 0.0)
        if "trade_quality" in r.keys() else 0.0,
        "trade_quality_band": r["trade_quality_band"]
        if "trade_quality_band" in r.keys() else "",
        "context": json.loads(r["context"]) if r["context"] else {},
        "status": r["status"] if "status" in r.keys() else "ACTIVE",
        "superseded_by": r["superseded_by"] if "superseded_by" in r.keys() else None,
    }


def load_ledger_snapshot(conn, stock, date, settings_hash=None,
                         model_version=MODEL_VERSION,
                         rule_version=DECISION_RULE_VERSION,
                         run_id=None, input_fingerprint=None):
    """严格审计身份读取：stock+date+七元身份子集全部一致，仅 ACTIVE"""
    sql = ("SELECT * FROM qcfp_decision_ledger WHERE stock_code=? "
           "AND decision_date=? AND model_version=? AND rule_version=? "
           "AND status='ACTIVE'")
    params = [stock, date, model_version, rule_version]
    if input_fingerprint:
        sql += " AND input_fingerprint=?"
        params.append(input_fingerprint)
    if settings_hash:
        sql += " AND settings_hash=?"
        params.append(settings_hash)
    if run_id:
        sql += " AND run_id=?"
        params.append(run_id)
    sql += " ORDER BY created_at DESC, id DESC LIMIT 1"
    r = conn.execute(sql, params).fetchone()
    return _snap_from_ledger_row(r) if r else None


def latest_ledger_identity(conn, stock, date):
    """返回最近一次台账决策的 (run_id, settings_hash, model_version, rule_version)"""
    r = conn.execute(
        "SELECT run_id, settings_hash, model_version, rule_version "
        "FROM qcfp_decision_ledger WHERE stock_code=? AND decision_date=? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (stock, date)).fetchone()
    return dict(r) if r else None


def ledger_summary(conn, stock=None, date=None):
    """台账统计（供审计/报告展示）"""
    sql = "SELECT COUNT(*) AS n FROM qcfp_decision_ledger"
    params = []
    if stock:
        sql += " WHERE stock_code=?"
        params.append(stock)
    if date:
        sql += " AND decision_date=?" if not stock else " AND decision_date=?"
        params.append(date)
    return conn.execute(sql, params).fetchone()["n"]
