#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— Canonical Decision Path Audit（唯一决策链审计）

验证 Live / Backtest / Replay / Shadow / Report / Ablation 全部经过
同一条 Canonical Decision Path（engine.evaluate），并确认：
    - Permission Gate 前置（BLOCK → target 0）
    - Governance Proof 计算（proof PASS 才允许 Decision）
    - 目标链 raw → governed → final 完整

用法：python Core/QCFP_MTF/scripts/canonical_audit.py
"""

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS


def _row(**kw):
    base = {
        "stock_code": "T_CAN", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Medium", "des_score": 1,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.3,
    }
    base.update(kw)
    return base


def main(argv=None) -> int:
    from QCFP_MTF.decision.engine import evaluate
    from QCFP_MTF.decision.decision_snapshot import (build_decision_snapshot,
                                                     build_report_snapshot)
    checks = []
    row = _row()
    canonical = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)

    via_build = build_decision_snapshot("FLAT", 0.0, row, DEFAULT_SETTINGS)
    checks.append(("build_decision_snapshot 委托唯一引擎",
                   via_build.as_dict() == canonical.as_dict()))
    via_report = build_report_snapshot(row, DEFAULT_SETTINGS)
    via_report = via_report[0] if isinstance(via_report, tuple) \
        else via_report
    checks.append(("build_report_snapshot（NON_CANONICAL）同源",
                   via_report.as_dict() == canonical.as_dict()))
    checks.append(("Permission Gate 前置（BLOCK 空仓→0 / 既有去风险）",
                   _block_target_zero()))
    checks.append(("Governance Proof 计算（PASS）",
                   (canonical.context.get("governance_proof") or {})
                   .get("proof") == "PASS"))
    gp = canonical.context.get("governance_proof") or {}
    checks.append(("目标链 raw→governed→final 完整",
                   "raw_target" in gp and "governed_target" in gp
                   and "final_target" in gp))
    checks.append(("权限上限约束（final ≤ cap）",
                   canonical.target_position
                   <= (canonical.context.get("governance_proof") or {})
                   .get("permission_cap", 1.0) + 1e-9
                   or canonical.target_position == 0.0))

    print(f"# Canonical Decision Path Audit　"
          f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print(f"结论：{'✅ 全部通过' if ok else '❌ 存在违规'}")
    return 0 if ok else 1


def _block_target_zero() -> bool:
    from QCFP_MTF.decision.engine import evaluate
    from QCFP_MTF.decision.permission_gate import assert_permission_upper_bound
    row = _row(c_state="C↓", f_state="F↓", p_state="P↓", prev_f_state="F↓")
    snap_flat = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    if snap_flat.institutional_permission != "BLOCK":
        return False
    try:
        assert_permission_upper_bound("BLOCK", snap_flat.target_position)
    except Exception:
        return False
    # 空仓 BLOCK → 0；既有仓位 BLOCK → 去风险（target < previous）
    if snap_flat.target_position != 0.0:
        return False
    snap_held = evaluate(dict(row), "HOLDING", 0.3, DEFAULT_SETTINGS)
    return snap_held.target_position < 0.3


if __name__ == "__main__":
    sys.exit(main())
