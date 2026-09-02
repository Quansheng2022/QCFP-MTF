#!/usr/bin/env python
# coding: utf-8
"""QCFP_MTF Daily Full-Universe Shadow Runner
（Runtime Evidence Wiring：第 3 项）

从 UniverseSnapshot(date) 出发，对**每只**股票执行：
    PIT/DataQuality → Canonical Engine → 唯一终态

每只股票必须属于：CERTIFIED / NO_TRADE / SAFE_MODE / ABSTAIN / HALTED。
关键：异常不能让股票消失——evidence missing → ABSTAIN；系统故障 → HALTED；
UNKNOWN + previous_position>0 → no-new-risk（不是强制 EXIT）。

输出 Coverage Artifact（硬门）：
    decision_count == universe_count
    missing_stocks   == []
    duplicates       == 0

用法：
    python Core/QCFP_MTF/scripts/shadow_universe.py [--date YYYY-MM-DD] [--limit N]
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
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.decision.decision_ledger import dataset_manifest_hash, \
    record_snapshot
from QCFP_MTF.decision.versions import RELEASE_TAG, feature_manifest_hash


TERMINAL_STATES = ("CERTIFIED", "NO_TRADE", "SAFE_MODE", "ABSTAIN", "HALTED")

SHADOW_FACT_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS qcfp_shadow_decision_fact (
    fact_id TEXT PRIMARY KEY,
    stock_code TEXT NOT NULL,
    decision_date TEXT NOT NULL,
    terminal_state TEXT NOT NULL,
    reason TEXT,
    run_id TEXT,
    release_id TEXT,
    created_at TEXT
)
"""


def ensure_shadow_fact_table(conn) -> None:
    """显式建表（测试/本地）。Production schema 由 SQL 迁移拥有。"""
    conn.execute(SHADOW_FACT_TABLE_DDL)


