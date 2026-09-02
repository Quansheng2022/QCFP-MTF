# coding: utf-8
"""Scenario Stress Matrix（QCFP-MTF 2.8：92 号多情景压力矩阵）

把压力测试升级为 2D/3D 矩阵：
    Market × Volatility × Liquidity × Institutional

验证每个情景下 Permission > Risk > Signal 是否仍成立。
"""


MATRIX_SCENARIOS = [
    {"market": "Bull", "vol": "Low", "liquidity": "High",
     "institutional": "Strong", "label": "正常"},
    {"market": "Bull", "vol": "High", "liquidity": "Medium",
     "institutional": "Weak", "label": "压力"},
    {"market": "Bear", "vol": "High", "liquidity": "Low",
     "institutional": "Weak", "label": "极端"},
    {"market": "Transition", "vol": "High", "liquidity": "Low",
     "institutional": "Mixed", "label": "高风险"},
    {"market": "Crash", "vol": "Extreme", "liquidity": "Collapse",
     "institutional": "Exit", "label": "生存"},
]


def scenario_parameters(scenario: dict) -> dict:
    """矩阵情景 → 决策链输入参数。"""
    s = scenario
    risk = {"Low": "Low", "Medium": "Medium", "High": "High",
            "Extreme": "Extreme"}.get(s["vol"], "Medium")
    perm = {"Strong": "STRONG_ALLOW", "Weak": "WATCH",
            "Mixed": "TEST", "Exit": "BLOCK"}.get(
        s["institutional"], "WATCH")
    port = {"High": "NORMAL", "Medium": "DEFENSIVE",
            "Low": "RISK_OFF", "Collapse": "RISK_OFF"}.get(
        s["liquidity"], "NORMAL")
    regime = {"Bull": "Bull", "Bear": "Bear", "Crash": "Crisis",
              "Transition": "Sideway"}.get(s["market"], "Sideway")
    return {"risk_level": risk, "permission": perm,
            "portfolio_state": port, "market_regime": regime,
            "liquidity_flag": "LIQUIDITY_LOW" if s["liquidity"] in
            ("Low", "Collapse") else "LIQUIDITY_OK"}


def stress_matrix(evaluate_fn, base_row, previous_state, previous_position,
                  settings) -> dict:
    """运行 5 情景矩阵，验证 Permission > Risk > Signal。"""
    from ..governance.conflict import resolve_conflict
    rows = []
    all_safe = True
    for sc in MATRIX_SCENARIOS:
        params = scenario_parameters(sc)
        row = dict(base_row)
        row.update(params)
        snap = evaluate_fn(row, previous_state, previous_position, settings)
        conflict = resolve_conflict(
            exit_event_kind=snap.exit_event_kind,
            risk_level=row.get("risk_level"),
            permission=snap.institutional_permission,
            fsm_next=snap.next_fsm_state,
            wave_strength=row.get("wave_strength"),
            setup_type=snap.setup_type,
            portfolio_state=row.get("portfolio_state"),
            liquidity_flag=row.get("liquidity_flag"))
        # 安全判定：Risk/Permission 优先于 Wave
        safe = conflict["winning_rule"] in ("GOVERNANCE_BLOCK", "HARD_EXIT",
                                            "RISK_BLOCK",
                                            "INSTITUTIONAL_PERMISSION",
                                            "PORTFOLIO_BLOCK",
                                            "LIQUIDITY_BLOCK", "NONE") \
            or (conflict["winning_rule"] == "WAVE"
                and row.get("risk_level") in ("Low", "Medium")
                and snap.institutional_permission in ("ALLOW",
                                                      "STRONG_ALLOW"))
        all_safe = all_safe and safe
        rows.append({
            **sc, "permission": snap.institutional_permission,
            "risk": row.get("risk_level"),
            "fsm": f"{snap.prev_fsm_state}→{snap.next_fsm_state}",
            "target": round(float(snap.target_position or 0.0), 4),
            "winning_rule": conflict["winning_rule"],
            "safe": safe,
        })
    return {"scenarios": rows, "all_safe": all_safe}
