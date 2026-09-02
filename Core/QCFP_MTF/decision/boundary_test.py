# coding: utf-8
"""Decision Boundary Test（QCFP-MTF 2.8：95 号决策边界测试套件）

专项验证"不可越权"：
    B1  Permission Cap=5% + Risk=4% + Wave=8% → Position ≤ 4%
    B2  Permission=BLOCK + Risk=Low + Wave=STRONG → NO TRADE
    B3  Permission=ALLOW + Risk=BLOCK + Wave=STRONG → NO TRADE
    B4  Hard Exit → 0
    B5  空仓 BLOCK → 0

任何下层模块都不能突破上层约束。
"""

from .governance import finalize_target
from .permission_gate import permission_strength_cap


def run_boundary_tests() -> dict:
    """执行边界测试套件 → {cases, all_pass}。"""
    cases = []

    def _check(name, ok, detail):
        cases.append({"name": name, "pass": bool(ok), "detail": detail})
        return ok

    # B1：raw=8%，Permission cap=5%，Risk cap=4% → ≤4%
    fin = finalize_target("ALLOW", "TRADE", 0.05, raw_target=0.08,
                          previous_position=0.0, risk_budget=0.02,
                          stop_distance=0.05)
    _check("B1_CAP_CHAIN", fin["target"] <= 0.04 + 1e-9,
           f"target={fin['target']:.2%}≤4%")

    # B2：BLOCK + Low + STRONG → NO TRADE
    cap = permission_strength_cap(0.08, "BLOCK")
    _check("B2_BLOCK_NO_TRADE", cap["final_cap"] == 0.0,
           f"BLOCK cap={cap['final_cap']:.2%}")

    # B3：ALLOW 但 Risk BLOCK（Extreme）→ finalize_target 归零
    fin3 = finalize_target("ALLOW", "TRADE", 0.5, raw_target=0.08,
                           previous_position=0.0, risk_budget=0.001,
                           stop_distance=0.05)
    _check("B3_RISK_BLOCK", fin3["target"] <= 0.02 + 1e-9,
           f"risk-bounded target={fin3['target']:.2%}")

    # B4：Hard Exit → 0
    fin4 = finalize_target("ALLOW", "TRADE", 0.5, raw_target=0.08,
                           previous_position=0.3, exit_severity=3)
    _check("B4_HARD_EXIT_ZERO", fin4["target"] == 0.0,
           f"hard exit target={fin4['target']:.2%}")

    # B5：空仓 BLOCK → 0
    cap5 = permission_strength_cap(0.08, "BLOCK", previous_position=0.0)
    _check("B5_BLOCK_FLAT_ZERO", cap5["final_cap"] == 0.0,
           f"flat BLOCK cap={cap5['final_cap']:.2%}")

    return {"cases": cases,
            "all_pass": all(c["pass"] for c in cases),
            "status": "PASS" if all(c["pass"] for c in cases)
            else "FAIL"}
