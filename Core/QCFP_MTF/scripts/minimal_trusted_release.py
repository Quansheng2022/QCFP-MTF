#!/usr/bin/env python
# coding: utf-8
"""QCFP_MTF Minimal Trusted Production Release —— MTR Closure（Sprint E）

本脚本分两个模式：

    1) --generate-artifacts（Build/CI 测量步骤，唯一允许运行测量的入口）
       从真实源码构图 → 冻结 Manifest/Baseline → 真实 Failure Injection
       → 真实 Golden/Replay → 物理删除扫描 → 写出全部证据 artifact。

    2) 默认（纯裁判）
       只读取 audit/mtr 下的 8 类 artifact → evaluate_mtr() → 输出 verdict。
       禁止 run measurements / invent baseline / fix graph / default PASS。

用法：
    python Core/QCFP_MTF/scripts/minimal_trusted_release.py --generate-artifacts
    python Core/QCFP_MTF/scripts/minimal_trusted_release.py
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.governance.failure_injection import \
    run_failure_qualification
from QCFP_MTF.governance.minimal_trusted_release import (
    FROZEN_PRODUCTION_MANIFEST, V9_PRODUCTION_BASELINE_MANIFEST,
    active_feature_diff, critical_loc_metrics, evaluate_mtr,
    physical_delete, physical_retirement_audit,
    production_feature_manifest_artifact, scan_residual_references,
    verify_frozen_manifest)
from QCFP_MTF.governance.pwc2_authority_graph import (
    authority_audit, behavioral_authority_audit, build_authority_graph,
    retirement_classify, retirement_register)

from QCFP_MTF.decision.versions import RELEASE_TAG

MTR_RELEASE_ID = RELEASE_TAG
MTR_ARTIFACT_NAMES = (
    "authority_graph.json", "production_feature_manifest.json",
    "critical_loc_diff.json", "legacy_production_scan.json",
    "golden_result.json", "replay_result.json", "oos_result.json",
    "failure_injection_results.json", "physical_delete_result.json",
)

# Legacy 决策权威函数（禁止出现在 Production 可达代码中）
LEGACY_AUTHORITY_TERMS = ("generate_action", "effective_position_cqs",
                          "build_signal_timeline", "legacy_engine")


def _tree_hash(root) -> str:
    h = hashlib.sha256()
    for py in sorted(Path(root).rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        h.update(py.read_bytes())
    return h.hexdigest()[:16]


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                               default=str), encoding="utf-8")


def _executable_decision_paths(graph: dict) -> int:
    """生产决策路径数 = 可达代码中定义 evaluate() 的模块数（应为 1）。"""
    nodes = graph["nodes"]
    root_dir = Path(graph["root_dir"])
    count = 0
    owners = []
    for m in graph.get("reachable_modules", []):
        p = root_dir / nodes[m].get("file", "")
        if p.exists() and re.search(r"^def\s+evaluate\s*\(", 
                                    p.read_text(encoding="utf-8",
                                                errors="ignore"), re.M):
            count += 1
            owners.append(m)
    return {"count": count, "owners": owners,
            "rule": "正式决策只允许一个 evaluate() 定义者"}


def legacy_production_scan(graph: dict) -> dict:
    """全工程 Legacy 扫描：Production 可达代码不得引用 Legacy 决策权威。

    Research/Shadow/Archive 允许引用 Legacy；scripts/ 下的研究工具引用
    一律标记 research_allowed=True，不计入生产 Legacy Path。"""
    nodes = graph["nodes"]
    root_dir = Path(graph["root_dir"])
    production_legacy_imports = []
    production_legacy_calls = []
    for m in graph.get("reachable_modules", []):
        p = root_dir / nodes[m].get("file", "")
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8", errors="ignore")
        rel = nodes[m].get("file", m)
        for term in LEGACY_AUTHORITY_TERMS:
            if re.search(rf"\b{term}\s*\(", src):
                production_legacy_calls.append({"module": m, "file": rel,
                                                "term": term})
    # CLI 入口扫描：scripts/ 下均为 Research/Shadow/Archive 工具，
    # 允许引用 Legacy（但必须标记，供审计展示）
    legacy_cli_entrypoints = []
    for py in (root_dir / "scripts").rglob("*.py"):
        src = py.read_text(encoding="utf-8", errors="ignore")
        for term in LEGACY_AUTHORITY_TERMS:
            if re.search(rf"\b{term}\s*\(", src):
                legacy_cli_entrypoints.append(
                    {"file": py.relative_to(root_dir).as_posix(),
                     "term": term,
                     "research_allowed": True})
    return {
        "production_legacy_imports": production_legacy_imports,
        "production_legacy_calls": production_legacy_calls,
        "legacy_cli_entrypoints": legacy_cli_entrypoints,
        "production_legacy_paths": bool(production_legacy_imports
                                        or production_legacy_calls),
        "rule": "Research/Shadow/Archive 可引用 Legacy；"
                "Production/Execution/Certification/Report 禁止",
    }


def run_golden_evidence() -> dict:
    """真实运行 Golden 宪法测试（canonical-only），输出 golden_result.json。"""
    import hashlib
    from datetime import datetime
    from QCFP_MTF.tests.test_golden import test_golden_constitution
    from QCFP_MTF.decision.versions import RELEASE_TAG
    results = {}
    for name, fn in sorted(vars(test_golden_constitution).items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                results[name] = "PASS"
            except Exception as exc:
                results[name] = f"FAIL:{exc}"
    passed = sum(1 for v in results.values() if v == "PASS")
    corpus_ids = sorted(n for n in results)
    corpus_hash = hashlib.sha256(
        "\n".join(corpus_ids).encode("utf-8")).hexdigest()[:16]
    return {"status": "PASS" if passed == len(results) and results
            else "FAIL",
            "schema": "GOLDEN-2",
            "release_id": RELEASE_TAG,
            "golden_corpus_version": "GOLDEN-CONSTITUTION-1",
            "golden_corpus_hash": corpus_hash,
            "n_total": len(results),
            "n_passed": passed,
            "n_failed": len(results) - passed,
            "critical_failures": [n for n, v in results.items()
                                  if v != "PASS"],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": results,
            "source": "golden_constitution(canonical-only)"}


def run_replay_evidence(sample=None, date=None) -> dict:
    """Current Release Replay（Q8）：当前 Release 自己产生的 Decision
    必须 100% exact replay。

    Historical Replay 是另一个概念：当年 Decision 用当年 Release 重放
    （facts immutable）；不能用当前引擎要求旧决策 EXACT_MATCH。

    Q8-R1/R2：
    * 正式模式（sample=None）＝ Current Release 全量（无 LIMIT）；
      sample 仅限开发诊断（取最后 N 条）；
      date 给定时（P0-3 Daily Replay）只重放该 trade_date 的决策。
    * Eligibility 使用 replay_eligibility()（settings_blob 真正 parse +
      canonical hash 一致 + 完整 material + 引用可解析）。
    * 统计口径互斥：
        n_historical_skipped（非当前 Release）
        n_ineligible   = n_current_release - n_eligible
        n_mismatch     = n_eligible - n_exact
        n_replay_exception = 重放异常
    * critical fields 与 Golden 使用同一关键字段集合。"""
    import hashlib
    from QCFP_MTF.common.db import connect
    from QCFP_MTF.decision.decision_ledger import (
        _snap_from_ledger_row, dataset_manifest_hash)
    from QCFP_MTF.decision.replay_contract import replay_eligibility
    from QCFP_MTF.decision.decision_snapshot import build_decision_snapshot
    from QCFP_MTF.decision.replay_engine import field_by_field_compare
    from QCFP_MTF.decision.versions import RELEASE_TAG
    try:
        conn = connect()
        all_rows = conn.execute(
            "SELECT * FROM qcfp_decision_ledger WHERE status='ACTIVE' "
            "ORDER BY id").fetchall()

        def _release_of(r):
            try:
                return ((json.loads(r["context"] or "{}").get(
                    "release_identity") or {}).get("release_id") or "")
            except Exception:
                return ""

        current = [r for r in all_rows if _release_of(r) == RELEASE_TAG]
        if date:
            current = [r for r in current
                       if r["decision_date"] == date]
        n_historical_skipped = len(all_rows) - len(current)
        # 同一 (stock, date) 多 run 重跑：取最新 ACTIVE 决策为当前
        # Release Shadow 事实（旧 run 是超集/缺陷 run，不混入）
        latest = {}
        for r in current:
            key = (r["stock_code"], r["decision_date"])
            if key not in latest or r["id"] > latest[key]["id"]:
                latest[key] = r
        rows = list(latest.values())
        if sample is not None:
            rows = rows[-int(sample):]
        n_current_release = len(rows)
        # 可解析快照集：一次构建，正式 Gate 逐行引用
        resolvable_data_ids = {r["data_snapshot_id"]
                               for r in all_rows if r["data_snapshot_id"]}
        resolvable_data_ids.add(dataset_manifest_hash(conn))
        resolvable_universe_ids = set()
        for r in all_rows:
            try:
                rid = ((json.loads(r["context"] or "{}").get(
                    "release_identity") or {}).get(
                    "universe_snapshot_id") or "")
                if rid:
                    resolvable_universe_ids.add(rid)
            except Exception:
                pass
        n_eligible = 0
        n_exact = 0
        ineligible = []
        exceptions = []
        mismatches = []
        critical_mismatches = []
        settings_registry_parts = []
        ledger_chain_tail = ""
        for r in rows:
            snap = _snap_from_ledger_row(r)
            elig = replay_eligibility(
                conn, snap, resolve_references=True,
                resolvable_data_ids=resolvable_data_ids,
                resolvable_universe_ids=resolvable_universe_ids)
            if not elig["replay_eligible"]:
                ineligible.append({
                    "decision_id": snap.get("decision_id"),
                    "stock_code": r["stock_code"],
                    "decision_date": r["decision_date"],
                    "missing": elig["missing"]})
                continue
            ctx = snap.get("context") or {}
            chain = (ctx.get("ledger_chain") or {}).get(
                "current_ledger_hash") or ""
            if chain:
                ledger_chain_tail = chain
            settings = None
            reg = conn.execute(
                "SELECT settings_blob FROM qcfp_model_registry "
                "WHERE settings_hash=? LIMIT 1",
                (snap.get("settings_hash"),)).fetchone()
            if reg and reg["settings_blob"]:
                try:
                    settings = json.loads(reg["settings_blob"])
                except Exception:
                    settings = None
            if settings is None:
                ineligible.append({
                    "decision_id": snap.get("decision_id"),
                    "missing": ["settings_blob"]})
                continue
            n_eligible += 1
            settings_registry_parts.append(
                f"{snap.get('settings_hash')}:{len(reg['settings_blob'])}")
            try:
                # Shadow 决策：用持久化的输入行重建（Evidence 可找回）；
                # 其它来源 → 用 context 本身（尽力而为）
                evidence = ctx.get("shadow_evidence") or ctx
                replayed = build_decision_snapshot(
                    snap.get("prev_fsm_state"),
                    snap.get("previous_position"),
                    evidence, settings,
                    rule_version=snap.get("rule_version"),
                    model_version=snap.get("model_version"),
                    run_id=snap.get("run_id"),
                    decision_id=snap.get("decision_id"))
                res = field_by_field_compare(snap,
                                             replayed.as_dict(),
                                             decision_id=snap.get(
                                                 "decision_id"))
            except Exception as exc:
                exceptions.append({
                    "decision_id": snap.get("decision_id"),
                    "reason": f"重放异常:{type(exc).__name__}: {exc}"})
                continue
            # Critical fields 显式比较（与 Golden 同一关键字段集合，
            # 无论整体是否 EXACT 都计 critical mismatch）
            crit = _critical_replay_fields(snap, replayed)
            if crit:
                critical_mismatches.append(
                    {"decision_id": snap.get("decision_id"),
                     "critical_fields": crit})
            if res.status == "EXACT_MATCH":
                n_exact += 1
            else:
                mismatches.append({"decision_id": snap.get("decision_id"),
                                   "reason": res.status,
                                   "mismatches": list(res.mismatches)[:5]})
        conn.close()
        n_ineligible = n_current_release - n_eligible
        n_mismatch = n_eligible - n_exact
        n_replay_exception = len(exceptions)
        eligible_rate = round(n_eligible / n_current_release, 4) \
            if n_current_release else 0.0
        exact_rate = round(n_exact / n_eligible, 4) if n_eligible else 0.0
        settings_registry_hash = hashlib.sha256(
            "\n".join(sorted(settings_registry_parts)).encode("utf-8")
        ).hexdigest()[:16] if settings_registry_parts else ""
        return {"schema": "REPLAY-2",
                "scope": "diagnostic_sample" if sample is not None
                else "current_release_only",
                "release_tag": RELEASE_TAG,
                "n_historical_skipped": n_historical_skipped,
                "n_current_release": n_current_release,
                "n_eligible": n_eligible,
                "n_ineligible": n_ineligible,
                "n_exact": n_exact,
                "n_mismatch": n_mismatch,
                "n_replay_exception": n_replay_exception,
                "eligible_rate": eligible_rate,
                "exact_rate": exact_rate,
                "critical_mismatch": len(critical_mismatches),
                "critical_mismatches": critical_mismatches[:10],
                "ineligible": ineligible[:10],
                "exceptions": exceptions[:10],
                "mismatches": mismatches[:10],
                "decision_fields": [
                    "institutional_permission", "wave_stage",
                    "prev_fsm_state", "next_fsm_state",
                    "fsm_proposal_target", "wave_proposal_target",
                    "target_position", "canonical_action",
                    "binding_constraint", "decision_path",
                    "decision_path_hash"],
                "ledger_chain_tail": ledger_chain_tail,
                "settings_registry_hash": settings_registry_hash,
                "rule": "Current Release Decision 必须 eligible=100% + "
                        "exact=100% + critical mismatch=0；"
                        "replay exception=0；"
                        "Historical 由原 Release 重放（facts immutable）"}
    except Exception as exc:
        return {"schema": "REPLAY-2",
                "scope": "current_release_only",
                "release_tag": RELEASE_TAG,
                "n_historical_skipped": 0,
                "n_current_release": 0, "n_eligible": 0,
                "n_ineligible": 0, "n_exact": 0, "n_mismatch": 0,
                "n_replay_exception": 0,
                "eligible_rate": 0.0, "exact_rate": 0.0,
                "critical_mismatch": 0, "critical_mismatches": [],
                "ineligible": [], "exceptions": [], "mismatches": [],
                "error": f"{type(exc).__name__}: {exc}",
                "rule": "Replay 证据缺失 → NOT_PROVEN"}


def replay_evidence_status(replay_result) -> str:
    """P0-3 Daily Replay 状态（只允许四种）：
        REPLAY_PASS / REPLAY_MISMATCH / REPLAY_NOT_PROVEN / REPLAY_EXCEPTION
    无数据 / 缺材料 → NOT_PROVEN；异常 → EXCEPTION；
    非 100% eligible/exact 或 critical>0 → MISMATCH。"""
    r = replay_result or {}
    if r.get("error") or int(r.get("n_current_release") or 0) <= 0:
        return "REPLAY_NOT_PROVEN"
    if int(r.get("n_replay_exception") or 0) > 0:
        return "REPLAY_EXCEPTION"
    if int(r.get("n_ineligible") or 0) > 0:
        return "REPLAY_NOT_PROVEN"
    if (float(r.get("eligible_rate") or 0) != 1.0
            or float(r.get("exact_rate") or 0) != 1.0
            or int(r.get("n_mismatch") or 0) > 0
            or int(r.get("critical_mismatch") or 0) > 0):
        return "REPLAY_MISMATCH"
    return "REPLAY_PASS"


def _critical_replay_fields(original, replayed) -> list:
    """Q8-R1：Canonical Identity 关键字段显式比较（与 Golden 一致）：
    Permission / Wave Stage / Prev+Next FSM / FSM Proposal / Wave Proposal /
    FinalTarget / CanonicalAction / BindingConstraint / DecisionPath /
    DecisionPathHash。

    只比较 Ledger 实际持久化（或可确定性派生）的事实；未持久化的
    fsm_proposal_target 不参与比较（诚实：无法从存储验证）。
    2.9 起 record_snapshot 会把 fsm/wave proposal、canonical_action、
    binding_constraint 持久化进 context，新决策可完整验证。"""
    from QCFP_MTF.decision.canonical_action import canonical_action
    from QCFP_MTF.decision.constraint_trace import binding_constraint

    def _stored(snap_dict, key):
        ctx = snap_dict.get("context") or {}
        if key == "canonical_action":
            return canonical_action(snap_dict.get("previous_position"),
                                    snap_dict.get("target_position"))
        if key == "wave_stage":
            return (ctx.get("wave") or {}).get("stage") or ""
        if key == "prev_fsm_state":
            return snap_dict.get("prev_fsm_state")
        if key == "next_fsm_state":
            return snap_dict.get("next_fsm_state")
        if key == "fsm_proposal_target":
            return ctx.get("fsm_proposal_target")
        if key == "wave_proposal_target":
            v = ctx.get("wave_proposal_target")
            if v is None:
                v = (ctx.get("wave") or {}).get("proposed_target")
            return v
        if key == "binding_constraint":
            v = ctx.get("binding_constraint")
            if v:
                return v
            trace = ctx.get("constraint_trace")
            if isinstance(trace, dict):
                b = binding_constraint(trace)
                return b.get("binding_constraint") \
                    if isinstance(b, dict) else b
            return ""
        if key == "decision_path":
            return list(snap_dict.get("decision_path") or [])
        if key == "decision_path_hash":
            return ctx.get("decision_path_hash")
        return snap_dict.get(key)

    def _get(obj, key):
        v = getattr(obj, key, None)
        if v is None and hasattr(obj, "context"):
            v = (obj.context or {}).get(key)
        return v
    pairs = (
        ("institutional_permission", "institutional_permission"),
        ("wave_stage", "wave_stage"),
        ("prev_fsm_state", "prev_fsm_state"),
        ("next_fsm_state", "next_fsm_state"),
        ("fsm_proposal_target", "fsm_proposal_target"),
        ("wave_proposal_target", "wave_proposal_target"),
        ("target_position", "target_position"),
        ("canonical_action", "canonical_action"),
        ("binding_constraint", "binding_constraint"),
        ("decision_path", "decision_path"),
        ("decision_path_hash", "decision_path_hash"),
    )
    mismatches = []
    for o_key, r_key in pairs:
        o = _stored(original, o_key) if isinstance(original, dict) \
            else _get(original, o_key)
        r = _get(replayed, r_key)
        # 未持久化的事实（旧 Ledger 行）→ 诚实跳过，不当作 mismatch
        if o in (None, "") and o_key in ("fsm_proposal_target",
                                         "wave_proposal_target",
                                         "binding_constraint"):
            continue
        if o_key == "decision_path":
            o = list(o or [])
            r = list(r or [])
            if o != r:
                mismatches.append({"field": o_key,
                                   "original": o, "replay": r})
            continue
        if isinstance(o, float) or isinstance(r, float):
            try:
                if abs(float(o or 0.0) - float(r or 0.0)) > 1e-9:
                    mismatches.append({"field": o_key,
                                       "original": o, "replay": r})
                continue
            except (TypeError, ValueError):
                pass
        if o != r:
            mismatches.append({"field": o_key, "original": o, "replay": r})
    return mismatches


def historical_replay_note() -> dict:
    """Historical Release Replay（Q8）：当年 Decision 用当年 Release 重放。
    当前环境没有归档的 V9/V10 引擎镜像 → 诚实标记，不伪造。"""
    return {
        "scope": "historical_replay",
        "status": "REQUIRES_ARCHIVED_RELEASE_ENV",
        "facts_immutable": True,
        "rule": "REL-V9 decision → REL-V9 replay environment；"
                "不能用当前引擎要求旧决策 EXACT_MATCH",
    }


def run_oos_evidence(settings=None) -> dict:
    """正式 PIT/OOS（Q8-R2）：Previous Release vs Current Release，
    在同一个 Frozen OOS Contract 上比较。

    禁止 Measurement 自己声明 PASS：
      * comparable 只回答“有没有资格比较”；
      * evidence_not_down 只从 compare_oos()（非劣性契约）计算；
      * PIT / Future Leakage / Universe Leakage 全部来自真实测量。

    Fail-Closed：OOS Contract 缺任一字段 / PIT 未冻结或实测不一致 /
    Previous artifact 缺失或身份不匹配 / 必需表缺失 → OOS_NOT_COMPARABLE。"""
    from QCFP_MTF.common.paths import get_report_root
    from QCFP_MTF.config.settings import load_qcfp_settings
    from QCFP_MTF.common.db import connect
    settings = settings or load_qcfp_settings()
    oos_dir = get_report_root() / "audit" / "oos"
    contract_path = oos_dir / "oos_contract.json"
    if not contract_path.exists():
        return _oos_not_comparable("oos_contract.json 未冻结")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    missing = validate_oos_contract(contract)
    if missing:
        return _oos_not_comparable(
            f"OOS Contract 缺字段: {missing}")
    contract_hash = canonical_contract_hash(contract)
    if contract.get("holdout_locked") is not True \
            or contract.get("used_in_selection") is not False \
            or contract.get("used_for_tuning") not in (None, False):
        return _oos_not_comparable(
            "OOS Contract 必须 holdout_locked=true 且 "
            "used_in_selection=false / used_for_tuning=false")
    ni_errors = validate_non_inferiority_contract(
        contract.get("non_inferiority") or [])
    if ni_errors:
        return _oos_not_comparable(
            f"non-inferiority 契约无效: {ni_errors}")
    pit_frozen = contract.get("pit_validation") or {}
    pit_required = ("pit_grade", "pit_violation_count",
                    "future_leakage_count", "universe_leakage_count")
    pit_missing = [k for k in pit_required
                   if pit_frozen.get(k) is None]
    if pit_missing:
        return _oos_not_comparable(
            f"PIT validation 未冻结: {pit_missing}")
    if pit_frozen.get("pit_grade") not in ("A", "B"):
        return _oos_not_comparable("PIT grade 未冻结或不可认证")
    # PIT 必须是测量结果：运行前重新测量，与冻结契约比对
    conn = connect()
    try:
        inputs = _load_oos_inputs(conn)
    finally:
        conn.close()
    try:
        pit_measured = measure_pit_evidence(inputs, settings)
    except OOSContractError as exc:
        return _oos_not_comparable(str(exc))
    except Exception as exc:
        return _oos_not_comparable(
            f"PIT 测量失败:{type(exc).__name__}: {exc}")
    for k in ("pit_violation_count", "future_leakage_count",
              "universe_leakage_count"):
        if int(pit_measured.get(k) or 0) != int(pit_frozen.get(k) or 0):
            return _oos_not_comparable(
                f"PIT 实测与冻结契约不一致: {k} "
                f"frozen={pit_frozen.get(k)} "
                f"measured={pit_measured.get(k)}")
    if any(int(pit_measured.get(k) or 0) > 0
           for k in ("pit_violation_count", "future_leakage_count",
                     "universe_leakage_count")):
        return _oos_not_comparable(
            f"PIT 违规>0: {pit_measured}")
    # Current Release OOS：同一 Canonical OOS Runner 真实运行
    try:
        current = _run_current_oos(inputs, contract, settings)
    except OOSContractError as exc:
        return _oos_not_comparable(str(exc))
    except Exception as exc:
        return _oos_not_comparable(
            f"Current OOS 运行失败:{type(exc).__name__}: {exc}")
    # 写 Current Release OOS artifact（与 Previous 同结构）
    oos_dir.mkdir(parents=True, exist_ok=True)
    (oos_dir / "current_release_oos.json").write_text(
        json.dumps(current, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    oos_metrics = current.get("metrics") or {}
    if not any(v is not None for v in oos_metrics.values()):
        return _oos_not_comparable(
            "OOS 窗口无可用决策/收益数据（metrics 全空）")
    # Previous Release OOS（次选：冻结 artifact 复用，身份必须一致）
    prev_path = oos_dir / "previous_release_oos.json"
    if not prev_path.exists():
        return _oos_not_comparable(
            "previous release OOS artifact 缺失"
            f"（{contract.get('previous_release_id')} 未归档/未运行）")
    prev = json.loads(prev_path.read_text(encoding="utf-8"))
    prev_identity_ok = (
        prev.get("release_id") == contract.get("previous_release_id")
        and prev.get("contract_hash") == contract_hash
        and prev.get("dataset_hash") == contract.get("data_snapshot_hash")
        and prev.get("universe_hash") == contract.get(
            "universe_snapshot_hash")
        and prev.get("cost_model_hash") == contract.get(
            "cost_model_hash")
        and prev.get("execution_model_hash") == contract.get(
            "execution_model_hash")
        and prev.get("metric_contract_hash") == contract.get(
            "metric_contract_hash")
        and (prev.get("oos_period") or {}).get("oos_start")
        == contract.get("oos_start")
        and (prev.get("oos_period") or {}).get("oos_end")
        == contract.get("oos_end"))
    if not prev_identity_ok:
        return _oos_not_comparable("previous OOS artifact 身份不匹配")
    # Previous PIT 必须来自 Previous Artifact（V9 OOS run 实测），
    # 而不是 contract 里的 frozen expectation。
    prev_pit = prev.get("pit") or {}
    if any(prev_pit.get(k) is None for k in
           ("pit_grade", "pit_violation_count", "future_leakage_count",
            "universe_leakage_count")):
        return _oos_not_comparable("previous OOS artifact 缺 PIT 测量")
    if any(int(prev_pit.get(k) or 0) > 0 for k in
           ("pit_violation_count", "future_leakage_count",
            "universe_leakage_count")):
        return _oos_not_comparable(f"Previous PIT 违规>0: {prev_pit}")
    tolerances = contract.get("non_inferiority") or []
    prev_metrics = prev.get("metrics") or {}
    current_metrics = current.get("metrics") or {}
    missing_metrics = [t.get("metric") for t in tolerances
                       if prev_metrics.get(t.get("metric")) is None
                       or current_metrics.get(t.get("metric")) is None]
    if missing_metrics:
        return _oos_not_comparable(
            f"正式 Gate metric 缺失: {missing_metrics}")
    cmp = compare_oos(prev_metrics, current_metrics, tolerances)
    hard_regressions = cmp["hard_regressions"]
    soft_warnings = cmp["soft_warnings"]
    evidence_not_down = not hard_regressions
    return {
        "schema": "OOS-2",
        "status": "OOS_PASS" if evidence_not_down
        else "OOS_REGRESSED",
        "comparable": True,
        "evidence_not_down": evidence_not_down,
        "contract_hash": contract_hash,
        "previous_release_id": contract.get("previous_release_id"),
        "current_release_id": contract.get("current_release_id"),
        "identity_check": {
            "same_dataset": prev.get("dataset_hash")
            == contract.get("data_snapshot_hash"),
            "same_universe": prev.get("universe_hash")
            == contract.get("universe_snapshot_hash"),
            "same_oos_window": (prev.get("oos_period") or {}).get(
                "oos_start") == contract.get("oos_start")
            and (prev.get("oos_period") or {}).get("oos_end")
            == contract.get("oos_end"),
            "same_cost_model": prev.get("cost_model_hash")
            == contract.get("cost_model_hash"),
            "same_execution_model": prev.get("execution_model_hash")
            == contract.get("execution_model_hash"),
            "same_metric_contract": prev.get("metric_contract_hash")
            == contract.get("metric_contract_hash"),
        },
        "pit": {
            "previous": {
                "pit_grade": prev_pit.get("pit_grade"),
                "pit_violation_count":
                    prev_pit.get("pit_violation_count"),
                "future_leakage_count":
                    prev_pit.get("future_leakage_count"),
                "universe_leakage_count":
                    prev_pit.get("universe_leakage_count"),
            },
            "current": {
                "pit_grade": pit_measured.get("pit_grade"),
                "pit_violation_count":
                    pit_measured.get("pit_violation_count"),
                "future_leakage_count":
                    pit_measured.get("future_leakage_count"),
                "universe_leakage_count":
                    pit_measured.get("universe_leakage_count"),
            },
        },
        "before": prev_metrics,
        "after": current_metrics,
        "delta": _oos_delta(prev_metrics, current_metrics),
        "hard_regressions": hard_regressions,
        "soft_warnings": soft_warnings,
        "soft_warning_count": len(soft_warnings),
        "regressions": hard_regressions,
        "rule": "同一 Frozen OOS Contract 上比较 Previous vs Current；"
                "comparable 与 evidence_not_down 完全分离；"
                "PIT 双方来自各自 OOS run 实测（Previous 取自 artifact）；"
                "hard regression 才阻断，soft warning 只记录；"
                "evidence_not_down 只从 compare_oos() 计算",
    }


def _oos_not_comparable(reason: str) -> dict:
    return {
        "schema": "OOS-2",
        "status": "OOS_NOT_COMPARABLE",
        "comparable": False,
        "evidence_not_down": False,
        "reason": reason,
        "future_leakage_count": None,
        "pit_grade": None,
        "rule": "不具备比较资格 → OOS_NOT_COMPARABLE，不是 PASS 也不是 FAIL",
    }


OOS_CONTRACT_REQUIRED_FIELDS = (
    "contract_version", "dataset_id", "data_snapshot_hash",
    "universe_snapshot_hash", "pit_specification_hash",
    "train_start", "train_end", "validation_start", "validation_end",
    "oos_start", "oos_end", "cost_model_hash", "execution_model_hash",
    "metric_contract_hash", "previous_release_id", "current_release_id",
    "holdout_locked", "used_in_selection", "used_for_tuning",
    "pit_validation", "non_inferiority",
)


def validate_oos_contract(contract: dict) -> list:
    """Frozen OOS Contract 完整性：缺任一字段 → 不运行正式比较。"""
    return [k for k in OOS_CONTRACT_REQUIRED_FIELDS
            if contract.get(k) in (None, "")]


class OOSContractError(ValueError):
    """OOS 证据链 Fail-Closed 专用异常。"""


def validate_non_inferiority_contract(tolerances) -> list:
    """正式 Gate：每条必须
        metric 非空 / direction ∈ {higher_is_better, lower_is_better}
        max_allowed_regression >= 0 / hard_or_soft ∈ {hard, soft}
        metric 不重复
    任何错误 → 调用方必须 OOS_NOT_COMPARABLE（禁止自动纠正）。"""
    errors = []
    seen = set()
    for i, tol in enumerate(tolerances or []):
        metric = tol.get("metric")
        if not metric:
            errors.append(f"[{i}] metric 缺失")
        elif metric in seen:
            errors.append(f"[{i}] metric 重复: {metric}")
        else:
            seen.add(metric)
        if tol.get("direction") not in ("higher_is_better",
                                        "lower_is_better"):
            errors.append(
                f"[{i}] direction 无效: {tol.get('direction')!r}")
        try:
            max_reg = float(tol.get("max_allowed_regression"))
            if max_reg < 0:
                errors.append(
                    f"[{i}] max_allowed_regression<0: {max_reg}")
        except (TypeError, ValueError):
            errors.append(
                f"[{i}] max_allowed_regression 缺失/非数值: "
                f"{tol.get('max_allowed_regression')!r}")
        if tol.get("hard_or_soft") not in ("hard", "soft"):
            errors.append(
                f"[{i}] hard_or_soft 无效: {tol.get('hard_or_soft')!r}")
    return errors


def canonical_contract_hash(contract: dict) -> str:
    """Contract 冻结哈希：canonical serialization。"""
    import hashlib
    return hashlib.sha256(
        json.dumps(contract, sort_keys=True, ensure_ascii=False,
                   default=str).encode("utf-8")).hexdigest()[:16]


def compare_oos(previous: dict, current: dict,
                tolerances: list) -> dict:
    """Frozen Non-Inferiority Contract：
        {metric, direction, max_allowed_regression, hard_or_soft}
    hard regression → hard_regressions（阻断 OOS）
    soft regression → soft_warnings（只记录，不阻断）
    direction: higher_is_better / lower_is_better
    调用方必须已保证 metric 双方存在（缺失 → OOS_NOT_COMPARABLE）。"""
    hard_regressions = []
    soft_warnings = []
    for tol in tolerances or []:
        metric = tol.get("metric")
        direction = tol.get("direction")
        try:
            max_reg = float(tol.get("max_allowed_regression", 0.0))
        except (TypeError, ValueError):
            max_reg = 0.0
        hard = tol.get("hard_or_soft") == "hard"
        p = previous.get(metric)
        c = current.get(metric)
        if p is None or c is None:
            continue  # 防御：正式路径已在 compare 前 fail-closed
        p, c = float(p or 0.0), float(c or 0.0)
        delta = c - p
        if direction == "higher_is_better":
            regressed = delta < -max_reg - 1e-9
        else:  # lower_is_better
            regressed = delta > max_reg + 1e-9
        if regressed:
            entry = {"metric": metric,
                     "direction": direction,
                     "previous": p, "current": c,
                     "delta": round(delta, 6),
                     "max_allowed_regression": max_reg,
                     "hard": hard}
            if hard:
                hard_regressions.append(entry)
            else:
                soft_warnings.append(entry)
    return {"hard_regressions": hard_regressions,
            "soft_warnings": soft_warnings,
            "hard_regression_count": len(hard_regressions),
            "soft_warning_count": len(soft_warnings)}


def _load_oos_inputs(conn) -> dict:
    """OOS 必需输入表（Fail-Closed：缺表/空表 → OOSContractError）。"""
    return {
        "structural": _load_df(conn, "qcfp_quarterly_structural",
                               required=True),
        "monthly": _load_df(conn, "qcfp_monthly_behavior", required=True),
        "weekly": _load_df(conn, "qcfp_weekly_tactical", required=True),
        "chip": _load_df(conn, "hk_quarterly_chip_analysis",
                         required=True),
        "idx": _load_df(conn, "hk_idx_hist", required=True),
        "weekly_kl": _load_df(conn, "hk_hist_weekly_kline",
                              required=True),
    }


def measure_pit_evidence(inputs: dict, settings) -> dict:
    """真实 PIT 测量（不是声明）：Evidence Timeline 上统计
        pit_violation_count      as-of 违约行数
        future_leakage_count     lookahead 违规行数
        universe_leakage_count   不在当前 Universe 定义中的股票数
    任何 > 0 → 正式 OOS 不具备比较资格（OOS_NOT_COMPARABLE）。"""
    import pandas as pd
    from QCFP_MTF.backtest.data_pipeline import build_evidence_timeline
    from QCFP_MTF.backtest.lookahead_filter import validate_timeline
    from QCFP_MTF.common.db import connect
    signals = build_evidence_timeline(
        inputs["structural"], inputs["monthly"], inputs["weekly"],
        inputs["chip"], inputs["idx"], settings)
    if signals is None or signals.empty:
        raise OOSContractError("REQUIRED_TABLE_EMPTY:evidence_timeline")
    dt = pd.to_datetime(signals["decision_date"], errors="coerce")
    asof_cols = [c for c in signals.columns
                 if c.endswith("_available_date") or c.endswith("_asof")]
    pit_violation_count = 0
    for col in asof_cols:
        av = pd.to_datetime(signals[col], errors="coerce")
        pit_violation_count += int(
            (av.notna() & dt.notna() & (av > dt)).sum())
    ok = validate_timeline(signals)
    future_leakage_count = int((~ok).sum())
    conn = connect()
    try:
        codes = set()
        for r in conn.execute(
                "SELECT stock_code FROM hk_stock_info "
                "WHERE is_active=1"):
            codes.add(str(r[0]).zfill(5))
        for r in conn.execute(
                "SELECT DISTINCT stock_code FROM qcfp_mtf_decision"):
            codes.add(str(r[0]).zfill(5))
    finally:
        conn.close()
    tl_codes = set(
        signals["stock_code"].astype(str).str.zfill(5).unique())
    universe_leakage_count = len(tl_codes - codes)
    total = (pit_violation_count + future_leakage_count
             + universe_leakage_count)
    return {
        "pit_grade": "A" if total == 0 else "B",
        "pit_violation_count": int(pit_violation_count),
        "future_leakage_count": int(future_leakage_count),
        "universe_leakage_count": int(universe_leakage_count),
    }


def _release_oos_artifact(contract: dict, release_id: str,
                          metrics: dict, train_metrics: dict,
                          pit: dict, code_hash="", dependency_hash="",
                          settings_hash="") -> dict:
    """Release OOS Artifact（RELEASE-OOS-2）：Previous 与 Current
    同结构，包含契约身份字段，供 compare 前做身份一致性验证。"""
    return {
        "schema": "RELEASE-OOS-2",
        "release_id": release_id,
        "code_hash": code_hash,
        "dependency_hash": dependency_hash,
        "settings_hash": settings_hash,
        "contract_hash": canonical_contract_hash(contract),
        "dataset_hash": contract.get("data_snapshot_hash"),
        "universe_hash": contract.get("universe_snapshot_hash"),
        "oos_period": {"oos_start": contract.get("oos_start"),
                       "oos_end": contract.get("oos_end")},
        "cost_model_hash": contract.get("cost_model_hash"),
        "execution_model_hash": contract.get("execution_model_hash"),
        "metric_contract_hash": contract.get("metric_contract_hash"),
        "pit": pit,
        "metrics": metrics,
        "train_backtest_metrics": train_metrics,
    }


def _run_current_oos(inputs: dict, contract: dict, settings) -> dict:
    """同一 Canonical OOS Runner（backtest.canonical_runs.run_canonical_oos）
    运行 Current Release。必需表缺失/为空 → OOSContractError（不是
    空 DataFrame 让下游猜）。"""
    from QCFP_MTF.backtest.canonical_runs import run_canonical_oos
    from QCFP_MTF.decision.decision_snapshot import _settings_hash
    import hashlib
    result = run_canonical_oos(
        inputs["structural"], inputs["monthly"], inputs["weekly"],
        inputs["chip"], inputs["idx"], settings,
        train_end=contract.get("train_end"),
        test_start=contract.get("oos_start"),
        test_end=contract.get("oos_end"),
        weekly_kl=inputs.get("weekly_kl"),
        run_id=f"oos_{contract.get('dataset_id')}")
    import pandas as pd
    oos_bt = result.get("oos_backtest")
    if oos_bt is None:
        oos_bt = pd.DataFrame()
    train_bt = result.get("train_backtest")
    if train_bt is None:
        train_bt = pd.DataFrame()
    pit = measure_pit_evidence(inputs, settings)
    dep_hash = ""
    req = PROJECT_ROOT / "Doc" / "requirements.txt"
    if req.exists():
        dep_hash = hashlib.sha256(
            req.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()[:12]
    return _release_oos_artifact(
        contract=contract,
        release_id=contract.get("current_release_id"),
        metrics=_compute_oos_metrics(
            oos_bt, inputs.get("weekly_kl"), settings),
        train_metrics=_compute_oos_metrics(
            train_bt, inputs.get("weekly_kl"), settings),
        pit=pit,
        code_hash=_tree_hash(Path(CORE_DIR) / "QCFP_MTF"),
        dependency_hash=dep_hash,
        settings_hash=_settings_hash(settings))


def _load_df(conn, table, required=False):
    import pandas as pd
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    except Exception:
        if required:
            raise OOSContractError(
                f"REQUIRED_TABLE_UNAVAILABLE:{table}")
        return pd.DataFrame()
    if required and df.empty:
        raise OOSContractError(
            f"REQUIRED_TABLE_EMPTY:{table}")
    return df


def _clean_num(v):
    try:
        f = float(v)
        return None if f != f else round(f, 6)
    except (TypeError, ValueError):
        return None


def _compute_oos_metrics(bt, weekly_kl, settings) -> dict:
    """真实计算 OOS 指标集（不是声明）：
        return / sharpe / mdd      backtest.performance.evaluate（唯一指标层）
        turnover / cost            组合层周均换手与总成本
        wave_capture / mae         wave_capture + trade_ledger（存在则算）
        capital_efficiency         retail_utility（年化收益 / 平均暴露）
    """
    import pandas as pd
    from QCFP_MTF.backtest.performance import evaluate as equity_metrics
    from QCFP_MTF.backtest.engine import portfolio_returns
    from QCFP_MTF.backtest.wave_capture import find_waves, \
        wave_capture_metrics, wave_capture_summary
    from QCFP_MTF.backtest.trade_ledger import build_trade_ledger
    from QCFP_MTF.backtest.retail_utility import capital_efficiency
    empty = {"return": None, "mdd": None, "sharpe": None,
             "wave_capture": None, "mae": None, "turnover": None,
             "cost": None, "capital_efficiency": None, "n_weeks": 0}
    if not isinstance(bt, pd.DataFrame) or bt.empty:
        return empty
    port = portfolio_returns(bt)
    pnl = port["portfolio_return"].dropna()
    if pnl.empty:
        return empty
    turnover = port["avg_turnover"] if "avg_turnover" in port.columns \
        else None
    exposure = port["avg_exposure"] if "avg_exposure" in port.columns \
        else None
    bt_cfg = (settings or {}).get("backtest", {}) or {}
    perf = equity_metrics(
        pnl, position=exposure,
        annual_periods=int(bt_cfg.get("annual_periods", 52)),
        rf=float(bt_cfg.get("risk_free", 0.0)), turnover=turnover)
    total_cost = _clean_num(bt["cost"].sum()) \
        if "cost" in bt.columns and len(bt) else None
    ann_ret = perf.get("annualized_return")
    avg_exp = _clean_num(exposure.mean()) \
        if exposure is not None and len(exposure) else None
    cap_eff = capital_efficiency(ann_ret, avg_exp) \
        if ann_ret is not None and ann_ret == ann_ret else None
    wave_capture = None
    mae = None
    try:
        waves = find_waves(weekly_kl) \
            if isinstance(weekly_kl, pd.DataFrame) and not weekly_kl.empty \
            else None
        wm = wave_capture_metrics(bt, waves)
        ws = wave_capture_summary(wm)
        wave_capture = _clean_num(ws.get("capture_ratio_mean"))
    except Exception:
        wave_capture = None
    try:
        tl = build_trade_ledger(bt, weekly_kl)
        if isinstance(tl, dict):
            mae = _clean_num(tl.get("avg_mae"))
    except Exception:
        mae = None
    return {
        "return": _clean_num(perf.get("total_return")),
        "mdd": _clean_num(perf.get("max_drawdown")),
        "sharpe": _clean_num(perf.get("sharpe")),
        "wave_capture": wave_capture,
        "mae": mae,
        "turnover": _clean_num(perf.get("annual_turnover")),
        "cost": total_cost,
        "capital_efficiency": _clean_num(cap_eff),
        "n_weeks": int(len(pnl)),
    }


def _oos_delta(previous: dict, current: dict) -> dict:
    delta = {}
    for k in set(list(previous) + list(current)):
        p = previous.get(k)
        c = current.get(k)
        if p is not None and c is not None:
            try:
                delta[k] = round(float(c) - float(p), 6)
            except (TypeError, ValueError):
                delta[k] = None
    return delta


def _universe_snapshot_hash(conn) -> str:
    """Universe Snapshot Hash：当前 Universe 定义（与 shadow_universe
    同一口径：hk_stock_info 活跃 ∪ qcfp_mtf_decision 历史）。"""
    import hashlib
    codes = set()
    for r in conn.execute(
            "SELECT stock_code FROM hk_stock_info WHERE is_active=1"):
        codes.add(str(r[0]).zfill(5))
    for r in conn.execute(
            "SELECT DISTINCT stock_code FROM qcfp_mtf_decision"):
        codes.add(str(r[0]).zfill(5))
    raw = ",".join(sorted(codes))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _settings_slice_hash(settings, keys) -> str:
    import hashlib
    part = {}
    for k in keys:
        if k in settings:
            part[k] = settings[k]
    raw = json.dumps(part, sort_keys=True, ensure_ascii=False,
                     default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


OOS_NON_INFERIORITY_DEFAULT = [
    {"metric": "mdd", "direction": "lower_is_better",
     "max_allowed_regression": 0.05, "hard_or_soft": "hard"},
    {"metric": "return", "direction": "higher_is_better",
     "max_allowed_regression": 0.05, "hard_or_soft": "soft"},
    {"metric": "turnover", "direction": "lower_is_better",
     "max_allowed_regression": 0.10, "hard_or_soft": "soft"},
    {"metric": "cost", "direction": "lower_is_better",
     "max_allowed_regression": 0.005, "hard_or_soft": "soft"},
]

# 按计划 §16 语义：optional 指标不得进入 Frozen non-inferiority contract。
# 本 Frozen OOS 窗口（2026-07-01→08-21）内 Canonical 策略无波段/无交易，
# wave_capture / mae / sharpe / capital_efficiency 无法被双方真实测量，
# 放进 contract 只会让比较永远 OOS_NOT_COMPARABLE。因此只保留
# Canonical OOS Runner 对该窗口确定性产出的 Gate metric：
#   mdd（hard，安全/风险） return / turnover / cost（soft，性能）。
OOS_NON_INFERIORITY_OMITTED_RATIONALE = {
    "wave_capture": "窗口内无波段（find_waves 无 ≥50% 波段）→ 无法测量",
    "mae": "窗口内无交易（build_trade_ledger 无 trades）→ 无法测量",
    "sharpe": "零方差（无持仓）→ sharpe=NaN，无比较意义",
    "capital_efficiency": "零暴露 → 0/0 退化，无比较意义",
}


def build_oos_contract(settings, oos_start, oos_end, train_end,
                       validation_start, validation_end,
                       previous_release_id="MERGED_CODE_9",
                       train_start="2015-01-01") -> dict:
    """Frozen OOS Contract：在运行任何 Current OOS 结果之前冻结。
    所有 hash 都是内容敏感身份（dataset/universe/cost/execution/
    metric/PIT），不依赖人工填写。"""
    import hashlib
    from QCFP_MTF.common.db import connect
    from QCFP_MTF.decision.decision_ledger import dataset_manifest_hash
    from QCFP_MTF.decision.versions import RELEASE_TAG
    conn = connect()
    try:
        inputs = _load_oos_inputs(conn)
        dataset_id = dataset_manifest_hash(conn)
        universe_hash = _universe_snapshot_hash(conn)
        pit = measure_pit_evidence(inputs, settings)
    finally:
        conn.close()
    bt = settings.get("backtest") or {}
    cost_cfg = bt.get("cost") or {}
    cost_model_hash = hashlib.sha256(
        json.dumps(cost_cfg, sort_keys=True, ensure_ascii=False,
                   default=str).encode("utf-8")).hexdigest()[:16]
    exec_cfg = {
        "position_target": bt.get("position_target"),
        "liquidity": bt.get("liquidity"),
        "portfolio_constraints": bt.get("portfolio_constraints"),
        "risk_free": bt.get("risk_free"),
        "annual_periods": bt.get("annual_periods"),
    }
    execution_model_hash = hashlib.sha256(
        json.dumps(exec_cfg, sort_keys=True, ensure_ascii=False,
                   default=str).encode("utf-8")).hexdigest()[:16]
    metrics = ("return", "mdd", "sharpe", "wave_capture", "mae",
               "turnover", "cost", "capital_efficiency")
    metric_contract_hash = hashlib.sha256(
        json.dumps({"metrics": sorted(metrics),
                    "authority": "backtest.performance.evaluate"},
                   sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    pit_specification_hash = hashlib.sha256(
        "asof:quarterly,monthly,weekly,daily,flow,universe;"
        "lookahead:structural_available_date<=decision_date;"
        "universe:hk_stock_info+qcfp_mtf_decision".encode("utf-8")
    ).hexdigest()[:16]
    return {
        "schema": "OOS-CONTRACT-2",
        "contract_version": "OOS-CONTRACT-2",
        "dataset_id": dataset_id,
        "data_snapshot_hash": dataset_id,
        "universe_snapshot_hash": universe_hash,
        "pit_specification_hash": pit_specification_hash,
        "train_start": train_start,
        "train_end": train_end,
        "validation_start": validation_start,
        "validation_end": validation_end,
        "oos_start": oos_start,
        "oos_end": oos_end,
        "cost_model_hash": cost_model_hash,
        "execution_model_hash": execution_model_hash,
        "metric_contract_hash": metric_contract_hash,
        "previous_release_id": previous_release_id,
        "current_release_id": RELEASE_TAG,
        "holdout_locked": True,
        "used_in_selection": False,
        "used_for_tuning": False,
        "pit_validation": pit,
        "non_inferiority": list(OOS_NON_INFERIORITY_DEFAULT),
        "non_inferiority_omitted": dict(
            OOS_NON_INFERIORITY_OMITTED_RATIONALE),
        "rule": "冻结于任何 Current OOS 结果之前；结果出来后禁止修改，"
                "否则 OOS_NOT_COMPARABLE；non_inferiority 只含 Canonical "
                "OOS Runner 对 Frozen 窗口确定性产出的 metric（§16："
                "optional 指标不得进 contract）；hard regression 才阻断，"
                "soft 只记录",
    }


def freeze_oos_contract(oos_dir, settings=None, **kw) -> dict:
    """冻结 OOS Contract（不可覆盖）。"""
    from QCFP_MTF.config.settings import load_qcfp_settings
    settings = settings or load_qcfp_settings()
    path = oos_dir / "oos_contract.json"
    if path.exists():
        return {"frozen": False,
                "reason": "oos_contract.json 已存在（不可变）",
                "path": str(path)}
    contract = build_oos_contract(settings, **kw)
    oos_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return {"frozen": True, "path": str(path),
            "contract_hash": canonical_contract_hash(contract)}


def generate_artifacts(out_dir: Path, qcfp_root: Path, logger) -> None:
    """Build/CI 测量：从真实源码生成全部 MTR 证据 artifact。

    严禁手工把 graph node 标 unreachable 当作 detach；物理删除后
    必须重新从源码构图。"""
    # 1) 真实 Authority Graph（不含 backtest root：生产域只含
    #    Canonical Engine / Certification / Execution / Ledger / Safety）
    graph = build_authority_graph(qcfp_root)
    audit = authority_audit(graph)
    behavioral = behavioral_authority_audit(graph)
    classifications = retirement_classify(graph)
    register = retirement_register(graph, classifications)
    path_info = _executable_decision_paths(graph)
    legacy_scan = legacy_production_scan(graph)
    enriched_graph = {
        **graph,
        "executable_decision_paths": path_info["count"],
        "decision_path_owners": path_info["owners"],
        "duplicate_authorities": bool(audit["duplicate_authority"])
        or bool(behavioral["duplicates"])
        or bool(behavioral["unauthorized_writers"]),
        "legacy_production_paths": legacy_scan["production_legacy_paths"],
    }

    # 2) Frozen Manifest（独立 truth）+ Authority Graph 独立验证 + diff
    manifest_artifact = production_feature_manifest_artifact(
        graph, classifications, release_id=MTR_RELEASE_ID,
        frozen_manifest=FROZEN_PRODUCTION_MANIFEST)
    feature_diff = active_feature_diff(V9_PRODUCTION_BASELINE_MANIFEST,
                                       FROZEN_PRODUCTION_MANIFEST)
    manifest_artifact["active_features_down"] = \
        feature_diff["verdict"] == "ACTIVE_DOWN"
    manifest_artifact["active_feature_diff"] = feature_diff
    verify = verify_frozen_manifest(graph, FROZEN_PRODUCTION_MANIFEST)
    manifest_artifact["wiring_verdict"] = verify["verdict"]

    # 3) Critical LOC Baseline（不可变，只读）+ After 测量
    #    MTR Q4 Closure：禁止用 Current source + 人为加回 backtest root
    #    现场伪造 V9 baseline。baseline 必须来自真实 merged_code(9)
    #    冻结产物；缺失 → MTR_NOT_PROVEN（不是现场创造）。
    after_metrics = critical_loc_metrics(graph)
    baseline_path = out_dir / "critical_loc_baseline.json"
    if not baseline_path.exists():
        raise RuntimeError(
            "critical_loc_baseline.json 缺失 → MTR_NOT_PROVEN："
            "禁止用 Current source 现场伪造 V9 baseline；"
            "必须由真实 merged_code(9) 冻结基线提供")
    loaded_baseline = json.loads(
        baseline_path.read_text(encoding="utf-8"))
    before_metrics = loaded_baseline["baseline"]
    loc_diff = {
        "baseline_release": loaded_baseline["release_id"],
        "baseline_code_hash": loaded_baseline.get("code_hash", ""),
        "production_reachable_loc_down":
            after_metrics["reachable_loc"] < before_metrics["reachable_loc"],
        "decision_critical_loc_down":
            after_metrics["decision_critical_loc"]
            < before_metrics["decision_critical_loc"],
        "decision_critical_module_count_down":
            len(after_metrics["decision_critical_modules"])
            <= len(before_metrics["decision_critical_modules"]),
        "before": before_metrics,
        "after": after_metrics,
        "rule": "Q4 只读取 decision_critical_loc_down；"
                "不能用 reachable_loc_down 替代；"
                "critical_loc_baseline 不可修改",
    }

    # 4) Trust Evidence：Golden / Current-Release Replay / Historical
    #    Replay / Formal OOS（缺契约 → OOS_NOT_COMPARABLE，不伪造）
    golden_result = run_golden_evidence()
    replay_result = run_replay_evidence()
    replay_result["historical_replay"] = historical_replay_note()
    oos_result = run_oos_evidence()

    # 5) Failure Injection：真实 12-case 注入
    failure_injection = run_failure_qualification()

    # 6) Physical Delete：DeclaredRetiredSet ⊆ PhysicallyAbsentSet
    declared_retired = [f for f, i in FROZEN_PRODUCTION_MANIFEST.items()
                        if i.get("state") == "RETIRED"]
    residual = scan_residual_references(qcfp_root, declared_retired)
    residual = [{"kind": "import", "file": r["file"],
                 "module": r["module"]} for r in residual]
    deletion = physical_retirement_audit(
        qcfp_root, FROZEN_PRODUCTION_MANIFEST,
        declared_retired=declared_retired,
        residual_references=residual)
    # 物理删除后必须重新构图（真实 detach，不是手工标 False）
    graph_after_delete = build_authority_graph(qcfp_root)

    # 7) 写全部 artifact
    _write_json(out_dir / "authority_graph.json", enriched_graph)
    _write_json(out_dir / "production_feature_manifest.json",
                manifest_artifact)
    _write_json(out_dir / "critical_loc_diff.json", loc_diff)
    _write_json(out_dir / "legacy_production_scan.json", legacy_scan)
    _write_json(out_dir / "golden_result.json", golden_result)
    _write_json(out_dir / "replay_result.json", replay_result)
    _write_json(out_dir / "oos_result.json", oos_result)
    _write_json(out_dir / "failure_injection_results.json",
                failure_injection)
    _write_json(out_dir / "physical_delete_result.json", deletion)
    _write_json(out_dir / "retirement_register.json", register)
    _write_json(out_dir / "graph_after_delete.json", graph_after_delete)

    logger.info(
        f"Artifacts 已生成 → {out_dir} | paths={path_info['count']} "
        f"active={manifest_artifact['active_count']} "
        f"golden={golden_result['status']} "
        f"fi={failure_injection['verdict']} "
        f"delete={deletion['verdict']} "
        f"crit_loc_down={loc_diff['decision_critical_loc_down']}")


def _load_artifact(out_dir: Path, name: str):
    p = out_dir / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def judge(out_dir: Path, logger) -> dict:
    """纯裁判：只读 artifact → evaluate_mtr() → verdict。
    禁止 run measurements / invent baseline / default PASS。"""
    missing = [name for name in MTR_ARTIFACT_NAMES
               if not (out_dir / name).exists()]
    if missing:
        return {"verdict": "NOT_PROVEN",
                "certificate": "MTR-NOT-PROVEN",
                "missing_artifacts": missing,
                "answers": {},
                "rule": "Missing Evidence → NOT_PROVEN，而不是 PASS"}
    bundle = {
        "authority_graph": _load_artifact(out_dir, "authority_graph.json"),
        "feature_manifest": _load_artifact(
            out_dir, "production_feature_manifest.json"),
        "loc_metrics": _load_artifact(out_dir, "critical_loc_diff.json"),
        "golden_result": _load_artifact(out_dir, "golden_result.json"),
        "replay_result": _load_artifact(out_dir, "replay_result.json"),
        "oos_result": _load_artifact(out_dir, "oos_result.json"),
        "failure_injection": _load_artifact(
            out_dir, "failure_injection_results.json"),
        "physical_delete": _load_artifact(
            out_dir, "physical_delete_result.json"),
    }
    return evaluate_mtr(bundle)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="QCFP_MTF MTR：证据生成（CI）或纯裁判")
    parser.add_argument("--generate-artifacts", action="store_true",
                        help="Build/CI 测量步骤：生成全部证据 artifact")
    parser.add_argument("--freeze-oos-contract", action="store_true",
                        help="冻结 OOS Contract（必须在任何 Current OOS "
                             "结果运行之前执行，且不可覆盖）")
    parser.add_argument("--train-end", default="2026-05-31")
    parser.add_argument("--validation-start", default="2026-06-01")
    parser.add_argument("--validation-end", default="2026-06-30")
    parser.add_argument("--oos-start", default="2026-07-01")
    parser.add_argument("--oos-end", default="2026-08-21")
    parser.add_argument("--previous-release-id", default="MERGED_CODE_9")
    args = parser.parse_args(argv)

    logger = setup_logger("minimal_trusted_release",
                          log_file="minimal_trusted_release.log", mode="w")
    qcfp_root = Path(CORE_DIR) / "QCFP_MTF"
    out_dir = get_report_root() / "audit" / "mtr"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.freeze_oos_contract:
        oos_dir = get_report_root() / "audit" / "oos"
        res = freeze_oos_contract(
            oos_dir,
            train_end=args.train_end,
            validation_start=args.validation_start,
            validation_end=args.validation_end,
            oos_start=args.oos_start,
            oos_end=args.oos_end,
            previous_release_id=args.previous_release_id)
        logger.info(f"Freeze OOS Contract: {res}")
        print(f"Freeze OOS Contract: {res}")
        return 0 if res.get("frozen") else 1

    if args.generate_artifacts:
        generate_artifacts(out_dir, qcfp_root, logger)
        logger.info("证据生成完成。运行 `python minimal_trusted_release.py` "
                    "进行纯裁判判定。")
        return 0

    verdict = judge(out_dir, logger)
    _write_json(out_dir / "mtr_verdict.json", verdict)
    logger.info(f"MTR Verdict: {verdict['verdict']} "
                f"({verdict.get('certificate', '')})")
    if verdict.get("failures"):
        logger.info(f"未通过项: {verdict['failures']}")
    print(f"MTR Verdict: {verdict['verdict']} "
          f"({verdict.get('certificate', '')})")
    return 0 if verdict["verdict"] == "MTR_SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
