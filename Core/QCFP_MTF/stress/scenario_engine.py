# coding: utf-8
"""Scenario / Stress Engine（QCFP-MTF 2.8：46 号情景压力引擎）

七类市场状态冲击，观察 Permission / Wave / FSM / Risk / Portfolio /
Final Target 是否自动收缩：
    S1 Market -10%     S2 Vol ×2     S3 Liquidity -50%
    S4 Sector Crash    S5 Permission Deteriorates
    S6 Wave Failure    S7 Execution Slippage ×3

理想：Shock → Risk↑ → Permission↓ → Target↓ → Exposure↓
失败：Shock 后 Wave Score 仍高且继续加仓 → 判定 NOT_RISK_RESPONSIVE。
"""


SCENARIOS = {
    "market_shock": {"row_overrides": {"risk_level": "High",
                                       "market_context": "risk_off",
                                       "market_regime": "Bear"}},
    "vol_shock": {"row_overrides": {"risk_level": "Extreme",
                                    "market_regime": "HighVolatility"}},
    "liquidity_shock": {"row_overrides": {"liquidity_flag": "LIQUIDITY_LOW",
                                          "participation_cap": 0.02}},
    "sector_crash": {"row_overrides": {"portfolio_state": "RISK_OFF",
                                       "risk_level": "High"}},
    "permission_deteriorates": {"row_overrides": {"c_state": "C↓",
                                                  "f_state": "F↓",
                                                  "p_state": "P↓",
                                                  "prev_f_state": "F↓"}},
    "wave_failure": {"row_overrides": {"tactical_signal": "Breakdown",
                                       "daily_state": "DAILY_NEUTRAL",
                                       "wave_strength": 0.0}},
    "execution_slippage": {"row_overrides": {"execution_cost": 0.03}},
}


def scenario_engine(evaluate_fn, base_row, previous_state, previous_position,
                    settings, scenarios=None) -> dict:
    """在 base_row 上叠加七情景 → 重跑决策链 → 汇总结果。

    evaluate_fn：engine.evaluate（或等价函数）。
    """
    scenarios = scenarios or SCENARIOS
    results = {}
    base_snap = evaluate_fn(dict(base_row), previous_state,
                            previous_position, settings)
    base_target = float(base_snap.target_position or 0.0)
    for name, spec in scenarios.items():
        row = dict(base_row)
        row.update(spec.get("row_overrides", {}))
        snap = evaluate_fn(row, previous_state, previous_position, settings)
        target = float(snap.target_position or 0.0)
        results[name] = {
            "target": round(target, 4),
            "permission": snap.institutional_permission,
            "fsm": f"{snap.prev_fsm_state}→{snap.next_fsm_state}",
            "risk": snap.exit_event_kind,
            "primary_reason": snap.primary_reason,
            "shrunk": target < base_target - 1e-9,
        }
    return {"base_target": round(base_target, 4), "scenarios": results,
            "risk_responsive": all(r["shrunk"] for r in results.values()
                                   if base_target > 1e-9)}


def scenario_verdict(report: dict) -> str:
    """PASS：冲击下目标自动收缩（风险响应）；FAIL：继续加仓。"""
    if report["base_target"] <= 1e-9:
        return "PASS_NO_EXPOSURE"
    return "PASS_RISK_RESPONSIVE" if report["risk_responsive"] \
        else "FAIL_NOT_RISK_RESPONSIVE"


def scenario_to_md(report: dict) -> str:
    lines = [
        "# Scenario Stress Report",
        "",
        f"**Base Target：{report['base_target']:.1%}**　"
        f"Verdict：{scenario_verdict(report)}",
        "",
        "| 情景 | Target | Permission | FSM | Risk | 收缩 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, r in report["scenarios"].items():
        lines.append(
            f"| {name} | {r['target']:.1%} | {r['permission']} | "
            f"{r['fsm']} | {r['risk']} | "
            f"{'✅' if r['shrunk'] else '❌'} |")
    return "\n".join(lines)
