# coding: utf-8
"""ABSTAIN / NO_DECISION（QCFP-MTF 2.8：47 号弃权语义）

区分：
    HOLD        系统完成有效判断，决定保持仓位（本身是一个决策）
    NO_DECISION 系统没有足够资格产生新的正式判断

PIT UNKNOWN / Replay FAILED / Ledger invalid / Evidence incomplete
→ 不能输出 HOLD（HOLD 也是决策）。
"""


ABSTAIN_REASONS = ("PIT_UNKNOWN", "REPLAY_FAILED", "LEDGER_INVALID",
                   "EVIDENCE_INCOMPLETE", "CERTIFICATE_MISSING")


def abstain_decision(pit_ok=True, replay_ok=True, ledger_ok=True,
                     evidence_complete=True,
                     certificate_ok=True) -> dict:
    """弃权判定：任一关键证据缺失 → NO_DECISION（不是 HOLD）。"""
    missing = []
    for ok, reason in ((pit_ok, "PIT_UNKNOWN"), (replay_ok, "REPLAY_FAILED"),
                       (ledger_ok, "LEDGER_INVALID"),
                       (evidence_complete, "EVIDENCE_INCOMPLETE"),
                       (certificate_ok, "CERTIFICATE_MISSING")):
        if not ok:
            missing.append(reason)
    if missing:
        return {"decision": "NO_DECISION", "abstain": True,
                "reasons": missing,
                "note": "无法可信判断 ≠ HOLD（HOLD 也是决策）"}
    return {"decision": "HOLD", "abstain": False, "reasons": [],
            "note": "有效判断：保持仓位"}


def abstain_semantics(status: str) -> dict:
    """新 47 号：HOLD ≠ NO_TRADE ≠ ABSTAIN ≠ DECISION_HALTED。"""
    mapping = {
        "HOLD": "系统完成可信判断：维持现有仓位",
        "NO_TRADE": "系统完成可信判断：现在没有值得参与的机会",
        "ABSTAIN": "系统没有足够证据形成可信判断",
        "DECISION_HALTED": "系统基础设施/治理不可信，禁止产生正式新决策",
    }
    s = str(status or "").upper()
    if s not in mapping:
        return {"status": s, "known": False,
                "note": "未知决策语义"}
    return {"status": s, "known": True, "meaning": mapping[s],
            "distinct_from_hold": s != "HOLD",
            "rule": "不交易和不知道为什么不能交易，是两件完全不同的事"}


def never_map_to_hold(reason: str) -> dict:
    """新 47 号：PIT UNKNOWN / Evidence insufficient / Replay
    unavailable / Critical data missing 不能自动映射成 HOLD。"""
    non_hold_reasons = {"PIT_UNKNOWN", "EVIDENCE_INSUFFICIENT",
                        "REPLAY_UNAVAILABLE", "CRITICAL_DATA_MISSING"}
    r = str(reason or "").upper()
    mapped_to_hold = r in non_hold_reasons
    return {"reason": r,
            "must_not_be_hold": mapped_to_hold,
            "violation": mapped_to_hold,
            "rule": "PIT UNKNOWN/证据不足/Replay 不可用/关键数据缺失 "
                    "不能映射成 HOLD"}
