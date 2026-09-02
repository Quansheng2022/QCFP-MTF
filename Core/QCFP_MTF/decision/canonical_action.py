# coding: utf-8
"""CanonicalAction（QCFP-MTF Convergence：新 4 号）

FSM State = Lifecycle Truth；Canonical Action = Execution Intent Truth。
最终 Action 只由 PreviousPosition → FinalTarget 派生：
    0→0 NO_TRADE / 0→>0 ENTRY / x→>x ADD / x→x HOLD /
    x→0<x'<x REDUCE / x→0 EXIT

不变量：任何不一致 → CANONICAL_ACTION_INVARIANT_FAIL → 阻止 Ledger commit。
"""


def canonical_action(previous_position, final_target) -> str:
    prev = float(previous_position or 0.0)
    final = float(final_target or 0.0)
    if prev <= 1e-9 and final <= 1e-9:
        return "NO_TRADE"
    if prev <= 1e-9 and final > 1e-9:
        return "ENTRY"
    if final > prev + 1e-9:
        return "ADD"
    if abs(final - prev) <= 1e-9:
        return "HOLD"
    if final > 1e-9:
        return "REDUCE"
    return "EXIT"


def assert_canonical_action_invariant(previous_position, final_target,
                                      action) -> dict:
    """验收不变量：
        ENTRY  ⇒ previous=0 and final>0
        ADD    ⇒ final>previous>0
        HOLD   ⇒ final==previous>0
        REDUCE ⇒ 0<final<previous
        EXIT   ⇒ previous>0 and final==0
    """
    prev = float(previous_position or 0.0)
    final = float(final_target or 0.0)
    expected = canonical_action(prev, final)
    ok = action == expected
    return {"ok": ok,
            "action": action,
            "expected": expected,
            "previous_position": prev,
            "final_target": final,
            "verdict": "OK" if ok else "CANONICAL_ACTION_INVARIANT_FAIL",
            "rule": "CanonicalAction 只由 PreviousPosition→FinalTarget 派生；"
                    "不一致阻止 Ledger commit"}


def wave_proposal_monotonic(fsm_proposal_target, wave_proposal_target,
                            final_target) -> dict:
    """新 3 号强不变量（正常新增风险路径）：
        FinalTarget ≤ WaveProposalTarget ≤ FSMProposalTarget
    Hard Exit（FinalTarget=0）除外。"""
    fsm = float(fsm_proposal_target or 0.0)
    wave = float(wave_proposal_target or 0.0)
    final = float(final_target or 0.0)
    if final <= 1e-9:   # Hard Exit / NO_TRADE 除外
        return {"monotonic": True, "note": "HardExit/NO_TRADE 除外",
                "fsm": fsm, "wave": wave, "final": final}
    ok = final <= wave + 1e-9 and wave <= fsm + 1e-9
    return {"monotonic": ok,
            "fsm": fsm, "wave": wave, "final": final,
            "verdict": "MONOTONIC" if ok else "WAVE_PROPOSAL_MONOTONICITY_FAIL",
            "rule": "FinalTarget ≤ WaveProposalTarget ≤ FSMProposalTarget"}
