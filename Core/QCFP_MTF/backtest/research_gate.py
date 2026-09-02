# coding: utf-8
"""Research Gate（QCFP-MTF 2.5：G0–G7 分层研究门）

不再是简单 10/10，而是分层的质量门：
    G0 Governance         版本身份完整 / Ledger 可用
    G1 PIT Integrity      PIT-A/B 才可 Research Validated（C 仅探索）
    G2 Signal Integrity   Run Status 无 FAILED（Look-ahead/T+1/成本）
    G3 Statistical        Sharpe>0 且 PF>1（HAC 如可用再叠加）
    G4 OOS Robustness     Rolling OOS Sharpe 中位数 > 0
    G5 Economic           Execution Ablation 盈亏平衡档位（成本压力）
    G6 Execution          T+1 生效无偏验证
    G7 Decision Governance 报告==Ledger / 重放确定性 / 版本身份

总体 = min(gates)：任一 FAIL → FAIL；任一 WARN → WARN；否则 PASS。
"""


def _pct(v):
    return float(v) if v is not None else None


def evaluate_research_gate(summary: dict, extras: dict = None) -> dict:
    extras = extras or {}
    overall = summary.get("overall", {})
    oos = summary.get("rolling_oos_evaluation", []) or []
    rstatus = summary.get("run_status", {}) or {}
    oos_sharpes = [r.get("sharpe") for r in oos if r.get("sharpe") is not None]
    median_oos = sorted(oos_sharpes)[len(oos_sharpes) // 2] if oos_sharpes else None
    sharpe = _pct(overall.get("sharpe"))
    pf = _pct(overall.get("profit_factor"))
    ret = _pct(overall.get("annualized_return"))
    mdd = _pct(overall.get("max_drawdown"))
    pit_grade = summary.get("pit_grade") or rstatus.get("pit_grade") or "C"
    mode = summary.get("pit_disclosure_mode") or "ESTIMATED"
    breakeven = extras.get("cost_stress_breakeven")
    t1_ok = extras.get("t_plus_1_verified", True)
    ledger_ok = extras.get("ledger_ok", True)
    versions_ok = bool(extras.get("model_version") and
                       extras.get("rule_version") and extras.get("schema_version"))

    gates = []
    # G0
    g = "PASS" if versions_ok and ledger_ok else "WARN"
    gates.append({"gate": "G0", "name": "Governance",
                  "status": g,
                  "evidence": f"版本身份完整={versions_ok}，Ledger={ledger_ok}"})
    # G1
    if rstatus.get("status") == "FAILED":
        g = "FAIL"
    elif pit_grade in ("A", "B") and mode == "REAL":
        g = "PASS"
    elif pit_grade in ("A", "B"):
        g = "PASS"
    else:
        g = "WARN"   # PIT-C：探索模式
    gates.append({"gate": "G1", "name": "PIT Integrity",
                  "status": g,
                  "evidence": f"PIT-{pit_grade}（{mode}）"})
    # G2
    g = "FAIL" if rstatus.get("status") == "FAILED" else \
        ("PASS" if rstatus.get("status") == "PASS" else "WARN")
    gates.append({"gate": "G2", "name": "Signal Integrity",
                  "status": g, "evidence": f"Run Status={rstatus.get('status')}"})
    # G3
    g = "PASS" if (sharpe is not None and sharpe > 0
                   and pf is not None and pf > 1) else \
        "WARN" if (sharpe is not None and sharpe > 0) or \
        (pf is not None and pf > 1) else "FAIL"
    gates.append({"gate": "G3", "name": "Statistical",
                  "status": g,
                  "evidence": f"Sharpe={sharpe} PF={pf} Ret={ret} MDD={mdd}"})
    # G4
    g = "PASS" if median_oos is not None and median_oos > 0 else \
        "WARN" if median_oos is not None else "FAIL"
    gates.append({"gate": "G4", "name": "OOS Robustness",
                  "status": g, "evidence": f"median_OOS_Sharpe={median_oos}"})
    # G5
    g = "PASS" if breakeven is not None and breakeven >= 2.0 else \
        "WARN" if breakeven is not None and breakeven >= 1.0 else \
        "WARN" if breakeven is None else "FAIL"
    gates.append({"gate": "G5", "name": "Economic",
                  "status": g,
                  "evidence": f"成本盈亏平衡=×{breakeven if breakeven is not None else '?'}"})
    # G6
    g = "PASS" if t1_ok else "FAIL"
    gates.append({"gate": "G6", "name": "Execution",
                  "status": g, "evidence": f"T+1={t1_ok}"})
    # G7
    g = "PASS" if ledger_ok and versions_ok else "WARN"
    gates.append({"gate": "G7", "name": "Decision Governance",
                  "status": g,
                  "evidence": f"Ledger={ledger_ok} 版本={versions_ok}"})

    statuses = [x["status"] for x in gates]
    overall_status = "FAIL" if "FAIL" in statuses else \
        ("WARN" if "WARN" in statuses else "PASS")
    return {"overall": overall_status,
            "status_label": {
                "PASS": "Research Validated",
                "WARN": "Conditional（研究探索）",
                "FAIL": "Not Validated",
            }.get(overall_status, overall_status),
            "gates": gates}