def record_coverage_fact(conn, state, stock, date, run_id, reason="",
                         release_id="") -> int:
    """ABSTAIN / SAFE_MODE / HALTED 也必须是 Ledger Fact——
    不允许只存在于 Coverage JSON（Closure 4）。"""
    from datetime import datetime
    ensure_shadow_fact_table(conn)
    cur = conn.execute(
        "INSERT OR IGNORE INTO qcfp_shadow_decision_fact "
        "(fact_id, stock_code, decision_date, terminal_state, reason, "
        "run_id, release_id, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (f"SF-{run_id}-{stock}-{date}", stock, date, state, reason,
         run_id, release_id,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    return cur.rowcount


def universe_symbols(conn, date, stock_limit=None) -> list:
    """UniverseSnapshot(date)：hk_stock_info 活跃代码 ∪
    当天/历史 qcfp_mtf_decision 代码（上游没出 decision row 的股票
    不能从 Shadow Coverage 消失）。"""
    codes = set()
    for r in conn.execute(
            "SELECT stock_code FROM hk_stock_info WHERE is_active=1"):
        codes.add(str(r[0]))
    for r in conn.execute(
            "SELECT DISTINCT stock_code FROM qcfp_mtf_decision"):
        codes.add(str(r[0]))
    result = sorted(codes)
    if stock_limit:
        result = result[:int(stock_limit)]
    return result


def universe_snapshot_id(codes: list, date: str) -> str:
    """Universe Snapshot ID：内容敏感（排序代码列表哈希），
    Replay Gate 可以证明该引用未来可找回。"""
    import hashlib
    raw = f"{date}|" + ",".join(sorted(str(c).zfill(5) for c in codes))
    return f"universe-{date}-" \
        f"{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _evidence_row(conn, stock, date):
    from QCFP_MTF.scripts.dss_report import _row
    return _row(conn, stock, date)


def _previous_state(conn, stock, date):
    r = conn.execute(
        "SELECT next_fsm_state, final_target FROM qcfp_decision_ledger "
        "WHERE stock_code=? AND decision_date<? AND status='ACTIVE' "
        "ORDER BY decision_date DESC, id DESC LIMIT 1",
        (stock, date)).fetchone()
    if r is None:
        return "FLAT", 0.0
    return r["next_fsm_state"] or "FLAT", float(r["final_target"] or 0.0)


def classify_terminal_state(snap, target_position) -> str:
    """Canonical Snapshot → Shadow 终态。
    SAFE_MODE（safety 信号）优先；target>0 → CERTIFIED；
    target==0（可信判断）→ NO_TRADE；无 snapshot → ABSTAIN。"""
    if snap is None:
        return "ABSTAIN"
    ctx = getattr(snap, "context", None) or {}
    if str(ctx.get("safety_status") or "").upper() == "SAFE_MODE":
        return "SAFE_MODE"
    return "CERTIFIED" if float(target_position or 0.0) > 1e-9 \
        else "NO_TRADE"


def run_universe_shadow(conn, date, settings, stock_limit=None,
                        run_id="", dry_run=False) -> dict:
    """全 Universe Shadow：每只股票必须落在五态之一，异常不得消失。"""
    run_id = run_id or f"shadow_universe_{date}_{datetime.now():%H%M%S}"
    release_id = settings.get("model", {}).get("release_id", "") \
        if isinstance(settings, dict) else ""
    release_id = release_id or RELEASE_TAG
    universe = universe_symbols(conn, date, stock_limit)
    data_snapshot_id = dataset_manifest_hash(conn)
    uv_snapshot_id = universe_snapshot_id(universe, date)
    release_manifest_hash = hashlib.sha256(
        f"{release_id}|{feature_manifest_hash()}".encode("utf-8")
    ).hexdigest()[:16]
    release_context = {
        "release_id": release_id,
        "release_manifest_hash": release_manifest_hash,
        "data_snapshot_id": data_snapshot_id,
        "universe_snapshot_id": uv_snapshot_id,
        "production_manifest_hash":
            (settings.get("model", {}).get("production_manifest_hash", "")
             if isinstance(settings, dict) else "") or feature_manifest_hash(),
    }
    outcomes = {}
    for code in universe:
        try:
            row = _evidence_row(conn, code, date)
            if row is None:
                record_coverage_fact(conn, "ABSTAIN", code, date, run_id,
                                     "EVIDENCE_MISSING", release_id)
                outcomes[code] = {"state": "ABSTAIN",
                                  "reason": "EVIDENCE_MISSING",
                                  "recorded": True}
                continue
            prev_fsm, prev_pos = _previous_state(conn, code, date)
            eval_row = dict(row)
            eval_row["release_context"] = dict(release_context)
            snap = evaluate(eval_row, prev_fsm, prev_pos, settings,
                            run_id=run_id)
            # Q8-R1：把决策输入行存入 Snapshot context——Replay 需要
            # Evidence 可找回（Ledger 不复制整份数据集，只存单条输入行）。
            snap.context["shadow_evidence"] = eval_row
            state = classify_terminal_state(snap, snap.target_position)
            recorded = False
            if state in ("CERTIFIED", "NO_TRADE"):
                if not dry_run:
                    record_snapshot(conn, snap, run_id, settings=settings)
                    recorded = True
            elif state == "SAFE_MODE" and not dry_run:
                record_coverage_fact(conn, state, code, date, run_id,
                                     snap.primary_reason, release_id)
                recorded = True
            outcomes[code] = {
                "state": state,
                "reason": snap.primary_reason,
                "target": snap.target_position,
                "permission": snap.institutional_permission,
                "fsm": snap.next_fsm_state,
                "recorded": recorded,
            }
        except Exception as exc:
            # 数据质量/PIT 类证据门 → ABSTAIN（无法形成判断）；
            # 其余系统级故障 → HALTED。绝不让股票消失。
            name = type(exc).__name__
            if any(k in name.upper() for k in
                   ("PIT", "EVIDENCE", "CONTRACT", "FEATURE", "QUALITY")):
                state = "ABSTAIN"
            else:
                state = "HALTED"
            record_coverage_fact(conn, state, code, date, run_id,
                                 f"{name}: {exc}", release_id)
            outcomes[code] = {"state": state,
                              "reason": f"{name}: {exc}",
                              "recorded": True}
    return build_coverage(outcomes, universe, run_id, date)


def build_coverage(outcomes: dict, universe: list, run_id="",
                   date="") -> dict:
    """Coverage Artifact + 硬门：
        decision_count == universe_count
        missing_stocks  == []
        duplicates      == 0
    """
    decision_count = len(outcomes)
    distinct = len({k for k in outcomes})
    duplicates = decision_count - distinct
    missing = [c for c in universe if c not in outcomes]
    state_counts = {s: 0 for s in TERMINAL_STATES}
    for v in outcomes.values():
        st = v["state"] if v["state"] in TERMINAL_STATES else "HALTED"
        state_counts[st] += 1
    gate_ok = (decision_count == len(universe)
               and not missing and duplicates == 0)
    return {
        "run_id": run_id,
        "decision_date": date,
        "universe_count": len(universe),
        "decision_count": decision_count,
        "distinct_stock_count": distinct,
        "duplicate_decisions": duplicates,
        "missing_stocks": missing,
        "state_counts": state_counts,
        "certified": state_counts["CERTIFIED"],
        "no_trade": state_counts["NO_TRADE"],
        "abstain": state_counts["ABSTAIN"],
        "safe_mode": state_counts["SAFE_MODE"],
        "halted": state_counts["HALTED"],
        "per_stock": outcomes,
        "coverage_ok": gate_ok,
        "verdict": "SHADOW_COVERAGE_OK" if gate_ok
        else "SHADOW_COVERAGE_INCOMPLETE",
        "rule": "Daily Shadow Decision Coverage=100%；"
                "Unexplained Missing=0",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="QCFP-MTF Daily Full-Universe Shadow Runner")
    parser.add_argument("--date", default="")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="不写 Ledger，仅计算覆盖率")
    args = parser.parse_args(argv)
    settings = load_qcfp_settings()
    logger = setup_logger("shadow_universe",
                          log_file="shadow_universe.log", mode="a")
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    conn = connect()
    try:
        coverage = run_universe_shadow(
            conn, date, settings, stock_limit=args.limit,
            dry_run=args.dry_run)
    finally:
        conn.close()
    out_dir = get_report_root() / "shadow" / "universe"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (out_dir / f"shadow_universe_{date}_{stamp}.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    logger.info(
        f"Universe={coverage['universe_count']} "
        f"decisions={coverage['decision_count']} "
        f"missing={len(coverage['missing_stocks'])} "
        f"duplicates={coverage['duplicate_decisions']} "
        f"verdict={coverage['verdict']}")
    print(f"Shadow Universe: {coverage['verdict']} "
          f"({coverage['universe_count']} stocks, "
          f"{coverage['decision_count']} decisions)")
    return 0 if coverage["coverage_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
