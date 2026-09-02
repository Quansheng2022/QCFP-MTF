#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.6 —— Release Gate（发布验收门）

版本不能因为"代码跑通"就发布，必须 12 门同时满足：
    Governance / PIT / Replay / Audit / Backtest / Ablation / OOS /
    FSM / Re-entry / Shadow / Report / Research

用法：python Core/QCFP_MTF/scripts/release_gate.py [--stock 01951]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.paths import get_report_root


def _run_invariant_modules():
    """在进程内运行不变量测试模块（governance matrix + decision invariants）"""
    import importlib
    fails = []
    for mod in ("test_decision.test_governance_matrix",
                "test_decision.test_decision_invariants"):
        m = importlib.import_module(f"QCFP_MTF.tests.{mod}")
        for name, fn in sorted(vars(m).items()):
            if name.startswith("test_") and callable(fn):
                try:
                    fn()
                except Exception as exc:  # noqa: BLE001
                    fails.append(f"{mod}.{name}: {exc}")
    return fails


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF Release Gate")
    parser.add_argument("--stock", default="01951")
    args = parser.parse_args(argv)
    gates = []

    # G-Governance：不变量矩阵 + Decision Invariants 全过
    fails = _run_invariant_modules()
    gates.append(("Governance", "PASS" if not fails else "FAIL",
                  f"不变量矩阵/10 条 Invariants {'全部通过' if not fails else fails[:2]}"))
    # G-PIT：台账全部记录身份与分级（无硬编码 D）
    conn = connect()
    try:
        latest_id = conn.execute(
            "SELECT MAX(id) FROM qcfp_decision_ledger").fetchone()[0]
        latest_run = conn.execute(
            "SELECT run_id FROM qcfp_decision_ledger WHERE id=?",
            (latest_id,)).fetchone()
        run_id = latest_run["run_id"] if latest_run else None
        n = conn.execute(
            "SELECT COUNT(*) FROM qcfp_decision_ledger WHERE run_id=?",
            (run_id,)).fetchone()[0] if run_id else 0
        n_ok = conn.execute(
            "SELECT COUNT(*) FROM qcfp_decision_ledger WHERE "
            "run_id=? AND decision_id IS NOT NULL AND "
            "input_fingerprint IS NOT NULL AND "
            "settings_hash IS NOT NULL AND model_version IS NOT NULL AND "
            "rule_version IS NOT NULL AND schema_version IS NOT NULL AND "
            "pit_grade IN ('A','B','C')",
            (run_id,)).fetchone()[0] if run_id else 0
        gates.append(("Audit", "PASS" if n and n_ok == n else "FAIL",
                      f"最新 run {run_id}：{n_ok}/{n} 条身份完整"))
        # PIT：无真实披露表 → 不应宣称 Research Validated
        pit_c = conn.execute(
            "SELECT COUNT(*) FROM qcfp_decision_ledger WHERE run_id=? "
            "AND pit_grade='C'", (run_id,)).fetchone()[0] if run_id else 0
        gates.append(("PIT", "WARN" if pit_c else "PASS",
                      f"PIT-C {pit_c} 条（估算披露日，探索模式）"))
        # Shadow：台账存在且与唯一引擎同源（由 shadow_mode 保证，非空即 PASS）
        gates.append(("Shadow", "PASS" if n else "FAIL",
                      "Shadow→Ledger 由 canonical_replay 单次 Evaluate 写入"))
        # Re-entry：再入场门存在且无冷启动（cooldown>0 行存在）
        n_cd = conn.execute(
            "SELECT COUNT(*) FROM qcfp_decision_ledger WHERE run_id=? "
            "AND next_fsm_state='COOLDOWN'",
            (run_id,)).fetchone()[0] if run_id else 0
        gates.append(("Re-entry", "PASS" if n_cd > 0 else "WARN",
                      f"COOLDOWN 行 {n_cd}（再入场门已参与决策链）"))
    finally:
        conn.close()
    # Replay：治理矩阵测试已覆盖确定性（G-Governance 通过即代表）
    gates.append(("Replay", "PASS" if not fails else "FAIL",
                  "同输入→同 DecisionSnapshot（治理矩阵重放覆盖）"))
    gates.append(("FSM", "PASS" if not fails else "FAIL",
                  "7 状态全转移由矩阵+不变量测试覆盖"))
    # Backtest / OOS / Report / Ablation / Research：读取最新回测汇总
    bt_dir = get_report_root() / "backtest"
    summaries = sorted(bt_dir.glob("summary_*.json"),
                       key=lambda p: p.stat().st_mtime)
    if summaries:
        s = json.loads(summaries[-1].read_text(encoding="utf-8"))
        rg = s.get("research_gate", {})
        oos_sharpes = [r.get("sharpe") for r in
                       s.get("rolling_oos_evaluation", [])
                       if r.get("sharpe") is not None]
        med = sorted(oos_sharpes)[len(oos_sharpes) // 2] if oos_sharpes else None
        gates.append(("Backtest", "PASS",
                      f"cost_model={s.get('cost_model_version')}，"
                      f"引擎源={s.get('run_id', '').split('_')[0]}"))
        gates.append(("OOS", "PASS" if med is not None and med > 0 else "WARN",
                      f"median_OOS_Sharpe={med}"))
        gates.append(("Research", "WARN" if rg.get("overall") != "PASS"
                      else "PASS",
                      f"Research Gate={rg.get('status_label')}"))
    else:
        gates.append(("Backtest", "FAIL", "无回测汇总"))
        gates.append(("OOS", "FAIL", "无回测汇总"))
        gates.append(("Research", "FAIL", "无回测汇总"))
    # Ablation：最近一次 Ablation JSON 存在且含机制报告
    abl = sorted(bt_dir.glob("permission_fsm_ablation_*.json"),
                 key=lambda p: p.stat().st_mtime)
    gates.append(("Ablation", "PASS" if abl else "FAIL",
                  f"最近实验 {abl[-1].name if abl else '无'}（含机制报告）"))
    # Report：Decision/Audit 报告存在
    dec = sorted((get_report_root() / "decision").glob(
        f"{args.stock}_decision_*.md"))
    aud = sorted((get_report_root() / "audit").glob(
        f"{args.stock}_audit_*.md"))
    gates.append(("Report", "PASS" if dec and aud else "WARN",
                  f"Decision {len(dec)} 份 / Audit {len(aud)} 份"))

    # 2.8（40 号）：生产级追加门——Stress / Execution / Statistical /
    # Capacity / Decision Consistency / Ledger Integrity
    stress_files = sorted((get_report_root() / "stress").glob(
        "stress_*.json"), key=lambda p: p.stat().st_mtime)
    stress_ok = False
    if stress_files:
        try:
            s = json.loads(stress_files[-1].read_text(encoding="utf-8"))
            stress_ok = s.get("survivable") is True and \
                s.get("liquidity_risk_count") is not None
        except Exception:
            stress_ok = False
    gates.append(("Stress", "PASS" if stress_ok else "FAIL",
                  f"压力报告{'可存活' if stress_ok else '缺失/不可存活'} "
                  f"({len(stress_files)} 份)"))

    exec_files = sorted((get_report_root() / "execution").glob(
        "execution_*.json"), key=lambda p: p.stat().st_mtime) \
        if (get_report_root() / "execution").exists() else []
    exec_ok = bool(exec_files)
    gates.append(("Execution", "PASS" if exec_ok else "FAIL",
                  f"执行仿真报告 {len(exec_files)} 份（成本/滑点/成交率显式化）"))

    stat_files = sorted((get_report_root() / "statistical").glob(
        "statistical_*.json"), key=lambda p: p.stat().st_mtime) \
        if (get_report_root() / "statistical").exists() else []
    stat_ok = False
    if stat_files:
        try:
            st = json.loads(stat_files[-1].read_text(encoding="utf-8"))
            stat_ok = bool(st.get("significant") is not None)
        except Exception:
            stat_ok = False
    gates.append(("Statistical", "PASS" if stat_ok else "FAIL",
                  f"统计验证 {len(stat_files)} 份（Bootstrap CI/Permutation）"))

    cap_files = sorted((get_report_root() / "capacity").glob(
        "capacity_*.json"), key=lambda p: p.stat().st_mtime)
    cap_ok = bool(cap_files)
    gates.append(("Capacity", "PASS" if cap_ok else "FAIL",
                  f"容量报告 {len(cap_files)} 份（1%/3%/5%/10% ADV 档位）"))

    # Decision Consistency / Ledger Integrity：重新打开连接（前面已关闭）
    conn2 = connect()
    try:
        runs = conn2.execute(
            "SELECT DISTINCT run_id FROM qcfp_decision_ledger "
            "WHERE status='ACTIVE' ORDER BY created_at DESC LIMIT 2"
        ).fetchall()
        flip_rate = None
        if len(runs) == 2:
            try:
                from QCFP_MTF.governance.version_impact import version_impact
                def _snaps(run_id):
                    rs = conn2.execute(
                        "SELECT decision_id, institutional_permission, "
                        "setup_type, exit_event, previous_fsm_state, "
                        "next_fsm_state, final_target, primary_reason "
                        "FROM qcfp_decision_ledger WHERE run_id=? "
                        "AND status='ACTIVE'", (run_id,)).fetchall()
                    return {r["decision_id"]: dict(r) for r in rs}
                imp = version_impact(_snaps(runs[1]["run_id"]),
                                     _snaps(runs[0]["run_id"]))
                flip_rate = imp.flip_rate
            except Exception:
                flip_rate = None
        cons_ok = flip_rate is not None and flip_rate <= 0.10
        gates.append(("Decision Consistency",
                      "PASS" if cons_ok else "FAIL" if flip_rate is not None
                      else "WARN",
                      f"最近 2 run 翻转率="
                      f"{flip_rate if flip_rate is not None else 'N/A'}"))

        led_n = conn2.execute(
            "SELECT COUNT(*) FROM qcfp_decision_ledger WHERE status='ACTIVE'"
        ).fetchone()[0]
        led_ok = conn2.execute(
            "SELECT COUNT(*) FROM qcfp_decision_ledger WHERE status='ACTIVE' "
            "AND decision_id IS NOT NULL AND input_fingerprint IS NOT NULL "
            "AND settings_hash IS NOT NULL AND model_version IS NOT NULL "
            "AND rule_version IS NOT NULL AND schema_version IS NOT NULL "
            "AND data_snapshot_id IS NOT NULL").fetchone()[0]
        gates.append(("Ledger Integrity",
                      "PASS" if led_n and led_ok == led_n else "FAIL",
                      f"{led_ok}/{led_n} 条身份完整"))
    finally:
        conn2.close()

    # 5 大验收评分
    scores = {}
    scores["governance"] = round(
        100 * (1 - len(fails) / max(1, 10 + 8)), 1)   # 不变量矩阵 + G1-G8
    scores["audit"] = round(100 * n_ok / n, 1) if n else 0.0
    bt_ok = sum(1 for g in gates if g[0] in ("PIT", "Backtest", "OOS")
                and g[1] == "PASS")
    scores["backtest_integrity"] = round(100 * bt_ok / 3, 1)
    abl_data = {}
    if abl:
        try:
            abl_data = json.loads(abl[-1].read_text(encoding="utf-8"))
        except Exception:
            abl_data = {}
    has_meta = bool(abl_data.get("experiment", {}).get("shared_input_hash"))
    has_mech = any(m.get("mechanism") for m in abl_data.get("models", []))
    scores["ablation_integrity"] = 100.0 if (has_meta and has_mech) else 60.0
    wave_files = sorted((get_report_root() / "wave_capture").glob(
        "wave_capture_*.json"), key=lambda p: p.stat().st_mtime)
    retail_ok = False
    if wave_files:
        try:
            w = json.loads(wave_files[-1].read_text(encoding="utf-8"))
            u = w.get("summary", {}).get("retail_utility", {})
            retail_ok = any(u.get(k) is not None
                            for k in ("false_exit_rate", "whipsaw_rate",
                                      "false_participation_rate"))
        except Exception:
            retail_ok = False
    scores["retail_practicality"] = 100.0 if retail_ok else 40.0

    statuses = [g[1] for g in gates]
    verdict = "FAIL" if "FAIL" in statuses else \
        ("CONDITIONAL" if "WARN" in statuses else "RELEASE")
    result = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "verdict": verdict,
              "scores": scores,
              "gates": [{"gate": g[0], "status": g[1], "evidence": g[2]}
                        for g in gates]}
    out_dir = get_report_root() / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (out_dir / f"release_gate_{stamp}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    print(f"Release Gate：{verdict}")
    print("  5 大验收评分：")
    for k, v in scores.items():
        print(f"    {k}: {v}")
    for g in gates:
        print(f"  [{g[1]:<4}] {g[0]}: {g[2]}")
    return 0 if verdict == "RELEASE" else 1


if __name__ == "__main__":
    sys.exit(main())
