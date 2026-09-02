# coding: utf-8
"""Report Contract（QCFP-MTF 2.8：P0-7 报告只解释事实，不产生事实）

正式报告只能消费：DecisionSnapshot + Ledger + ValidationCertificate +
ExecutionOutcome；禁止报告调用 position sizing/permission/FSM/Wave
再算一次。

验收：删掉报告中的决策计算函数后，报告结果完全不变。
"""


class ReportContractError(ValueError):
    pass


REPORT_LEDGER_FIELDS = (
    ("institutional_permission", "institutional_permission"),
    ("prev_fsm_state", "previous_fsm_state"),
    ("next_fsm_state", "next_fsm_state"),
    ("target_position", "final_target"),
    ("primary_reason", "primary_reason"),
)


def assert_report_ledger_only(snapshot, ledger_row) -> None:
    """报告字段必须与 Ledger 完全一致（不得自行重算）。

    snapshot：DecisionSnapshot（或 dict）
    ledger_row：qcfp_decision_ledger 行（或 dict）
    """
    get_s = snapshot.get if isinstance(snapshot, dict) else \
        (lambda k: getattr(snapshot, k, None))
    get_l = ledger_row.get if isinstance(ledger_row, dict) else \
        (lambda k: getattr(ledger_row, k, None))
    mismatches = []
    for snap_key, ledger_key in REPORT_LEDGER_FIELDS:
        sv = get_s(snap_key)
        lv = get_l(ledger_key)
        if snap_key in ("target_position", "previous_position"):
            sv = round(float(sv or 0.0), 4)
            lv = round(float(lv or 0.0), 4)
        if sv != lv:
            mismatches.append(f"{snap_key}={sv} vs ledger.{ledger_key}={lv}")
    if mismatches:
        raise ReportContractError(
            "Report 违反 Ledger-only 契约（报告重算了决策）："
            + "; ".join(mismatches))


def report_consumes_only(snapshot, ledger_row) -> dict:
    """报告消费审计：返回 {ok, mismatches}（供报告入口调用）。"""
    try:
        assert_report_ledger_only(snapshot, ledger_row)
        return {"ok": True, "mismatches": []}
    except ReportContractError as exc:
        return {"ok": False, "mismatches": [str(exc)]}
