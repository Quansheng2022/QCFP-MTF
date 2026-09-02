#!/usr/bin/env python
# coding: utf-8
"""QCFP_MTF Daily Runtime Evidence Runner（P0-1/2/3）

把 Runtime Evidence 接成长期运行、自动判定的生产证据链：
    Shadow Universe（全终态 → Ledger Fact）
    → Outcome Backfill（INSERT ONLY）
    → Paper EOD Reconciliation（独立 5 层对账）
    → Daily Current-Release Replay（REPLAY_PASS/MISMATCH/...）
    → Calibration Aggregation（禁止自动改参数）
    → Runtime Evidence（fail-closed）
    → Rolling Evidence Store（qcfp_runtime_evidence_daily）

每次运行带唯一：
    run_id / release_id / trade_date / universe_hash / config_hash /
    started_at / completed_at / runner_version

Run 生命周期（启动先写 RUN_STARTED；结束只能是）：
    RUN_COMPLETED / RUN_PARTIAL / RUN_HALTED

Universe 闭合计数：
    UniverseCount == Certified + NoTrade + Abstain + SafeMode + Halted
    不等 → SHADOW_COVERAGE_INCOMPLETE（不生成 PASS Evidence）。

产物（共享同一 run_id + release_id + trade_date + universe_hash）：
    shadow_run_manifest.json
    shadow_daily_summary.json
    shadow_runtime_evidence.json

用法：
    python Core/QCFP_MTF/scripts/runtime_evidence_runner.py \
        [--date YYYY-MM-DD] [--release REL-A] [--mode SHADOW|PAPER|SMALL_LIVE]
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings


RUNNER_VERSION = "runtime-evidence-1.0"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _since_date(date, lookback_days=90) -> str:
    from datetime import timedelta
    return (datetime.strptime(date, "%Y-%m-%d")
            - timedelta(days=lookback_days)).strftime("%Y-%m-%d")


def _load_or_create_freeze_contract(conn, date, settings, release_id,
                                    universe_hash, config_hash,
                                    run_id) -> dict:
    """EA-0：窗口首个交易日创建 Freeze Contract；之后复用（身份不一致
    由 Daily Gate 判定为 EVIDENCE_WINDOW_IDENTITY_BREAK）。"""
    from QCFP_MTF.governance.evidence_freeze_contract import (
        build_freeze_contract, load_freeze_contract, persist_freeze_contract)
    existing = load_freeze_contract()
    if existing.get("evidence_freeze_id"):
        return existing
    contract = build_freeze_contract(
        conn, settings, release_id=release_id, window_start=date,
        runner_version=RUNNER_VERSION, universe_hash=universe_hash)
    persist_freeze_contract(contract)
    return contract


def _config_hash(settings) -> str:
    raw = json.dumps(settings, sort_keys=True, ensure_ascii=False,
                     default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _universe_hash(codes) -> str:
    raw = ",".join(sorted(str(c).zfill(5) for c in codes))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                               default=str), encoding="utf-8")


def _decision_release_where(conn) -> str:
    """qcfp_decision_ledger 的 release 过滤：优先 release_id 列，
    否则从 context JSON（真实台账的 release identity）。"""
    try:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(qcfp_decision_ledger)").fetchall()]
    except Exception:
        cols = []
    if "release_id" in cols:
        return "release_id=?"
    return "json_extract(context,'$.release_identity.release_id')=?"


def paper_eod_reconciliation_from_ledger(conn, release_id, date) -> dict:
    """EOD：从 Runtime Event Ledger 取 FILL/PARTIAL_FILL 的 broker 仓位，
    canonical_targets 来自 Decision Ledger——两者独立事实集合。

    P0-5：同时收集 order/fill/fee 独立事实，交给 5 层对账。"""
    from QCFP_MTF.execution.paper_pipeline import \
        paper_daily_reconciliation
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        ("qcfp_runtime_event_ledger",)).fetchone()
    if not exists:
        return {"expected_reconciliations": 0,
                "actual_reconciliations": 0,
                "reconciliation_coverage": 0.0,
                "status": "NOT_PROVEN",
                "reason": "qcfp_runtime_event_ledger 未迁移（SQL schema "
                          "未应用）；无法对账（fail-closed）"}
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(qcfp_runtime_event_ledger)").fetchall()]
    select = ["stock_code", "broker_order_id"]
    for c in ("broker_position", "internal_position", "filled_qty",
              "commission", "stamp_duty", "exchange_fee", "other_fee"):
        if c in cols:
            select.append(c)
    paper_records = {}
    order_records = {}
    fill_records = {}
    fee_records = {}
    for r in conn.execute(
            "SELECT " + ",".join(select) + " "
            "FROM qcfp_runtime_event_ledger "
            "WHERE release_id=? AND event_type IN "
            "('FILL','PARTIAL_FILL') AND event_time LIKE ? "
            "ORDER BY event_seq",
            (release_id, f"{date}%")):
        code = r["stock_code"]
        paper_records.setdefault(code, {})
        if "broker_position" in r.keys() \
                and r["broker_position"] is not None:
            paper_records[code]["broker_position"] = \
                r["broker_position"]
        if "internal_position" in r.keys() \
                and r["internal_position"] is not None:
            paper_records[code]["position"] = r["internal_position"]
        order_records.setdefault(code, {})["broker_order_id"] = \
            r["broker_order_id"] or ""
        if "filled_qty" in r.keys():
            fill_records.setdefault(code, {})["filled_qty"] = \
                r["filled_qty"]
        fee_keys = [c for c in ("commission", "stamp_duty",
                                "exchange_fee", "other_fee")
                    if c in r.keys() and r[c] is not None]
        if fee_keys:
            fee_records.setdefault(code, {})["realized_fee"] = round(
                float(sum(r[k] for k in fee_keys)), 6)
    canonical_targets = {}
    release_where = _decision_release_where(conn)
    for r in conn.execute(
            "SELECT stock_code, final_target FROM qcfp_decision_ledger "
            "WHERE " + release_where +
            " AND decision_date=? AND status='ACTIVE'",
            (release_id, date)):
        canonical_targets[r["stock_code"]] = float(r["final_target"] or 0.0)
    return paper_daily_reconciliation(
        paper_records, canonical_targets,
        order_records=order_records or None,
        fill_records=fill_records or None,
        fee_records=fee_records or None)


def calibration_from_ledger(conn, release_id, date) -> dict:
    """从 Runtime Event payload 聚合 Calibration 样本。"""
    from QCFP_MTF.execution.paper_pipeline import paper_calibration_samples
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        ("qcfp_runtime_event_ledger",)).fetchone()
    if not exists:
        return {"dimensions": {}, "research_review_required": False,
                "status": "NOT_PROVEN",
                "reason": "qcfp_runtime_event_ledger 未迁移；"
                          "无 Calibration 样本（fail-closed）"}
    events = []
    for r in conn.execute(
            "SELECT payload FROM qcfp_runtime_event_ledger "
            "WHERE release_id=? AND event_type IN "
            "('FILL','PARTIAL_FILL','ORDER_REJECT','ORDER_UNKNOWN') "
            "AND event_time LIKE ?",
            (release_id, f"{date}%")):
        try:
            events.append({"payload": json.loads(r["payload"] or "{}")})
        except Exception:
            continue
    return paper_calibration_samples(events)


def run_daily_replay(conn, date, release_id, execution_mode="SHADOW",
                     dry_run=False, run_id="") -> dict:
    """P0-3 Daily Current-Release Replay：T 日 Shadow Decision 用同一
    Release 重放 → 只允许 REPLAY_PASS / REPLAY_MISMATCH /
    REPLAY_NOT_PROVEN / REPLAY_EXCEPTION。"""
    from QCFP_MTF.scripts.minimal_trusted_release import \
        replay_evidence_status, run_replay_evidence
    replay = run_replay_evidence(date=date)
    status = replay_evidence_status(replay)
    if not dry_run:
        from QCFP_MTF.execution.runtime_event_ledger import \
            append_runtime_event, ensure_runtime_event_table
        ensure_runtime_event_table(conn)
        suffix = run_id[-8:] if run_id else \
            datetime.now().strftime("%H%M%S")
        append_runtime_event(conn, {
            "event_id": f"RPL-{release_id}-{date}-{status}-{suffix}",
            "event_type": "REPLAY",
            # Replay 事件语义上属于 trade_date 的证据窗
            # （T 日决策 → T 日/当日重放认证），事件时间落在窗内
            # 以便 daily evidence 的 safety section 读取到。
            "event_time": f"{date} 23:59:59",
            "release_id": release_id,
            "execution_mode": execution_mode,
            "payload": {
                "trade_date": date,
                "verified": status == "REPLAY_PASS",
                "status": status,
                "replay_hash": replay.get(
                    "settings_registry_hash", ""),
                "n_total": replay.get("n_current_release"),
                "n_exact": replay.get("n_exact"),
                "critical_mismatch": replay.get("critical_mismatch"),
            }}, require_decision=False)
    return {"status": status,
            "n_current_release": replay.get("n_current_release"),
            "n_eligible": replay.get("n_eligible"),
            "n_ineligible": replay.get("n_ineligible"),
            "n_exact": replay.get("n_exact"),
            "n_mismatch": replay.get("n_mismatch"),
            "n_replay_exception": replay.get("n_replay_exception"),
            "eligible_rate": replay.get("eligible_rate"),
            "exact_rate": replay.get("exact_rate"),
            "critical_mismatch": replay.get("critical_mismatch"),
            "replay_hash": replay.get("settings_registry_hash"),
            "rule": "每日 Replay 只允许四种状态；无数据/缺材料 → "
                    "REPLAY_NOT_PROVEN"}


def _closure_check(shadow: dict) -> dict:
    """Universe 闭合计数：
        UniverseCount == Certified + NoTrade + Abstain + SafeMode + Halted"""
    counts = shadow.get("state_counts") or {}
    terminal_count = sum(int(counts.get(k) or 0) for k in
                         ("CERTIFIED", "NO_TRADE", "ABSTAIN",
                          "SAFE_MODE", "HALTED"))
    universe_count = int(shadow.get("universe_count") or 0)
    ok = (terminal_count == universe_count
          and universe_count > 0
          and not shadow.get("missing_stocks")
          and int(shadow.get("duplicate_decisions") or 0) == 0)
    return {"ok": ok,
            "universe_count": universe_count,
            "terminal_count": terminal_count,
            "missing_stocks": shadow.get("missing_stocks"),
            "duplicate_decisions": shadow.get("duplicate_decisions"),
            "verdict": "SHADOW_COVERAGE_OK" if ok
            else "SHADOW_COVERAGE_INCOMPLETE"}


def run_daily(conn, date, release_id, mode, settings,
              dry_run=False, run_id="", universe_hash="",
              config_hash="", started_at="",
              enable_paper_reconciliation=False) -> dict:
    from QCFP_MTF.monitoring.runtime_evidence import \
        build_runtime_evidence_from_ledger
    from QCFP_MTF.monitoring.runtime_evidence_store import \
        persist_daily_runtime_evidence
    from QCFP_MTF.scripts.backfill_research_outcomes import backfill_outcomes
    from QCFP_MTF.scripts.shadow_universe import run_universe_shadow, \
        universe_symbols
    started_at = started_at or _now()
    run_id = run_id or f"runtime_{date}_{mode}_{datetime.now():%H%M%S}"
    if not universe_hash:
        universe = universe_symbols(conn, date)
        universe_hash = _universe_hash(universe)
    if not config_hash:
        config_hash = _config_hash(settings)
    freeze = _load_or_create_freeze_contract(
        conn, date, settings, release_id, universe_hash, config_hash,
        run_id)
    manifest = {
        "run_id": run_id, "release_id": release_id,
        "trade_date": date, "universe_hash": universe_hash,
        "config_hash": config_hash, "runner_version": RUNNER_VERSION,
        "started_at": started_at, "completed_at": "",
        "run_state": "RUN_STARTED", "evidence_freeze_id": "",
    }
    try:
        # 1) Shadow 全终态 → Ledger Fact
        shadow = run_universe_shadow(
            conn, date, settings,
            run_id=f"daily_{date}_{run_id}", dry_run=dry_run)
        closure = _closure_check(shadow)
        if not dry_run:
            from QCFP_MTF.execution.runtime_event_ledger import \
                ensure_runtime_event_table
            ensure_runtime_event_table(conn)
        # 2) Outcome Backfill（INSERT ONLY）
        if dry_run:
            outcomes = {"inserted": 0, "skipped": 0, "errors": [],
                        "dry_run": True}
        else:
            outcomes = backfill_outcomes(
                conn, horizons=("5D", "20D", "60D"),
                release_id=release_id, since=_since_date(date))
        # 3) Paper EOD Reconciliation（OPTIONAL hook，默认不执行；
        #    决策支持资格不依赖 Broker/Order/Fill）
        if enable_paper_reconciliation:
            reconciliation = paper_eod_reconciliation_from_ledger(
                conn, release_id, date)
            calibration = calibration_from_ledger(conn, release_id, date)
        else:
            reconciliation = {
                "applicable": "OPTIONAL_SIMULATION_EVIDENCE",
                "reason": "决策支持模式不执行 Paper 对账"}
            calibration = {
                "applicable": "OPTIONAL_SIMULATION_EVIDENCE",
                "dimensions": {}, "research_review_required": False,
                "reason": "决策支持模式不执行 Calibration"}
        # 4) Daily Current-Release Replay（P0-3）
        replay = run_daily_replay(
            conn, date, release_id, execution_mode=mode, dry_run=dry_run,
            run_id=run_id)
        # 6) Decision Support Evidence（fail-closed）
        evidence = build_runtime_evidence_from_ledger(
            conn, release_id, {"start": date, "end": date},
            execution_mode=mode, replay_result=replay,
            today=_now()[:10])
        # 7) Daily Evidence Completeness Gate（P0-2）
        from QCFP_MTF.monitoring.evidence_daily_gate import \
            evaluate_daily_evidence_gate
        outcome_section = (evidence.get("evidence") or {}).get(
            "outcome") or {}
        gate_pre = evaluate_daily_evidence_gate(
            evidence, replay=replay, shadow=shadow,
            outcome=outcome_section, outcome_backfill=outcomes,
            freeze_contract=freeze, day_identity=freeze)
        persisted = None
        if not dry_run:
            from QCFP_MTF.monitoring.runtime_evidence_store import (
                persist_daily_runtime_evidence,
                upgrade_runtime_evidence_daily_schema)
            upgrade_runtime_evidence_daily_schema(conn)
            persisted = persist_daily_runtime_evidence(
                conn, evidence, release_id=release_id,
                execution_mode=mode, trade_date=date, run_id=run_id,
                shadow=shadow, replay=replay, outcome=outcome_section,
                stability=(evidence.get("evidence") or {}).get(
                    "stability") or {},
                freeze=freeze, daily_gate=gate_pre)
        gate = evaluate_daily_evidence_gate(
            evidence, replay=replay, shadow=shadow,
            outcome=outcome_section, outcome_backfill=outcomes,
            persisted=persisted, freeze_contract=freeze,
            day_identity=freeze)
        if persisted and not dry_run:
            conn.execute(
                "UPDATE qcfp_runtime_evidence_daily SET "
                "daily_evidence_state=?, qualification_eligible=? "
                "WHERE evidence_id=?",
                (gate["state"], 1 if gate["qualified"] else 0,
                 persisted["evidence_id"]))
            conn.commit()
        run_state = "RUN_COMPLETED" if (closure["ok"]
                                        and gate["state"]
                                        == "DAILY_EVIDENCE_READY") \
            else "RUN_PARTIAL"
        manifest.update({"completed_at": _now(),
                         "run_state": run_state,
                         "evidence_freeze_id":
                             freeze.get("evidence_freeze_id", "")})
        return {
            "manifest": manifest,
            "run_date": date,
            "release_id": release_id,
            "execution_mode": mode,
            "run_state": run_state,
            "shadow": {k: shadow[k] for k in
                       ("universe_count", "decision_count",
                        "missing_stocks", "duplicate_decisions",
                        "state_counts", "verdict")},
            "closure": closure,
            "outcome_backfill": outcomes,
            "paper_eod_reconciliation": reconciliation,
            "calibration": calibration,
            "replay": replay,
            "runtime_evidence": evidence,
            "persisted_evidence": persisted,
            "daily_evidence_gate": gate,
            "evidence_freeze_id": freeze.get("evidence_freeze_id", ""),
        }
    except Exception as exc:
        manifest.update({"completed_at": _now(),
                         "run_state": "RUN_HALTED",
                         "error": f"{type(exc).__name__}: {exc}"})
        return {"manifest": manifest, "run_date": date,
                "release_id": release_id, "execution_mode": mode,
                "run_state": "RUN_HALTED",
                "error": f"{type(exc).__name__}: {exc}",
                "shadow": {}, "closure": {"ok": False},
                "outcome_backfill": {}, "paper_eod_reconciliation": {},
                "calibration": {}, "replay": {},
                "runtime_evidence": {"verdict": "NOT_PROVEN"},
                "persisted_evidence": None}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="QCFP-MTF Daily Runtime Evidence Runner")
    parser.add_argument("--date", default="")
    parser.add_argument("--release", default="")
    parser.add_argument("--mode", default="SHADOW",
                        choices=("SHADOW", "PAPER", "SMALL_LIVE"))
    parser.add_argument("--dry-run", action="store_true",
                        help="不写 Ledger/Fact/Outcome/Event/Store，仅计算")
    parser.add_argument("--enable-paper-reconciliation",
                        action="store_true",
                        help="可选执行 Paper EOD 5 层对账与 Calibration"
                             "（决策支持资格不依赖，默认关闭）")
    args = parser.parse_args(argv)
    logger = setup_logger("runtime_evidence_runner",
                          log_file="runtime_evidence_runner.log", mode="a")
    settings = load_qcfp_settings()
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    from QCFP_MTF.decision.versions import RELEASE_TAG
    release_id = args.release or RELEASE_TAG
    from QCFP_MTF.scripts.shadow_universe import universe_symbols
    conn = connect()
    try:
        universe = universe_symbols(conn, date)
    finally:
        conn.close()
    universe_hash = _universe_hash(universe)
    config_hash = _config_hash(settings)
    run_id = f"runtime_{date}_{args.mode}_{datetime.now():%H%M%S}"
    out_dir = get_report_root() / "audit" / "runtime_evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id, "release_id": release_id,
        "trade_date": date, "universe_hash": universe_hash,
        "config_hash": config_hash, "runner_version": RUNNER_VERSION,
        "started_at": _now(), "completed_at": "",
        "run_state": "RUN_STARTED",
    }
    _write_json(out_dir / "shadow_run_manifest.json", manifest)
    logger.info(
        f"RUN_STARTED run_id={run_id} date={date} mode={args.mode} "
        f"universe_hash={universe_hash}")
    try:
        conn = connect()
        try:
            result = run_daily(
                conn, date, release_id, args.mode, settings,
                dry_run=args.dry_run, run_id=run_id,
                universe_hash=universe_hash, config_hash=config_hash,
                started_at=manifest["started_at"],
                enable_paper_reconciliation=
                args.enable_paper_reconciliation)
        finally:
            conn.close()
    except Exception as exc:
        manifest.update({"completed_at": _now(),
                         "run_state": "RUN_HALTED",
                         "error": f"{type(exc).__name__}: {exc}"})
        _write_json(out_dir / "shadow_run_manifest.json", manifest)
        logger.error(f"RUN_HALTED: {exc}")
        print(f"Runtime Evidence: RUN_HALTED ({type(exc).__name__})")
        return 1
    manifest = result.get("manifest") or manifest
    _write_json(out_dir / "shadow_run_manifest.json", manifest)
    _write_json(out_dir / "shadow_daily_summary.json", {
        **manifest,
        "shadow": result.get("shadow"),
        "closure": result.get("closure"),
        "outcome_backfill": result.get("outcome_backfill"),
        "paper_eod_reconciliation":
            result.get("paper_eod_reconciliation"),
        "calibration": result.get("calibration"),
        "replay": result.get("replay"),
        "persisted_evidence": result.get("persisted_evidence"),
    })
    _write_json(out_dir / "shadow_runtime_evidence.json", {
        **manifest,
        "runtime_evidence": result.get("runtime_evidence"),
        "replay": result.get("replay"),
        "daily_evidence_gate": result.get("daily_evidence_gate"),
    })
    # P0-6：每日 Evidence Accumulation Health Report
    try:
        from QCFP_MTF.scripts.evidence_accumulation_report import \
            build_accumulation_report
        conn = connect()
        try:
            health = build_accumulation_report(
                conn, release_id, args.mode,
                required_days=20)
        finally:
            conn.close()
        _write_json(out_dir / "evidence_accumulation_report.json", health)
    except Exception as exc:
        logger.warning(f"health report failed: {type(exc).__name__}: {exc}")
    ev_verdict = (result.get("runtime_evidence") or {}).get(
        "verdict", "NOT_PROVEN")
    run_state = result.get("run_state", "RUN_PARTIAL")
    logger.info(
        f"daily={date} mode={args.mode} run_state={run_state} "
        f"shadow={result.get('shadow', {}).get('verdict')} "
        f"closure={result.get('closure', {}).get('verdict')} "
        f"replay={result.get('replay', {}).get('status')} "
        f"evidence={ev_verdict}")
    print(f"Runtime Evidence: {ev_verdict} "
          f"(run_state={run_state}, "
          f"replay={result.get('replay', {}).get('status')}, "
          f"closure={result.get('closure', {}).get('verdict')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
